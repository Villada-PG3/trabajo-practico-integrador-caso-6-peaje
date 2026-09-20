# Register your models here.
from django.contrib import admin
from .models import CategoriaVehiculo, Tarifa, Venta

admin.site.register(CategoriaVehiculo)
admin.site.register(Tarifa)
admin.site.register(Venta)