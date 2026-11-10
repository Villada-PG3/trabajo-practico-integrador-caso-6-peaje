import json
from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Casilla,
    CategoriaVehiculo,
    Estacion,
    Operador,
    Ruta,
    SentidoCobro,
    Tarifa,
    Turno,
    Venta,
    VentaModificacion,
)


class DatosInicialesFixtureTests(TestCase):
    def test_loaddata_carga_rutas_estaciones_y_casillas_idempotentemente(self):
        call_command("loaddata", "Data-Fija", verbosity=0)
        call_command("loaddata", "Data-Fija", verbosity=0)

        self.assertEqual(CategoriaVehiculo.objects.count(), 7)
        self.assertEqual(Tarifa.objects.count(), 7)
        self.assertEqual(Ruta.objects.count(), 4)
        self.assertEqual(Estacion.objects.count(), 17)
        self.assertEqual(Casilla.objects.count(), 19)

        ruta = Ruta.objects.get(nombre="Tren de las Sierras")
        self.assertEqual(ruta.ramal, "Ramal A1 (Córdoba)")
        estacion = Estacion.objects.get(ruta=ruta, numero_estacion=6)
        self.assertEqual(estacion.nombre, "Capilla del Monte")
        self.assertEqual(estacion.kilometro, Decimal("154.00"))
        self.assertTrue(
            Casilla.objects.filter(estacion=estacion, numero_casilla=106).exists()
        )


