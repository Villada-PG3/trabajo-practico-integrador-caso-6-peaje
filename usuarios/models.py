# usuario/models.py
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager


class OperadorManager(BaseUserManager):
    def create_user(self, legajo, password=None, **extra_fields):
        if not legajo:
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