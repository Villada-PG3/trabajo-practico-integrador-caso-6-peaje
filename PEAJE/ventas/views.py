from django.shortcuts import render
from rest_framework.generics import ListAPIView
from .models import CategoriaVehiculo
from .serializers import CategoriaVehiculoSerializer

class CategoriaVehiculoListView(ListAPIView):
    queryset = CategoriaVehiculo.objects.all()
    serializer_class = CategoriaVehiculoSerializer