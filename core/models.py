# Create your models here.
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager #Te permite crear un modelo de usuario personalizado
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
 
class OperadorManager(BaseUserManager):
    def create_user(self, legajo, password=None, **extra_fields):
        if legajo is None:
            raise ValueError("El operador debe tener un legajo")
        operador = self.model(legajo=legajo, **extra_fields)
        operador.set_password(password)
        operador.save(using=self._db)
        return operador

    def create_superuser(self, legajo, password=None, **extra_fields):
        extra_fields.setdefault("es_administrador", True)
        extra_fields.setdefault("activo", True)
        return self.create_user(legajo=legajo, password=password, **extra_fields)
 
class Operador(AbstractBaseUser):
    legajo = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    es_administrador = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)
    objects = OperadorManager()

    USERNAME_FIELD = "legajo"
    REQUIRED_FIELDS = ["nombre", "apellido"]

    def has_perm(self, perm, obj=None):
        return self.es_administrador

    def has_module_perms(self, app_label):
        return self.es_administrador
 
 
    class Meta:
        db_table = "operador"
 
    def __str__(self):
        return f"{self.legajo} - {self.nombre} {self.apellido}"
 
    @property
    def is_active(self):
        return self.activo
 
    @property
    def is_staff(self):
        return self.es_administrador
 

class SentidoCobro(models.TextChoices):
    NORTE_SUR = "NS", "Norte-Sur"
    SUR_NORTE = "SN", "Sur-Norte"
    ESTE_OESTE = "EO", "Este-Oeste"
    OESTE_ESTE = "OE", "Oeste-Este"
 
 
class Turno(models.Model):
    id_turno = models.AutoField(primary_key=True)
    # PROTECT: un turno es historial; no debe desaparecer al borrar casilla/operador.
    casilla = models.ForeignKey(
        Casilla,
        on_delete=models.PROTECT,
        related_name="turnos",
        db_column="id_casilla",
    )
    operador = models.ForeignKey(
        Operador,
        on_delete=models.PROTECT,
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
 
 
class CategoriaVehiculo(models.Model):
    id_categoria = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=80)
 
    class Meta:
        db_table = "categoria_vehiculo"
 
    def __str__(self):
        return self.nombre
 
 
class Tarifa(models.Model):
    id_tarifa = models.AutoField(primary_key=True)
    categoria = models.ForeignKey(
        CategoriaVehiculo, on_delete=models.PROTECT, related_name="tarifas"
    )
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)
 
    class Meta:
        db_table = "tarifa"

    def __str__(self):
        return f"{self.categoria} - ${self.monto} ({self.vigente_desde})"
 
 
class Venta(models.Model):
    numero_ticket = models.AutoField(primary_key=True)
    turno = models.ForeignKey(Turno, on_delete=models.PROTECT, related_name="ventas")
    tarifa = models.ForeignKey(Tarifa, on_delete=models.PROTECT, related_name="ventas")
    fecha_hora_emision = models.DateTimeField(auto_now_add=True)
    importe_cobrado = models.DecimalField(max_digits=10, decimal_places=2)
    patente_detectada = models.CharField(max_length=15, null=True, blank=True)
 
    class Meta:
        db_table = "venta"
 
    def __str__(self):
        return f"Ticket #{self.numero_ticket}"