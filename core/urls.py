from django.urls import path
from . import views
from django.views.generic import RedirectView

urlpatterns = [

    path('apertura-turno/', views.apertura_turno_view, name='apertura_turno'),

    path('cobro/', views.cobro_view, name='cobro'),

    path('cierre-caja/', views.cierre_caja_view, name='cierre_caja'),

    path('prueba/', views.prueba, name='prueba'),

    # Muestra login.html
    path('login/', views.login_view, name='login'),

    # Procesa usuario y contraseña
    path('api/login/', views.api_login_view, name='api-login'),

    # Si alguien entra a la raíz del sitio, lo mandamos a la ruta llamada 'login'
    path('', RedirectView.as_view(pattern_name='login'), name='raiz'),

    #procesa el panel de crear usuario
    path('panel/crear-usuario/', views.crear_usuario, name='crear_usuario'),

    #procesa la creación de un nuevo usuario (operador) vía API
    path('api/operadores/', views.api_operadores_view, name='api-operadores'),
]