import json
import re
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Prefetch, Q, Sum
from django.http import HttpResponseForbidden, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie

from django import forms
from django.urls import reverse_lazy
from django.contrib.auth.mixins import UserPassesTestMixin
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from .models import (
    CategoriaVehiculo,
    Casilla,
    Operador,
    SentidoCobro,
    Tarifa,
    Turno,
    Venta,
    VentaModificacion,
    Ruta,
    Estacion,
)


# Decorador que exime a esta función de validar el token CSRF (necesario cuando se reciben peticiones desde un cliente API como fetch)
@csrf_exempt
def api_login_view(request): # Define la función de la vista para manejar el inicio de sesión, recibiendo la petición HTTP en la variable 'request'

    # Verifica si el método de la petición NO es POST (ej. si intentan entrar usando GET desde el navegador)
    if request.method != "POST":
        # Retorna un error en formato JSON indicando que el método no está permitido con el código de estado HTTP 405
        return JsonResponse({"detail": "Método no permitido"}, status=405)

    # Inicia un bloque try-except para capturar posibles errores al procesar el texto que envía el cliente
    try:
        # Lee el cuerpo bruto de la petición ('request.body') y lo convierte de texto JSON a un diccionario de Python
        data = json.loads(request.body)
    # Si el texto enviado por el frontend no es un JSON válido o está mal formado
    except json.JSONDecodeError:
        # Retorna un error indicando "JSON inválido" junto con el código de estado HTTP 400 (Bad Request)
        return JsonResponse({"detail": "JSON inválido"}, status=400)

    # Llama a la función de autenticación de Django pasando los datos recibidos del frontend
    operador = authenticate(
        request,
        # Obtiene el valor del campo "legajo" del JSON y lo usa como el nombre de usuario (username)
        username=data.get("legajo"),
        # Obtiene el valor del campo "password" del JSON para validarlo
        password=data.get("password"),
    )

    # Si las credenciales son incorrectas o el usuario no existe, 'authenticate' devuelve 'None'
    if operador is None:
        # Retorna un mensaje indicando "Credenciales inválidas" con el código de estado HTTP 401 (No autorizado)
        return JsonResponse({"detail": "Credenciales inválidas"}, status=401)

    # Crea la sesión: sin esto Django ve al usuario como anónimo y el paso 2 devuelve 403
    auth_login(request, operador)

    # Si la autenticación fue exitosa, retorna una respuesta JSON con el código de estado 200 (OK por defecto)
    return JsonResponse({
    "legajo": operador.legajo,
    "es_administrador": operador.es_administrador,
    })

@ensure_csrf_cookie
def login_view(request):
    """Vista del formulario de inicio de sesión por legajo."""
    return render(request, 'login.html')

@login_required(login_url="login")
@ensure_csrf_cookie
def apertura_turno_view(request):
    """Vista para abrir caja/turno (monto inicial y sentido de cobro)."""
    # Si el operador ya tiene un turno abierto, no tiene sentido abrir otro
    if _turno_abierto(request.user):
        return redirect("cobro")
    rutas = (
        Ruta.objects.filter(estaciones__casillas__isnull=False)
        .distinct()
        .order_by("nombre")
    )
    casillas = (
        Casilla.objects.select_related("estacion", "estacion__ruta")
        .order_by(
            "estacion__ruta__nombre",
            "estacion__numero_estacion",
            "numero_casilla",
        )
    )
    return render(
        request,
        "apertura_turno.html",
        {"rutas": rutas, "casillas": casillas, "sentidos": SentidoCobro.choices},
    )

@login_required(login_url="login")
@ensure_csrf_cookie
def cobro_view(request):
    """Vista principal de cobro de peaje, categorías y emisión de tickets."""
    return render(request, 'cobro.html')

@login_required(login_url="login")
@ensure_csrf_cookie
def cierre_caja_view(request):
    """Vista para resumen de cierre de turno e informe de caja."""
    return render(request, 'cierre_caja.html')

def prueba(request):
    """Vista de prueba para desarrollo y testing."""
    return render(request, 'prueba.html')
   
def crear_usuario(request):
    """Vista para crear un nuevo usuario (operador)."""
    return render(request, 'panel/crear_usuario.html')

