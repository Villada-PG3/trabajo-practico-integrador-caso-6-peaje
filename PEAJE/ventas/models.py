from django.db import models

# Create your models here.
from turnos.models import Turno  # ajustá el import al nombre real de la app de Back 1

class CategoriaVehiculo(models.Model):
    id_categoria = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=80)

    def __str__(self):
        return self.nombre


class Tarifa(models.Model):
    id_tarifa = models.AutoField(primary_key=True)
    categoria = models.ForeignKey(CategoriaVehiculo, on_delete=models.PROTECT, related_name='tarifas')
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)  # null = sigue vigente

    def __str__(self):
        return f"{self.categoria} - ${self.monto} ({self.vigente_desde})"


class Venta(models.Model):
    numero_ticket = models.AutoField(primary_key=True)
    turno = models.ForeignKey(Turno, on_delete=models.PROTECT, related_name='ventas')
    tarifa = models.ForeignKey(Tarifa, on_delete=models.PROTECT, related_name='ventas')
    fecha_hora_emision = models.DateTimeField(auto_now_add=True)
    importe_cobrado = models.DecimalField(max_digits=10, decimal_places=2)
    patente_detectada = models.CharField(max_length=15, null=True, blank=True)

    def __str__(self):
        return f"Ticket #{self.numero_ticket}"