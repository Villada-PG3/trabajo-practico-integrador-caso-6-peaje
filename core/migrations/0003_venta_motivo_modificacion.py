from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_datos_iniciales"),
    ]

    operations = [
        migrations.AddField(
            model_name="venta",
            name="motivo_modificacion",
            field=models.TextField(blank=True),
        ),
    ]
