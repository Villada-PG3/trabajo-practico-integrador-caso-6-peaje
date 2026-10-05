from django.db import migrations


def crear_datos_iniciales(apps, schema_editor):
    """
    Crea la ruta, la estación y las 3 casillas que usa la pantalla de
    apertura de turno. Sin estas filas no se puede crear ningún Turno,
    porque Turno.casilla es una clave foránea obligatoria.
    Es idempotente: si ya existen, no las duplica.
    """
    Ruta = apps.get_model("core", "Ruta")
    Estacion = apps.get_model("core", "Estacion")
    Casilla = apps.get_model("core", "Casilla")

    ruta, _ = Ruta.objects.get_or_create(nombre="Ruta 20")
    estacion, _ = Estacion.objects.get_or_create(
        ruta=ruta,
        numero_estacion=4,
        defaults={"nombre": "Estación Ruta 20 Km 18", "kilometro": "18.00"},
    )
    for numero in (1, 2, 3):
        Casilla.objects.get_or_create(estacion=estacion, numero_casilla=numero)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(crear_datos_iniciales, migrations.RunPython.noop),
    ]