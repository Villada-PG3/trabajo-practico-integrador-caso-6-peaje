from django.contrib import admin

# Register your models here.
# ventas/admin.py
from .models import CategoriaVehiculo, Tarifa, Venta

admin.site.register(CategoriaVehiculo)
admin.site.register(Tarifa)
admin.site.register(Venta)