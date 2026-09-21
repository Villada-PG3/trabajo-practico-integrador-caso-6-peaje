from django.shortcuts import render

# Create your views here.


# Vistas de renderizado para el FRONT 1 (Panel Empleado)

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