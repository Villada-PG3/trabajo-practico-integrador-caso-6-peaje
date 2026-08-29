from rest_framework import serializers
from .models import CategoriaVehiculo

class CategoriaVehiculoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriaVehiculo
        fields = ['id_categoria', 'nombre']