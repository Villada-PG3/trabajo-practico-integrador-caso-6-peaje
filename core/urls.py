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

    # --- API de turnos y ventas ---
    path('api/turnos/abrir/', views.api_turno_abrir, name='api-turno-abrir'),
    path('api/turnos/actual/', views.api_turno_actual, name='api-turno-actual'),
    path('api/turnos/cerrar/', views.api_turno_cerrar, name='api-turno-cerrar'),
    path('api/tarifas/', views.api_tarifas, name='api-tarifas'),
    path('api/ventas/', views.api_ventas, name='api-ventas'),
    path('api/logout/', views.api_logout_view, name='api-logout'),

    # Lista de rutas
    path('panel/rutas/', views.RutaListView.as_view(), name='rutas'),
    # Formulario de alta
    path('panel/rutas/nueva/', views.RutaCreateView.as_view(), name='ruta_crear'),
    # <int:pk> captura el número de la ruta que se quiere modificar
    path('panel/rutas/<int:pk>/editar/', views.RutaUpdateView.as_view(), name='ruta_editar'),
    # Lo mismo para borrar
    path('panel/rutas/<int:pk>/borrar/', views.RutaDeleteView.as_view(), name='ruta_borrar'),

        # Lista de estaciones
    path('panel/estaciones/', views.EstacionListView.as_view(), name='estaciones'),
    # Formulario de alta
    path('panel/estaciones/nueva/', views.EstacionCreateView.as_view(), name='estacion_crear'),
    # <int:pk> captura el número de la estación que se quiere modificar
    path('panel/estaciones/<int:pk>/editar/', views.EstacionUpdateView.as_view(), name='estacion_editar'),
    # Lo mismo para borrar
    path('panel/estaciones/<int:pk>/borrar/', views.EstacionDeleteView.as_view(), name='estacion_borrar'),

        # Lista de casillas
    path('panel/casillas/', views.CasillaListView.as_view(), name='casillas'),
    # Formulario de alta
    path('panel/casillas/nueva/', views.CasillaCreateView.as_view(), name='casilla_crear'),
    # <int:pk> captura el número de la casilla que se quiere modificar
    path('panel/casillas/<int:pk>/editar/', views.CasillaUpdateView.as_view(), name='casilla_editar'),
    # Lo mismo para borrar
    path('panel/casillas/<int:pk>/borrar/', views.CasillaDeleteView.as_view(), name='casilla_borrar'),
]