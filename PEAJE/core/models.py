from django.db import models


class Ruta(models.Model):
    id_ruta = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = "ruta"

    def __str__(self):
        return self.nombre


class Estacion(models.Model):
    id_estacion = models.AutoField(primary_key=True)
    ruta = models.ForeignKey(
        Ruta,
        on_delete=models.CASCADE,
        related_name="estaciones",
        db_column="id_ruta",
    )
    nombre = models.CharField(max_length=100)
    numero_estacion = models.IntegerField()
    kilometro = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        db_table = "estacion"
        unique_together = ("ruta", "numero_estacion")

    def __str__(self):
        return f"{self.nombre} (Ruta {self.ruta.nombre})"


class Casilla(models.Model):
    id_casilla = models.AutoField(primary_key=True)
    estacion = models.ForeignKey(
        Estacion,
        on_delete=models.CASCADE,
        related_name="casillas",
        db_column="id_estacion",
    )
    numero_casilla = models.IntegerField()

    class Meta:
        db_table = "casilla"
        unique_together = ("estacion", "numero_casilla")

    def __str__(self):
        return f"Casilla {self.numero_casilla} - {self.estacion.nombre}"