@csrf_exempt
def api_operadores_view(request):
    # Solo se acepta POST (el formulario manda los datos así)
    if request.method != "POST":
        return JsonResponse({"detail": "Método no permitido"}, status=405)

    # Solo un administrador logueado puede crear usuarios
    if not (request.user.is_authenticated and request.user.es_administrador):
        return JsonResponse({"detail": "No autorizado"}, status=403)

    # Lee el JSON que manda el formulario
    try:
        data = json.loads(request.body)
        legajo = int(data.get("legajo"))
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"detail": "Datos inválidos"}, status=400)

    # El legajo es la clave primaria: no puede repetirse
    if Operador.objects.filter(legajo=legajo).exists():
        return JsonResponse({"detail": "Ya existe ese legajo"}, status=400)

    # create_user guarda la contraseña encriptada
    Operador.objects.create_user(
        legajo=legajo,
        password=data.get("password"),
        nombre=data.get("nombre"),
        apellido=data.get("apellido"),
        es_administrador=data.get("es_administrador", False),
    )
    return JsonResponse({"legajo": legajo}, status=201)


# ======================================================================
#  API de turnos y ventas
#  Autenticación por sesión de Django (la que crea api_login_view) y
#  protección CSRF activa: el JS manda el token en el header X-CSRFToken.
# ======================================================================

def api_operador(metodo):
    """Exige el método HTTP indicado y un operador con sesión iniciada."""
    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if request.method != metodo:
                return JsonResponse({"detail": "Método no permitido"}, status=405)
            if not request.user.is_authenticated:
                return JsonResponse({"detail": "Sesión no iniciada"}, status=401)
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador


