from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('inicio/', views.inicio, name='inicio'),
    path('apertura-turno/', views.apertura_turno_view, name='apertura_turno'),
    path('cobro/', views.cobro_view, name='cobro'),
    path('cierre-caja/', views.cierre_caja_view, name='cierre_caja'),
]