from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login
from rest_framework.decorators import api_view
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


# Decorador que exime a esta función de validar el token CSRF (necesario cuando se reciben peticiones desde un cliente API como fetch)
@csrf_exempt
def api_login_view(request): # Define la función de la vista para manejar el inicio de sesión, recibiendo la petición HTTP en la variable 'request'

    # Verifica si el método de la petición NO es POST (ej. si intentan entrar usando GET desde el navegador)
    if request.method != "POST":
        # Retorna un error en formato JSON indicando que el método no está permitido con el código de estado HTTP 405
        return JsonResponse({"detail": "Método no permitido"}, status=405)

    # Inicia un bloque try-except para capturar posibles errores al procesar el texto que envía el cliente
    try:
        # Lee el cuerpo bruto de la petición ('request.body') y lo convierte de texto JSON a un diccionario de Python
        data = json.loads(request.body)
    # Si el texto enviado por el frontend no es un JSON válido o está mal formado
    except json.JSONDecodeError:
        # Retorna un error indicando "JSON inválido" junto con el código de estado HTTP 400 (Bad Request)
        return JsonResponse({"detail": "JSON inválido"}, status=400)

    # Llama a la función de autenticación de Django pasando los datos recibidos del frontend
    operador = authenticate(
        request,
        # Obtiene el valor del campo "legajo" del JSON y lo usa como el nombre de usuario (username)
        username=data.get("legajo"),
        # Obtiene el valor del campo "password" del JSON para validarlo
        password=data.get("password"),
    )

    # Si las credenciales son incorrectas o el usuario no existe, 'authenticate' devuelve 'None'
    if operador is None:
        # Retorna un mensaje indicando "Credenciales inválidas" con el código de estado HTTP 401 (No autorizado)
        return JsonResponse({"detail": "Credenciales inválidas"}, status=401)

    # Si la autenticación fue exitosa, retorna una respuesta JSON con el código de estado 200 (OK por defecto)
    return JsonResponse(
        {
            # Envía el legajo del operador autenticado
            "legajo": operador.legajo,
            # Envía un valor booleano (true/false) indicando si el operador es administrador
            "es_administrador": operador.es_administrador,
        }
    )

def login_view(request):
    """Vista del formulario de inicio de sesión por legajo."""
    return render(request, 'login.html')

def apertura_turno_view(request):
    """Vista para abrir caja/turno (monto inicial y sentido de cobro)."""
    return render(request, 'apertura_turno.html')

def cobro_view(request):
    """Vista principal de cobro de peaje (Categorías, OCR Webcam y Ticket)."""
    return render(request, 'cobro.html')

def cierre_caja_view(request):
    """Vista para resumen de cierre de turno e informe de caja."""
    return render(request, 'cierre_caja.html')

def prueba(request):
    """Vista de prueba para desarrollo y testing."""
    return render(request, 'prueba.html')