def _leer_json(request):
    """Devuelve el cuerpo JSON como dict, o None si es inválido."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _turno_abierto(operador):
    """Turno actualmente abierto del operador (o None)."""
    return (
        Turno.objects.select_related("casilla__estacion__ruta", "operador")
        .filter(
            operador=operador,
            fecha_hora_apertura__isnull=False,
            fecha_hora_cierre__isnull=True,
        )
        .order_by("-fecha_hora_apertura")
        .first()
    )


def _tarifa_vigente(categoria_id, hoy):
    """Tarifa de la categoría que está vigente en la fecha dada."""
    return (
        Tarifa.objects.select_related("categoria")
        .filter(categoria_id=categoria_id, vigente_desde__lte=hoy)
        .filter(Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=hoy))
        .order_by("-vigente_desde")
        .first()
    )


def _numero_ticket(venta):
    return f"{venta.turno.casilla.estacion.numero_estacion:04d}-{venta.numero_ticket:06d}"


def _datos_estacion(casilla):
    e = casilla.estacion
    return {
        "estacion_nombre": e.nombre,
        "estacion_numero": e.numero_estacion,
        "ruta_nombre": e.ruta.nombre,
        "kilometro": format(e.kilometro.normalize(), "f"),
    }


def _turno_a_dict(turno):
    return {
        "id_turno": turno.id_turno,
        "legajo": turno.operador_id,
        "casilla_id": turno.casilla_id,
        "casilla_numero": turno.casilla.numero_casilla,
        "sentido": turno.sentido_cobro,
        "sentido_display": turno.get_sentido_cobro_display(),
        "monto_cambio_inicial": str(turno.monto_cambio_inicial),
        "fecha_hora_apertura": turno.fecha_hora_apertura.isoformat(),
        "fecha_hora_cierre": (
            turno.fecha_hora_cierre.isoformat() if turno.fecha_hora_cierre else None
        ),
        **_datos_estacion(turno.casilla),
    }


def _resumen_turno(turno):
    """Cantidad de vehículos y recaudación por categoría, calculado desde la BD."""
    filas = (
        Venta.objects.filter(turno=turno)
        .values("tarifa__categoria_id", "tarifa__categoria__nombre")
        .annotate(cantidad=Count("numero_ticket"), subtotal=Sum("importe_cobrado"))
        .order_by("tarifa__categoria_id")
    )
    categorias = [
        {
            "categoria_id": f["tarifa__categoria_id"],
            "categoria": f["tarifa__categoria__nombre"],
            "cantidad": f["cantidad"],
            "subtotal": str(Decimal(f["subtotal"]).quantize(Decimal("0.01"))),
        }
        for f in filas
    ]
    return {
        "categorias": categorias,
        "total_vehiculos": sum(c["cantidad"] for c in categorias),
        "total_recaudado": str(sum((Decimal(c["subtotal"]) for c in categorias), Decimal("0.00"))),
    }


def _venta_a_dict(venta):
    return {
        "numero_ticket": venta.numero_ticket,
        "ticket": _numero_ticket(venta),
        "categoria_id": venta.tarifa.categoria_id,
        "categoria": venta.tarifa.categoria.nombre,
        "importe": str(venta.importe_cobrado),
        "patente": venta.patente_detectada or "S/PATENTE",
        "fecha_hora_emision": timezone.localtime(venta.fecha_hora_emision).isoformat(),
        "motivo_modificacion": venta.motivo_modificacion,
    }


def _ventas_turno(turno):
    return [
        _venta_a_dict(venta)
        for venta in (
            Venta.objects.select_related(
                "tarifa__categoria", "turno__casilla__estacion"
            )
            .filter(turno=turno)
            .order_by("numero_ticket")
        )
    ]


@api_operador("POST")
def api_turno_abrir(request):
    """Abre un turno: crea la fila en la tabla `turno`."""
    data = _leer_json(request)
    if data is None:
        return JsonResponse({"detail": "JSON inválido"}, status=400)

    sentido = data.get("sentido")
    if sentido not in SentidoCobro.values:
        return JsonResponse({"detail": "Sentido de cobro inválido"}, status=400)

    try:
        ruta_id = int(data.get("ruta_id"))
    except (TypeError, ValueError):
        return JsonResponse({"detail": "Ruta inválida"}, status=400)

    try:
        casilla = Casilla.objects.select_related("estacion__ruta").get(
            pk=int(data.get("casilla_id"))
        )
    except (TypeError, ValueError, Casilla.DoesNotExist):
        return JsonResponse({"detail": "Casilla inválida"}, status=400)

    if casilla.estacion.ruta_id != ruta_id:
        return JsonResponse(
            {"detail": "La casilla no pertenece a la ruta seleccionada"}, status=400
        )

    try:
        monto = Decimal(str(data.get("monto_cambio_inicial")))
        if not monto.is_finite() or monto < 0 or monto >= Decimal("100000000"):
            raise InvalidOperation
        monto = monto.quantize(Decimal("0.01"))
    except InvalidOperation:
        return JsonResponse({"detail": "Monto de cambio inicial inválido"}, status=400)

    with transaction.atomic():
        # Si ya tenía un turno abierto (ej. recargó la página), lo retoma
        existente = _turno_abierto(request.user)
        if existente:
            return JsonResponse(
                {"turno": _turno_a_dict(existente), "reanudado": True}, status=200
            )

        casilla_ocupada = Turno.objects.filter(
            casilla=casilla,
            fecha_hora_apertura__isnull=False,
            fecha_hora_cierre__isnull=True,
        ).exists()
        if casilla_ocupada:
            return JsonResponse(
                {"detail": "Esa casilla ya tiene un turno abierto"}, status=409
            )

        ahora = timezone.now()
        turno = Turno.objects.create(
            casilla=casilla,
            operador=request.user,
            sentido_cobro=sentido,
            monto_cambio_inicial=monto,
            inicio_programado=ahora,
            fin_programado=ahora + timedelta(hours=8),  # turno estándar de 8 hs
            fecha_hora_apertura=ahora,
        )
    return JsonResponse({"turno": _turno_a_dict(turno), "reanudado": False}, status=201)


@api_operador("GET")
def api_turno_actual(request):
    """Devuelve el turno abierto del operador con su resumen de ventas."""
    turno = _turno_abierto(request.user)
    if turno is None:
        return JsonResponse({"detail": "No hay un turno abierto"}, status=404)
    return JsonResponse(
        {
            "turno": _turno_a_dict(turno),
            "resumen": _resumen_turno(turno),
            "ventas": _ventas_turno(turno),
        }
    )


@api_operador("POST")
def api_turno_cerrar(request):
    """Cierra el turno abierto: completa fecha_hora_cierre."""
    with transaction.atomic():
        turno = _turno_abierto(request.user)
        if turno is None:
            return JsonResponse({"detail": "No hay un turno abierto"}, status=409)
        turno.fecha_hora_cierre = timezone.now()
        turno.save(update_fields=["fecha_hora_cierre"])
    return JsonResponse({"turno": _turno_a_dict(turno), "resumen": _resumen_turno(turno)})


@api_operador("GET")
def api_tarifas(request):
    """Categorías con su tarifa vigente hoy (para armar los botones de cobro)."""
    hoy = timezone.localdate()
    resultado = []
    for categoria in CategoriaVehiculo.objects.order_by("id_categoria"):
        tarifa = _tarifa_vigente(categoria.id_categoria, hoy)
        if tarifa:
            resultado.append(
                {
                    "categoria_id": categoria.id_categoria,
                    "nombre": categoria.nombre,
                    "monto": str(tarifa.monto),
                }
            )
    return JsonResponse({"tarifas": resultado})


@api_operador("POST")
def api_ventas(request):
    """
    Registra una venta (ticket) en la tabla `venta`.
    El importe NO lo manda el navegador: se toma de la tarifa vigente en la BD.
    """
    data = _leer_json(request)
    if data is None:
        return JsonResponse({"detail": "JSON inválido"}, status=400)

    try:
        categoria_id = int(data.get("categoria_id"))
    except (TypeError, ValueError):
        return JsonResponse({"detail": "Categoría inválida"}, status=400)

    # Patente opcional: se normaliza (mayúsculas, sin espacios ni guiones)
    patente = re.sub(r"[\s-]", "", str(data.get("patente") or "")).upper()
    if patente == "S/PATENTE":
        patente = ""
    if patente and not re.fullmatch(r"[A-Z0-9]{1,15}", patente):
        return JsonResponse({"detail": "Patente inválida"}, status=400)

    turno = _turno_abierto(request.user)
    if turno is None:
        return JsonResponse(
            {"detail": "No hay un turno abierto. Abrí un turno antes de cobrar."},
            status=409,
        )

    tarifa = _tarifa_vigente(categoria_id, timezone.localdate())
    if tarifa is None:
        return JsonResponse(
            {"detail": "No hay una tarifa vigente para esa categoría"}, status=404
        )

    venta = Venta.objects.create(
        turno=turno,
        tarifa=tarifa,
        importe_cobrado=tarifa.monto,
        patente_detectada=patente or None,
    )
    return JsonResponse(
        {
            "numero_ticket": venta.numero_ticket,
            "ticket": _numero_ticket(venta),
            "fecha_hora_emision": timezone.localtime(venta.fecha_hora_emision).isoformat(),
            "categoria": tarifa.categoria.nombre,
            "importe": str(venta.importe_cobrado),
            "patente": venta.patente_detectada or "S/PATENTE",
            "casilla_numero": turno.casilla.numero_casilla,
            "legajo": turno.operador_id,
            **_datos_estacion(turno.casilla),
        },
        status=201,
    )


@api_operador("POST")
def api_venta_editar(request, venta_id):
    """Actualiza una venta del turno abierto y registra el motivo del cambio."""
    data = _leer_json(request)
    if data is None:
        return JsonResponse({"detail": "JSON inválido"}, status=400)

    turno = _turno_abierto(request.user)
    if turno is None:
        return JsonResponse({"detail": "No hay un turno abierto"}, status=409)

    try:
        categoria_id = int(data.get("categoria_id"))
    except (TypeError, ValueError):
        return JsonResponse({"detail": "Categoría inválida"}, status=400)

    patente = re.sub(r"[\s-]", "", str(data.get("patente") or "")).upper()
    if patente == "S/PATENTE":
        patente = ""
    if patente and not re.fullmatch(r"[A-Z0-9]{1,15}", patente):
        return JsonResponse({"detail": "Patente inválida"}, status=400)

    motivo = str(data.get("motivo") or "").strip()
    if not motivo:
        return JsonResponse({"detail": "El motivo del cambio es obligatorio"}, status=400)

    tarifa = _tarifa_vigente(categoria_id, timezone.localdate())
    if tarifa is None:
        return JsonResponse(
            {"detail": "No hay una tarifa vigente para esa categoría"}, status=404
        )

    try:
        venta = Venta.objects.select_related(
            "tarifa__categoria", "turno__casilla__estacion"
        ).get(pk=venta_id, turno=turno)
    except Venta.DoesNotExist:
        return JsonResponse({"detail": "La venta no pertenece al turno abierto"}, status=404)

    with transaction.atomic():
        VentaModificacion.objects.create(
            venta=venta,
            operador=request.user,
            categoria_anterior=venta.tarifa.categoria.nombre,
            categoria_nueva=tarifa.categoria.nombre,
            patente_anterior=venta.patente_detectada or "",
            patente_nueva=patente,
            motivo=motivo,
        )
        venta.tarifa = tarifa
        venta.importe_cobrado = tarifa.monto
        venta.patente_detectada = patente or None
        venta.motivo_modificacion = motivo
        venta.save(
            update_fields=[
                "tarifa",
                "importe_cobrado",
                "patente_detectada",
                "motivo_modificacion",
            ]
        )
    return JsonResponse({"venta": _venta_a_dict(venta)})


def _solo_admin_api(request):
    if not request.user.is_authenticated or not request.user.es_administrador:
        return JsonResponse({"detail": "No autorizado"}, status=403)
    return None


def estadisticas_view(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if not request.user.es_administrador:
        return HttpResponseForbidden("No autorizado")
    return render(
        request,
        "panel/estadisticas.html",
        {
            "rutas": Ruta.objects.order_by("nombre"),
            "casillas": Casilla.objects.select_related("estacion", "estacion__ruta").order_by(
                "estacion__ruta__nombre", "estacion__numero_estacion", "numero_casilla"
            ),
            "empleados": Operador.objects.order_by("apellido", "nombre"),
        },
    )


def api_estadisticas_casilla(request):
    if request.method != "GET":
        return JsonResponse({"detail": "Método no permitido"}, status=405)
    no_autorizado = _solo_admin_api(request)
    if no_autorizado:
        return no_autorizado

    try:
        ruta_id = int(request.GET.get("ruta_id"))
        casilla_id = int(request.GET.get("casilla_id"))
    except (TypeError, ValueError):
        return JsonResponse({"detail": "Ruta o casilla inválida"}, status=400)

    casilla = (
        Casilla.objects.select_related("estacion__ruta")
        .filter(pk=casilla_id, estacion__ruta_id=ruta_id)
        .first()
    )
    if casilla is None:
        return JsonResponse({"detail": "La casilla no pertenece a la ruta"}, status=404)

    ventas = Venta.objects.filter(turno__casilla=casilla)
    categorias = list(
        ventas.values("tarifa__categoria__nombre")
        .annotate(cantidad=Count("numero_ticket"))
        .order_by("tarifa__categoria__nombre")
    )
    total_ventas = sum(categoria["cantidad"] for categoria in categorias)
    categorias_resultado = [
        {
            "nombre": categoria["tarifa__categoria__nombre"],
            "cantidad": categoria["cantidad"],
            "porcentaje": (
                round(categoria["cantidad"] * 100 / total_ventas, 2)
                if total_ventas
                else 0
            ),
        }
        for categoria in categorias
    ]

    ventas_por_hora = [0] * 24
    for fecha_hora in ventas.values_list("fecha_hora_emision", flat=True).iterator():
        ventas_por_hora[timezone.localtime(fecha_hora).hour] += 1
    hora_pico = max(range(24), key=ventas_por_hora.__getitem__) if total_ventas else None

    return JsonResponse(
        {
            "ruta": casilla.estacion.ruta.nombre,
            "estacion": casilla.estacion.nombre,
            "casilla": casilla.numero_casilla,
            "total_ventas": total_ventas,
            "categorias": categorias_resultado,
            "ventas_por_hora": ventas_por_hora,
            "hora_pico": hora_pico,
        }
    )


def api_estadisticas_empleado(request):
    if request.method != "GET":
        return JsonResponse({"detail": "Método no permitido"}, status=405)
    no_autorizado = _solo_admin_api(request)
    if no_autorizado:
        return no_autorizado

    try:
        legajo = int(request.GET.get("legajo"))
    except (TypeError, ValueError):
        return JsonResponse({"detail": "Empleado inválido"}, status=400)

    empleado = Operador.objects.filter(pk=legajo).first()
    if empleado is None:
        return JsonResponse({"detail": "Empleado inexistente"}, status=404)

    turnos_por_casilla = list(
        Turno.objects.filter(operador=empleado)
        .values(
            "casilla_id",
            "casilla__numero_casilla",
            "casilla__estacion__nombre",
            "casilla__estacion__ruta__nombre",
        )
        .annotate(
            cantidad_turnos=Count("id_turno", distinct=True),
            cantidad_ventas=Count("ventas", distinct=True),
        )
        .order_by("casilla__estacion__ruta__nombre", "casilla__numero_casilla")
    )
    resultado_casillas = [
        {
            "casilla_id": item["casilla_id"],
            "casilla": item["casilla__numero_casilla"],
            "estacion": item["casilla__estacion__nombre"],
            "ruta": item["casilla__estacion__ruta__nombre"],
            "turnos": item["cantidad_turnos"],
            "ventas": item["cantidad_ventas"],
        }
        for item in turnos_por_casilla
    ]

    correcciones = [
        {
            "ticket": _numero_ticket(modificacion.venta),
            "fecha_hora": timezone.localtime(modificacion.fecha_hora).isoformat(),
            "casilla": modificacion.venta.turno.casilla.numero_casilla,
            "categoria_anterior": modificacion.categoria_anterior,
            "categoria_nueva": modificacion.categoria_nueva,
            "patente_anterior": modificacion.patente_anterior or "S/PATENTE",
            "patente_nueva": modificacion.patente_nueva or "S/PATENTE",
            "motivo": modificacion.motivo,
        }
        for modificacion in (
            VentaModificacion.objects.filter(operador=empleado)
            .select_related("venta__turno__casilla__estacion")
            .order_by("-fecha_hora", "-id")
        )
    ]

    return JsonResponse(
        {
            "empleado": {
                "legajo": empleado.legajo,
                "nombre": f"{empleado.nombre} {empleado.apellido}",
            },
            "total_ventas": Venta.objects.filter(turno__operador=empleado).count(),
            "total_turnos": Turno.objects.filter(operador=empleado).count(),
            "casillas": resultado_casillas,
            "total_correcciones": len(correcciones),
            "correcciones": correcciones,
        }
    )


def api_logout_view(request):
    """Cierra la sesión del operador."""
    if request.method != "POST":
        return JsonResponse({"detail": "Método no permitido"}, status=405)
    auth_logout(request)
    return JsonResponse({"detail": "Sesión cerrada"})

class SoloAdminMixin(UserPassesTestMixin):
    """Protege la vista: solo entra un administrador logueado."""
    # A dónde manda a quien no está logueado (nombre de la URL del login)
    login_url = 'login'

    def test_func(self):
    # Django corre esto antes de ejecutar la vista; si devuelve False, la bloquea
        u = self.request.user
        return u.is_authenticated and u.es_administrador


class TarifaMontoForm(forms.Form):
    monto = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Precio",
    )


def _categorias_con_tarifa_actual():
    hoy = timezone.localdate()
    categorias = CategoriaVehiculo.objects.order_by("id_categoria")
    for categoria in categorias:
        categoria.tarifa_actual = _tarifa_vigente(categoria.id_categoria, hoy)
    return categorias


def tarifas_admin_view(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if not request.user.es_administrador:
        return HttpResponseForbidden("No autorizado")
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    return render(
        request,
        "panel/tarifas.html",
        {"categorias": _categorias_con_tarifa_actual()},
    )


def tarifa_actualizar_view(request, categoria_id):
    if not request.user.is_authenticated:
        return redirect("login")
    if not request.user.es_administrador:
        return HttpResponseForbidden("No autorizado")
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    categoria = get_object_or_404(CategoriaVehiculo, pk=categoria_id)
    form = TarifaMontoForm(request.POST)
    if not form.is_valid():
        errores = "; ".join(
            error for error_list in form.errors.values() for error in error_list
        )
        messages.error(request, f"No se pudo actualizar {categoria.nombre}: {errores}")
        return redirect("tarifas")

    hoy = timezone.localdate()
    with transaction.atomic():
        tarifa_actual = _tarifa_vigente(categoria.id_categoria, hoy)
        if tarifa_actual and tarifa_actual.vigente_desde == hoy:
            tarifa_actual.monto = form.cleaned_data["monto"]
            tarifa_actual.save(update_fields=["monto"])
        else:
            if tarifa_actual:
                tarifa_actual.vigente_hasta = hoy - timedelta(days=1)
                tarifa_actual.save(update_fields=["vigente_hasta"])
            Tarifa.objects.create(
                categoria=categoria,
                monto=form.cleaned_data["monto"],
                vigente_desde=hoy,
            )

    messages.success(request, f"Tarifa de {categoria.nombre} actualizada correctamente.")
    return redirect("tarifas")


class BootstrapFormMixin:
    """Le pone clases de Bootstrap a los campos del formulario, sin escribir HTML a mano."""
    def get_form(self, form_class=None):
        # Pide a Django el formulario que armó solo a partir de "fields"
        form = super().get_form(form_class)
        for campo in form.fields.values():
            if isinstance(campo.widget, forms.Select):
                # Los desplegables (claves foráneas) usan form-select
                campo.widget.attrs['class'] = 'form-select'
            elif isinstance(campo.widget, forms.CheckboxInput):
                # Las casillas de tilde (campos booleanos) usan form-check-input
                campo.widget.attrs['class'] = 'form-check-input'
            else:
                # El resto (texto, números) usa form-control
                campo.widget.attrs['class'] = 'form-control'
        return form


class RutaListView(SoloAdminMixin, ListView):
    """Lista todas las rutas."""
    model = Ruta                                   # Qué modelo listar
    template_name = 'panel/rutas_lista.html'       # Template que se muestra
    context_object_name = 'rutas'                  # Nombre de la lista dentro del template
    ordering = ['nombre']                          # Orden alfabético


class RutaCreateView(SoloAdminMixin, BootstrapFormMixin, CreateView):
    """Formulario para crear una ruta nueva."""
    model = Ruta
    fields = ['nombre']                            # Campos del modelo que se piden en el formulario
    template_name = 'panel/form_generico.html'     # Un solo template de formulario para todo
    success_url = reverse_lazy('rutas')            # A dónde vuelve después de guardar
    # Variables fijas que recibe el template: el título y a qué URL vuelve el botón "Volver"
    extra_context = {'titulo': 'Nueva ruta', 'volver': 'rutas'}


class RutaUpdateView(SoloAdminMixin, BootstrapFormMixin, UpdateView):
    """Formulario para modificar una ruta existente (el pk viene en la URL)."""
    model = Ruta
    fields = ['nombre']
    template_name = 'panel/form_generico.html'
    success_url = reverse_lazy('rutas')
    extra_context = {'titulo': 'Modificar ruta', 'volver': 'rutas'}


class RutaDeleteView(SoloAdminMixin, DeleteView):
    """Pantalla de confirmación y borrado de una ruta."""
    model = Ruta
    template_name = 'panel/confirmar_borrado.html'
    success_url = reverse_lazy('rutas')
    extra_context = {'volver': 'rutas'}

class EstacionListView(SoloAdminMixin, ListView):
    """Lista todas las estaciones."""
    model = Estacion                                    # Qué modelo listar
    template_name = 'panel/estaciones_lista.html'       # Template que se muestra
    context_object_name = 'estaciones'                  # Nombre de la lista dentro del template
    # select_related('ruta') trae la ruta junto con cada estación en una sola consulta,
    # en vez de hacer una consulta extra por cada fila de la tabla
    # Ordena primero por nombre de ruta y después por número de estación
    queryset = Estacion.objects.select_related('ruta').order_by('ruta__nombre', 'numero_estacion')


class EstacionCreateView(SoloAdminMixin, BootstrapFormMixin, CreateView):
    """Formulario para crear una estación nueva."""
    model = Estacion
    # 'ruta' es una clave foránea: Django la dibuja sola como un desplegable con las rutas
    fields = ['ruta', 'nombre', 'numero_estacion', 'kilometro']
    template_name = 'panel/form_generico.html'          # El mismo template de formulario que usan las rutas
    success_url = reverse_lazy('estaciones')            # A dónde vuelve después de guardar
    # Título que se muestra y nombre de la URL a la que lleva el botón "Volver"
    extra_context = {'titulo': 'Nueva estación', 'volver': 'estaciones'}


class EstacionUpdateView(SoloAdminMixin, BootstrapFormMixin, UpdateView):
    """Formulario para modificar una estación existente (el pk viene en la URL)."""
    model = Estacion
    fields = ['ruta', 'nombre', 'numero_estacion', 'kilometro']
    template_name = 'panel/form_generico.html'
    success_url = reverse_lazy('estaciones')
    extra_context = {'titulo': 'Modificar estación', 'volver': 'estaciones'}


class EstacionDeleteView(SoloAdminMixin, DeleteView):
    """Pantalla de confirmación y borrado de una estación."""
    model = Estacion
    template_name = 'panel/confirmar_borrado.html'      # El mismo template de borrado que usan las rutas
    success_url = reverse_lazy('estaciones')
    extra_context = {'volver': 'estaciones'}

class CasillaListView(SoloAdminMixin, ListView):
    """Lista todas las casillas."""
    model = Casilla                                     # Qué modelo listar
    template_name = 'panel/casillas_lista.html'         # Template que se muestra
    context_object_name = 'casillas'                    # Nombre de la lista dentro del template
    # select_related trae la estación y su ruta junto con cada casilla en una sola consulta
    # ('estacion__ruta' sigue dos claves foráneas seguidas: casilla -> estación -> ruta)
    # Ordena por ruta, después por número de estación y al final por número de casilla
    queryset = Casilla.objects.select_related('estacion__ruta').order_by(
        'estacion__ruta__nombre', 'estacion__numero_estacion', 'numero_casilla'
    )


class CasillaCreateView(SoloAdminMixin, BootstrapFormMixin, CreateView):
    """Formulario para crear una casilla nueva."""
    model = Casilla
    # 'estacion' es una clave foránea: Django la dibuja como un desplegable con las estaciones
    fields = ['estacion', 'numero_casilla']
    template_name = 'panel/form_generico.html'          # El mismo template de formulario que usan rutas y estaciones
    success_url = reverse_lazy('casillas')              # A dónde vuelve después de guardar
    # Título que se muestra y nombre de la URL a la que lleva el botón "Volver"
    extra_context = {'titulo': 'Nueva casilla', 'volver': 'casillas'}


class CasillaUpdateView(SoloAdminMixin, BootstrapFormMixin, UpdateView):
    """Formulario para modificar una casilla existente (el pk viene en la URL)."""
    model = Casilla
    fields = ['estacion', 'numero_casilla']
    template_name = 'panel/form_generico.html'
    success_url = reverse_lazy('casillas')
    extra_context = {'titulo': 'Modificar casilla', 'volver': 'casillas'}


class CasillaDeleteView(SoloAdminMixin, DeleteView):
    """Pantalla de confirmación y borrado de una casilla."""
    model = Casilla
    template_name = 'panel/confirmar_borrado.html'      # El mismo template de borrado de las otras entidades
    success_url = reverse_lazy('casillas')
    extra_context = {'volver': 'casillas'}

class EmpleadoListView(SoloAdminMixin, ListView):
    """Lista todos los empleados (operadores y administradores)."""
    model = Operador                                    # Qué modelo listar
    template_name = 'panel/empleados_lista.html'        # Template que se muestra
    context_object_name = 'empleados'                   # Nombre de la lista dentro del template
    # annotate agrega a cada operador un campo "num_turnos" con la cantidad de turnos que tiene
    # ("turnos" es el related_name del modelo Turno); ordena por legajo
    queryset = (
        Operador.objects.annotate(num_turnos=Count("turnos"))
        .prefetch_related(
            Prefetch(
                "turnos",
                queryset=Turno.objects.filter(
                    fecha_hora_apertura__isnull=False,
                    fecha_hora_cierre__isnull=True,
                )
                .select_related("casilla__estacion__ruta")
                .order_by("-fecha_hora_apertura"),
                to_attr="turnos_abiertos",
            )
        )
        .order_by("legajo")
    )


class EmpleadoUpdateView(SoloAdminMixin, BootstrapFormMixin, UpdateView):
    """Formulario para modificar un empleado (el pk es el legajo y viene en la URL)."""
    model = Operador
    # No se incluyen el legajo (es la clave primaria) ni la contraseña (se guarda encriptada)
    fields = ['nombre', 'apellido', 'es_administrador', 'activo']
    template_name = 'panel/form_generico.html'          # El mismo template de formulario que usan las demás pantallas
    success_url = reverse_lazy('empleados')             # A dónde vuelve después de guardar
    extra_context = {'titulo': 'Modificar empleado', 'volver': 'empleados'}

    def form_valid(self, form):
        # Se ejecuta cuando el formulario es válido, justo antes de guardar.
        # Evita que un administrador se bloquee a sí mismo quitándose el rol o desactivándose.
        es_uno_mismo = self.object.pk == self.request.user.pk
        if es_uno_mismo and not (form.cleaned_data['es_administrador'] and form.cleaned_data['activo']):
            # add_error(None, ...) agrega un error general, que form_generico.html muestra arriba del formulario
            form.add_error(None, 'No podés quitarte el rol de administrador ni desactivarte a vos mismo.')
            return self.form_invalid(form)
        return super().form_valid(form)


class EmpleadoToggleActivoView(SoloAdminMixin, View):
    """Activa o desactiva un empleado con un clic (en vez de borrarlo)."""
    # Solo acepta POST: cambiar datos con un simple link (GET) no es seguro
    http_method_names = ['post']

    def post(self, request, pk):
        empleado = get_object_or_404(Operador, pk=pk)   # Busca por legajo; 404 si no existe
        # Un administrador no puede desactivarse a sí mismo
        if empleado.pk != request.user.pk:
            empleado.activo = not empleado.activo       # Invierte el estado actual
            empleado.save(update_fields=['activo'])     # Guarda solo ese campo
        return redirect('empleados')                    # Vuelve a la lista


class EmpleadoCerrarTurnoView(SoloAdminMixin, View):
    """Permite a un administrador cerrar un turno abierto de un empleado."""
    http_method_names = ["post"]

    def post(self, request, pk, turno_id):
        turno = get_object_or_404(
            Turno.objects.select_related("operador"),
            pk=turno_id,
            operador_id=pk,
            fecha_hora_apertura__isnull=False,
            fecha_hora_cierre__isnull=True,
        )
        turno.fecha_hora_cierre = timezone.now()
        turno.save(update_fields=["fecha_hora_cierre"])
        return redirect("empleados")