class AperturaTurnoTests(TestCase):
    def setUp(self):
        self.operador = Operador.objects.create(
            legajo=123,
            nombre="Ana",
            apellido="Operadora",
        )
        self.client.force_login(self.operador)

        self.ruta_a = Ruta.objects.create(nombre="Ruta A")
        self.ruta_b = Ruta.objects.create(nombre="Ruta B")
        self.estacion_a = Estacion.objects.create(
            ruta=self.ruta_a,
            nombre="Estación A",
            numero_estacion=1,
            kilometro="10.00",
        )
        self.estacion_b = Estacion.objects.create(
            ruta=self.ruta_b,
            nombre="Estación B",
            numero_estacion=1,
            kilometro="20.00",
        )
        self.casilla_a = Casilla.objects.create(
            estacion=self.estacion_a,
            numero_casilla=1,
        )
        self.casilla_b = Casilla.objects.create(
            estacion=self.estacion_b,
            numero_casilla=1,
        )

    def test_apertura_muestra_rutas_y_casillas_identificadas_por_ruta(self):
        response = self.client.get(reverse("apertura_turno"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{self.ruta_a.id_ruta}"')
        self.assertContains(response, f'value="{self.ruta_b.id_ruta}"')
        self.assertContains(response, f'data-ruta-id="{self.ruta_a.id_ruta}"')
        self.assertContains(response, f'data-ruta-id="{self.ruta_b.id_ruta}"')
        self.assertContains(response, "Estación A")
        self.assertContains(response, "Estación B")

    def test_api_rechaza_casilla_que_no_pertenece_a_la_ruta(self):
        response = self.client.post(
            reverse("api-turno-abrir"),
            data=json.dumps(
                {
                    "ruta_id": self.ruta_a.id_ruta,
                    "casilla_id": self.casilla_b.id_casilla,
                    "sentido": "NS",
                    "monto_cambio_inicial": "5000.00",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Turno.objects.count(), 0)

    def test_api_abre_turno_con_casilla_de_la_ruta_seleccionada(self):
        response = self.client.post(
            reverse("api-turno-abrir"),
            data=json.dumps(
                {
                    "ruta_id": self.ruta_b.id_ruta,
                    "casilla_id": self.casilla_b.id_casilla,
                    "sentido": "NS",
                    "monto_cambio_inicial": "5000.00",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json()["turno"]["casilla_id"],
            self.casilla_b.id_casilla,
        )
        self.assertEqual(Turno.objects.get().casilla, self.casilla_b)


class VentasTurnoTests(TestCase):
    def setUp(self):
        operador = Operador.objects.create(
            legajo=456,
            nombre="Juan",
            apellido="Cajero",
        )
        self.client.force_login(operador)

        ruta = Ruta.objects.create(nombre="Ruta de prueba")
        estacion = Estacion.objects.create(
            ruta=ruta,
            nombre="Estación de prueba",
            numero_estacion=1,
            kilometro="10.00",
        )
        casilla = Casilla.objects.create(estacion=estacion, numero_casilla=1)
        ahora = timezone.now()
        self.turno = Turno.objects.create(
            casilla=casilla,
            operador=operador,
            sentido_cobro=SentidoCobro.NORTE_SUR,
            monto_cambio_inicial="5000.00",
            inicio_programado=ahora,
            fin_programado=ahora + timedelta(hours=8),
            fecha_hora_apertura=ahora,
        )

        hoy = timezone.localdate()
        self.categoria = CategoriaVehiculo.objects.create(nombre="Automóviles")
        self.tarifa = Tarifa.objects.create(
            categoria=self.categoria,
            monto="90.00",
            vigente_desde=hoy,
        )
        self.nueva_categoria = CategoriaVehiculo.objects.create(nombre="Motocicletas")
        self.nueva_tarifa = Tarifa.objects.create(
            categoria=self.nueva_categoria,
            monto="60.00",
            vigente_desde=hoy,
        )

    def test_venta_se_guarda_inmediatamente_con_patente_y_aparece_en_turno(self):
        respuesta_venta = self.client.post(
            reverse("api-ventas"),
            data=json.dumps(
                {"categoria_id": self.categoria.id_categoria, "patente": "aa123cd"}
            ),
            content_type="application/json",
        )

        self.assertEqual(respuesta_venta.status_code, 201)
        venta = Venta.objects.get()
        self.assertEqual(venta.turno, self.turno)
        self.assertEqual(venta.patente_detectada, "AA123CD")

        respuesta_turno = self.client.get(reverse("api-turno-actual"))
        self.assertEqual(respuesta_turno.status_code, 200)
        self.assertEqual(len(respuesta_turno.json()["ventas"]), 1)
        self.assertEqual(respuesta_turno.json()["ventas"][0]["patente"], "AA123CD")

    def test_editar_venta_actualiza_datos_persistidos_y_motivo(self):
        venta = Venta.objects.create(
            turno=self.turno,
            tarifa=self.tarifa,
            importe_cobrado=self.tarifa.monto,
            patente_detectada="AA123CD",
        )

        respuesta = self.client.post(
            reverse("api-venta-editar", args=[venta.numero_ticket]),
            data=json.dumps(
                {
                    "categoria_id": self.nueva_categoria.id_categoria,
                    "patente": "ab456cd",
                    "motivo": "Corrección de patente",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(respuesta.status_code, 200)
        venta.refresh_from_db()
        self.assertEqual(venta.tarifa, self.nueva_tarifa)
        self.assertEqual(venta.importe_cobrado, Decimal("60.00"))
        self.assertEqual(venta.patente_detectada, "AB456CD")
        self.assertEqual(venta.motivo_modificacion, "Corrección de patente")
        self.assertEqual(VentaModificacion.objects.count(), 1)
        modificacion = VentaModificacion.objects.get()
        self.assertEqual(modificacion.operador.legajo, 456)
        self.assertEqual(modificacion.patente_anterior, "AA123CD")
        self.assertEqual(modificacion.patente_nueva, "AB456CD")


class DatosEstacionTicketTests(TestCase):
    def setUp(self):
        operador = Operador.objects.create(
            legajo=457,
            nombre="Lucía",
            apellido="Cajera",
        )
        self.client.force_login(operador)

        ruta = Ruta.objects.get(nombre="Ruta 20")
        estacion = Estacion.objects.create(
            ruta=ruta,
            nombre="Estación Test",
            numero_estacion=7,
            kilometro="59.20",
        )
        casilla = Casilla.objects.create(estacion=estacion, numero_casilla=2)
        ahora = timezone.now()
        self.turno = Turno.objects.create(
            casilla=casilla,
            operador=operador,
            sentido_cobro=SentidoCobro.NORTE_SUR,
            monto_cambio_inicial="5000.00",
            inicio_programado=ahora,
            fin_programado=ahora + timedelta(hours=8),
            fecha_hora_apertura=ahora,
        )
        self.categoria = CategoriaVehiculo.objects.create(nombre="Automóviles")
        Tarifa.objects.create(
            categoria=self.categoria,
            monto="90.00",
            vigente_desde=timezone.localdate(),
        )

    def test_api_ventas_y_turno_actual_incluyen_datos_de_estacion_en_ticket(self):
        respuesta_venta = self.client.post(
            reverse("api-ventas"),
            data=json.dumps({"categoria_id": self.categoria.id_categoria}),
            content_type="application/json",
        )

        self.assertEqual(respuesta_venta.status_code, 201)
        datos_venta = respuesta_venta.json()
        self.assertEqual(datos_venta["estacion_nombre"], "Estación Test")
        self.assertEqual(datos_venta["estacion_numero"], 7)
        self.assertEqual(datos_venta["ruta_nombre"], "Ruta 20")
        self.assertEqual(datos_venta["kilometro"], "59.2")
        self.assertTrue(datos_venta["ticket"].startswith("0007-"))

        respuesta_turno = self.client.get(reverse("api-turno-actual"))

        self.assertEqual(respuesta_turno.status_code, 200)
        datos_turno = respuesta_turno.json()["turno"]
        self.assertEqual(datos_turno["estacion_nombre"], "Estación Test")
        self.assertEqual(datos_turno["estacion_numero"], 7)
        self.assertEqual(datos_turno["ruta_nombre"], "Ruta 20")
        self.assertEqual(datos_turno["kilometro"], "59.2")
        self.assertTrue(
            respuesta_turno.json()["ventas"][0]["ticket"].startswith("0007-")
        )

    def test_paginas_no_muestran_datos_fijos_de_estacion(self):
        respuesta_cobro = self.client.get(reverse("cobro"))
        respuesta_cierre = self.client.get(reverse("cierre_caja"))

        self.assertNotContains(respuesta_cobro, "Km 18")
        self.assertNotContains(respuesta_cobro, "N° 04")
        self.assertNotContains(respuesta_cierre, "Km 18")
        self.assertNotContains(respuesta_cierre, "N° 04")


class EmpleadoTurnoAdminTests(TestCase):
    def setUp(self):
        admin = Operador.objects.create(
            legajo=900,
            nombre="Admin",
            apellido="Sistema",
            es_administrador=True,
        )
        self.operador = Operador.objects.create(
            legajo=901,
            nombre="Operador",
            apellido="Turno",
        )
        self.client.force_login(admin)

        ruta = Ruta.objects.create(nombre="Ruta Admin")
        estacion = Estacion.objects.create(
            ruta=ruta,
            nombre="Estación Admin",
            numero_estacion=1,
            kilometro="5.00",
        )
        casilla = Casilla.objects.create(estacion=estacion, numero_casilla=2)
        ahora = timezone.now()
        self.turno_abierto = Turno.objects.create(
            casilla=casilla,
            operador=self.operador,
            sentido_cobro=SentidoCobro.NORTE_SUR,
            monto_cambio_inicial="1000.00",
            inicio_programado=ahora,
            fin_programado=ahora + timedelta(hours=8),
            fecha_hora_apertura=ahora,
        )

    def test_administrador_ve_turno_abierto_del_operador(self):
        respuesta = self.client.get(reverse("empleados"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ruta Admin")
        self.assertContains(respuesta, "Cerrar turno")
        self.assertContains(respuesta, reverse(
            "empleado_cerrar_turno",
            args=[self.operador.legajo, self.turno_abierto.id_turno],
        ))

    def test_administrador_puede_cerrar_turno_de_empleado(self):
        respuesta = self.client.post(
            reverse(
                "empleado_cerrar_turno",
                args=[self.operador.legajo, self.turno_abierto.id_turno],
            )
        )

        self.assertRedirects(respuesta, reverse("empleados"))
        self.turno_abierto.refresh_from_db()
        self.assertIsNotNone(self.turno_abierto.fecha_hora_cierre)

    def test_no_se_puede_cerrar_turno_de_otro_operador(self):
        otro_operador = Operador.objects.create(
            legajo=902,
            nombre="Otro",
            apellido="Operador",
        )
        ruta = Ruta.objects.create(nombre="Otra ruta")
        estacion = Estacion.objects.create(
            ruta=ruta,
            nombre="Otra estación",
            numero_estacion=1,
            kilometro="6.00",
        )
        otra_casilla = Casilla.objects.create(estacion=estacion, numero_casilla=1)
        ahora = timezone.now()
        otro_turno = Turno.objects.create(
            casilla=otra_casilla,
            operador=otro_operador,
            sentido_cobro=SentidoCobro.NORTE_SUR,
            monto_cambio_inicial="1000.00",
            inicio_programado=ahora,
            fin_programado=ahora + timedelta(hours=8),
            fecha_hora_apertura=ahora,
        )

        respuesta = self.client.post(
            reverse(
                "empleado_cerrar_turno",
                args=[self.operador.legajo, otro_turno.id_turno],
            )
        )

        self.assertEqual(respuesta.status_code, 404)
        otro_turno.refresh_from_db()
        self.assertIsNone(otro_turno.fecha_hora_cierre)


class EstadisticasTests(TestCase):
    def setUp(self):
        self.admin = Operador.objects.create(
            legajo=950,
            nombre="Admin",
            apellido="Estadísticas",
            es_administrador=True,
        )
        self.empleado = Operador.objects.create(
            legajo=951,
            nombre="Eva",
            apellido="Operadora",
        )
        self.client.force_login(self.admin)

        self.ruta = Ruta.objects.create(nombre="Ruta Estadísticas")
        estacion = Estacion.objects.create(
            ruta=self.ruta,
            nombre="Estación Estadísticas",
            numero_estacion=1,
            kilometro="12.00",
        )
        self.casilla = Casilla.objects.create(estacion=estacion, numero_casilla=3)
        ahora = timezone.now()
        self.turno = Turno.objects.create(
            casilla=self.casilla,
            operador=self.empleado,
            sentido_cobro=SentidoCobro.NORTE_SUR,
            monto_cambio_inicial="1000.00",
            inicio_programado=ahora,
            fin_programado=ahora + timedelta(hours=8),
            fecha_hora_apertura=ahora,
        )

        hoy = timezone.localdate()
        self.categoria = CategoriaVehiculo.objects.create(nombre="Autos")
        self.tarifa = Tarifa.objects.create(
            categoria=self.categoria,
            monto="100.00",
            vigente_desde=hoy,
        )
        self.venta = Venta.objects.create(
            turno=self.turno,
            tarifa=self.tarifa,
            importe_cobrado=self.tarifa.monto,
            patente_detectada="AA123BB",
            motivo_modificacion="Se corrigió la patente",
        )
        Venta.objects.create(
            turno=self.turno,
            tarifa=self.tarifa,
            importe_cobrado=self.tarifa.monto,
        )

    def test_estadisticas_casilla_incluyen_ventas_categorias_y_horario(self):
        respuesta = self.client.get(
            reverse("api-estadisticas-casilla"),
            {"ruta_id": self.ruta.id_ruta, "casilla_id": self.casilla.id_casilla},
        )

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual(datos["total_ventas"], 2)
        self.assertEqual(datos["categorias"], [{"nombre": "Autos", "cantidad": 2, "porcentaje": 100.0}])
        self.assertEqual(sum(datos["ventas_por_hora"]), 2)
        self.assertIsNotNone(datos["hora_pico"])

    def test_estadisticas_empleado_muestran_turnos_ventas_y_correcciones(self):
        self.client.force_login(self.empleado)
        for patente, motivo in (
            ("AB123CD", "Corrección inicial"),
            ("AC123CD", "Segunda corrección"),
        ):
            self.client.post(
                reverse("api-venta-editar", args=[self.venta.numero_ticket]),
                data=json.dumps(
                    {
                        "categoria_id": self.categoria.id_categoria,
                        "patente": patente,
                        "motivo": motivo,
                    }
                ),
                content_type="application/json",
            )

        self.client.force_login(self.admin)
        respuesta = self.client.get(
            reverse("api-estadisticas-empleado"),
            {"legajo": self.empleado.legajo},
        )

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual(datos["total_ventas"], 2)
        self.assertEqual(datos["total_turnos"], 1)
        self.assertEqual(datos["casillas"][0]["turnos"], 1)
        self.assertEqual(datos["casillas"][0]["ventas"], 2)
        self.assertEqual(datos["total_correcciones"], 2)
        self.assertEqual(
            {item["motivo"] for item in datos["correcciones"]},
            {"Corrección inicial", "Segunda corrección"},
        )
        self.assertEqual(
            datos["correcciones"][0]["ticket"],
            f"{self.casilla.estacion.numero_estacion:04d}-{self.venta.pk:06d}",
        )

    def test_estadisticas_requieren_permisos_de_administrador(self):
        self.client.force_login(self.empleado)

        respuesta_pagina = self.client.get(reverse("estadisticas"))
        respuesta_api = self.client.get(
            reverse("api-estadisticas-empleado"),
            {"legajo": self.empleado.legajo},
        )

        self.assertEqual(respuesta_pagina.status_code, 403)
        self.assertEqual(respuesta_api.status_code, 403)


class TarifasAdminTests(TestCase):
    def setUp(self):
        admin = Operador.objects.create(
            legajo=980,
            nombre="Admin",
            apellido="Tarifas",
            es_administrador=True,
        )
        self.client.force_login(admin)
        self.categoria = CategoriaVehiculo.objects.create(nombre="Automóviles")
        self.tarifa_anterior = Tarifa.objects.create(
            categoria=self.categoria,
            monto="90.00",
            vigente_desde=timezone.localdate() - timedelta(days=30),
        )
        for numero, nombre in (
            (2, "Autos"),
            (3, "Dos ejes"),
            (4, "Tres o cuatro ejes"),
            (5, "Tres o cuatro ejes duales"),
            (6, "Cinco o seis ejes"),
            (7, "Más de seis ejes"),
        ):
            CategoriaVehiculo.objects.create(
                id_categoria=numero,
                nombre=nombre,
            )

    def test_pagina_tarifas_muestra_precios_y_logos_de_vehiculos(self):
        respuesta = self.client.get(reverse("tarifas"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Automóviles")
        self.assertContains(respuesta, "$90.00")
        self.assertContains(respuesta, "Downloads.Moto.png")
        self.assertContains(respuesta, "autp.png")
        self.assertContains(respuesta, "Ejes2.png")
        self.assertContains(respuesta, "ejes3o4.png")
        self.assertContains(respuesta, "ejes3o4-2.png")
        self.assertContains(respuesta, "ejes5o6.png")
        self.assertContains(respuesta, "%2B6.png")

    def test_actualizar_tarifa_crea_nueva_vigencia_y_conserva_la_anterior(self):
        respuesta = self.client.post(
            reverse("tarifa_actualizar", args=[self.categoria.id_categoria]),
            {"monto": "125.50"},
        )

        hoy = timezone.localdate()
        self.assertRedirects(respuesta, reverse("tarifas"))
        self.tarifa_anterior.refresh_from_db()
        self.assertEqual(self.tarifa_anterior.vigente_hasta, hoy - timedelta(days=1))
        tarifa_nueva = Tarifa.objects.get(categoria=self.categoria, vigente_desde=hoy)
        self.assertEqual(tarifa_nueva.monto, Decimal("125.50"))

    def test_actualizar_tarifa_iniciada_hoy_no_crea_otra_vigencia(self):
        hoy = timezone.localdate()
        self.tarifa_anterior.vigente_hasta = hoy - timedelta(days=1)
        self.tarifa_anterior.save(update_fields=["vigente_hasta"])
        tarifa_hoy = Tarifa.objects.create(
            categoria=self.categoria,
            monto="100.00",
            vigente_desde=hoy,
        )

        respuesta = self.client.post(
            reverse("tarifa_actualizar", args=[self.categoria.id_categoria]),
            {"monto": "110.00"},
        )

        self.assertRedirects(respuesta, reverse("tarifas"))
        tarifa_hoy.refresh_from_db()
        self.assertEqual(tarifa_hoy.monto, Decimal("110.00"))
        self.assertEqual(
            Tarifa.objects.filter(categoria=self.categoria, vigente_desde=hoy).count(),
            1,
        )

    def test_operador_no_puede_acceder_ni_modificar_tarifas(self):
        operador = Operador.objects.create(
            legajo=981,
            nombre="Operador",
            apellido="Común",
        )
        self.client.force_login(operador)

        respuesta_pagina = self.client.get(reverse("tarifas"))
        respuesta_cambio = self.client.post(
            reverse("tarifa_actualizar", args=[self.categoria.id_categoria]),
            {"monto": "200.00"},
        )

        self.assertEqual(respuesta_pagina.status_code, 403)
        self.assertEqual(respuesta_cambio.status_code, 403)
        self.assertFalse(
            Tarifa.objects.filter(
                categoria=self.categoria,
                vigente_desde=timezone.localdate(),
            ).exists()
        )

    def test_tarifa_rechaza_precio_invalido(self):
        respuesta = self.client.post(
            reverse("tarifa_actualizar", args=[self.categoria.id_categoria]),
            {"monto": "-5"},
        )

        self.assertRedirects(respuesta, reverse("tarifas"))
        self.assertFalse(
            Tarifa.objects.filter(
                categoria=self.categoria,
                vigente_desde=timezone.localdate(),
            ).exists()
        )
