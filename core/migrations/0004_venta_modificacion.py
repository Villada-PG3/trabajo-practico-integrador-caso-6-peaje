from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def migrar_correcciones_existentes(apps, schema_editor):
    Venta = apps.get_model("core", "Venta")
    VentaModificacion = apps.get_model("core", "VentaModificacion")

    ventas = (
        Venta.objects.exclude(motivo_modificacion="")
        .select_related("turno", "tarifa__categoria")
        .iterator()
    )
    for venta in ventas:
        VentaModificacion.objects.create(
            venta_id=venta.pk,
            operador_id=venta.turno.operador_id,
            fecha_hora=venta.fecha_hora_emision,
            categoria_anterior=venta.tarifa.categoria.nombre,
            categoria_nueva=venta.tarifa.categoria.nombre,
            patente_anterior=venta.patente_detectada or "",
            patente_nueva=venta.patente_detectada or "",
            motivo=venta.motivo_modificacion,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_venta_motivo_modificacion"),
    ]

    operations = [
        migrations.CreateModel(
            name="VentaModificacion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("fecha_hora", models.DateTimeField(default=django.utils.timezone.now)),
                ("categoria_anterior", models.CharField(max_length=80)),
                ("categoria_nueva", models.CharField(max_length=80)),
                ("patente_anterior", models.CharField(blank=True, max_length=15)),
                ("patente_nueva", models.CharField(blank=True, max_length=15)),
                ("motivo", models.TextField()),
                (
                    "operador",
                    models.ForeignKey(
                        db_column="legajo_operador",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="modificaciones_ventas",
                        to="core.operador",
                    ),
                ),
                (
                    "venta",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="modificaciones",
                        to="core.venta",
                    ),
                ),
            ],
            options={
                "db_table": "venta_modificacion",
                "ordering": ["-fecha_hora", "-id"],
            },
        ),
        migrations.RunPython(
            migrar_correcciones_existentes,
            migrations.RunPython.noop,
        ),
    ]
