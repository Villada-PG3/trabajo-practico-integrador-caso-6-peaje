import json
import re
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie

from .models import (
    CategoriaVehiculo,
    Casilla,
    Operador,
    SentidoCobro,
    Tarifa,
    Turno,
    Venta,
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
    casillas = Casilla.objects.select_related("estacion").order_by("numero_casilla")
    return render(
        request,
        "apertura_turno.html",
        {"casillas": casillas, "sentidos": SentidoCobro.choices},
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
        Turno.objects.select_related("casilla__estacion", "operador")
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
    return f"0004-{venta.numero_ticket:06d}"


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
        casilla = Casilla.objects.select_related("estacion").get(pk=int(data.get("casilla_id")))
    except (TypeError, ValueError, Casilla.DoesNotExist):
        return JsonResponse({"detail": "Casilla inválida"}, status=400)

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
    return JsonResponse({"turno": _turno_a_dict(turno), "resumen": _resumen_turno(turno)})


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
        },
        status=201,
    )


def api_logout_view(request):
    """Cierra la sesión del operador."""
    if request.method != "POST":
        return JsonResponse({"detail": "Método no permitido"}, status=405)
    auth_logout(request)
    return JsonResponse({"detail": "Sesión cerrada"})