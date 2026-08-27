from django.db import models
from core.models import Casilla
from usuarios.models import Operador


class SentidoCobro(models.TextChoices):
    NORTE_SUR = "NS", "Norte-Sur"
    SUR_NORTE = "SN", "Sur-Norte"
    ESTE_OESTE = "EO", "Este-Oeste"
    OESTE_ESTE = "OE", "Oeste-Este"


class Turno(models.Model):
    id_turno = models.AutoField(primary_key=True)
    casilla = models.ForeignKey(
        Casilla,
        on_delete=models.CASCADE,
        related_name="turnos",
        db_column="id_casilla",
    )
    operador = models.ForeignKey(
        Operador,
        on_delete=models.CASCADE,
        related_name="turnos",
        db_column="legajo_operador",
        to_field="legajo",
    )
    sentido_cobro = models.CharField(max_length=2, choices=SentidoCobro.choices)

    monto_cambio_inicial = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    inicio_programado = models.DateTimeField()
    fin_programado = models.DateTimeField()
    fecha_hora_apertura = models.DateTimeField(null=True, blank=True)
    fecha_hora_cierre = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "turno"

    def __str__(self):
        return f"Turno {self.id_turno} - {self.operador} - {self.casilla}"

