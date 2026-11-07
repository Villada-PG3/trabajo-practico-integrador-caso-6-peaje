import json

from django.test import TestCase
from django.urls import reverse

from .models import Casilla, Estacion, Operador, Ruta, Turno


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
