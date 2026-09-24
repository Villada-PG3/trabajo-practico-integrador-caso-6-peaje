from django.urls import path
from . import views

urlpatterns = [

    path('apertura-turno/', views.apertura_turno_view, name='apertura_turno'),

    path('cobro/', views.cobro_view, name='cobro'),

    path('cierre-caja/', views.cierre_caja_view, name='cierre_caja'),

    path('prueba/', views.prueba, name='prueba'),

    # Muestra login.html
    path('login/', views.login_view, name='login'),

    # Procesa usuario y contraseña
    path('api/login/', views.api_login_view, name='api-login'),

]