from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login

def login_view(request):
    error = None

    if request.method == 'POST':
        legajo = request.POST.get('legajo')
        password = request.POST.get('password')

        # authenticate() busca en el modelo Operador por el campo "legajo"
        # (porque en settings.py definimos USERNAME_FIELD = "legajo" en el modelo)
        operador = authenticate(request, legajo=legajo, password=password)

        if operador is not None:
            auth_login(request, operador)
            return redirect('inicio')
        else:
            error = "Legajo o contraseña incorrectos."

    context = {'error': error}
    return render(request, 'core/login.html', context)


def inicio(request):
    # Placeholder temporal: cuando Bossiii y el resto tengan sus páginas,
    # esto va a redirigir según operador.es_administrador
    return render(request, 'core/inicio.html')
# Create your views here.
