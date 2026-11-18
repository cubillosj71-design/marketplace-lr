"""tarifa_servicio, cotizacion y cotizacion_servicio_adicional iguales al modelo relacional (MOD-04).

- tarifa_servicio.administrador_id pasa a NOT NULL. Las filas sin administrador (la tarifa inicial de la
  migración 0002) toman la primera cuenta de administrador; si no hay ninguna se quitan, y la tarifa
  inicial la crea el comando cargar_demo junto con el administrador.
- cotizacion.tarifa_servicio_id NOT NULL: FK a la tarifa vigente que se usó al cotizar. Las cotizaciones
  existentes toman la tarifa vigente en su fecha de creación.
- cotizacion_servicio_adicional: PRIMARY KEY (cotizacion_id, servicio_adicional_id) y precio_aplicado.
  Django no cambia una clave simple por una compuesta, así que la tabla se recrea copiando sus filas.
"""

import django.db.models.deletion
from django.db import migrations, models


def asignar_administrador(apps, schema_editor):
    TarifaServicio = apps.get_model("reservas", "TarifaServicio")
    Usuario = apps.get_model("identidad", "Usuario")
    admin = Usuario.objects.filter(rol="ADMINISTRADOR").order_by("id").first()
    sin_admin = TarifaServicio.objects.filter(administrador__isnull=True)
    if admin:
        sin_admin.update(administrador=admin)
    else:
        sin_admin.delete()


def asignar_tarifa(apps, schema_editor):
    TarifaServicio = apps.get_model("reservas", "TarifaServicio")
    Cotizacion = apps.get_model("reservas", "Cotizacion")
    primera = TarifaServicio.objects.order_by("vigente_desde").first()
    for c in Cotizacion.objects.filter(tarifa_servicio_ref__isnull=True):
        t = TarifaServicio.objects.filter(vigente_desde__lte=c.creada).order_by("-vigente_desde").first() or primera
        Cotizacion.objects.filter(pk=c.pk).update(tarifa_servicio_ref=t)


COPIAR = """
CREATE TEMPORARY TABLE cotizacion_adicional_copia AS
SELECT DISTINCT ON (cotizacion_id, servicio_adicional_id) cotizacion_id, servicio_adicional_id, precio
FROM cotizacion_servicio_adicional ORDER BY cotizacion_id, servicio_adicional_id, id;
"""
RESTAURAR = """
INSERT INTO cotizacion_servicio_adicional (cotizacion_id, servicio_adicional_id, precio_aplicado)
SELECT cotizacion_id, servicio_adicional_id, precio FROM cotizacion_adicional_copia;
DROP TABLE cotizacion_adicional_copia;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("catalogo", "0003_periodo_calendario_a_reservas"),
        ("identidad", "0003_usuario_segun_modelo_relacional"),
        ("reservas", "0003_periodo_calendario"),
    ]

    operations = [
        # tarifa_servicio.administrador_id NOT NULL
        migrations.RunPython(asignar_administrador, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="tarifaservicio", name="administrador",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="identidad.usuario"),
        ),
        # cotizacion.tarifa_servicio_id NOT NULL
        migrations.AddField(
            model_name="cotizacion", name="tarifa_servicio_ref",
            field=models.ForeignKey(
                db_column="tarifa_servicio_id", null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="+", to="reservas.tarifaservicio",
            ),
        ),
        migrations.RunPython(asignar_tarifa, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="cotizacion", name="tarifa_servicio_ref",
            field=models.ForeignKey(
                db_column="tarifa_servicio_id", on_delete=django.db.models.deletion.PROTECT,
                related_name="+", to="reservas.tarifaservicio",
            ),
        ),
        # cotizacion_servicio_adicional con clave primaria compuesta
        migrations.RunSQL(COPIAR, migrations.RunSQL.noop),
        migrations.DeleteModel(name="CotizacionServicioAdicional"),
        migrations.CreateModel(
            name="CotizacionServicioAdicional",
            fields=[
                (
                    "pk",
                    models.CompositePrimaryKey(
                        "cotizacion_id", "servicio_adicional_id", blank=True, editable=False, primary_key=True, serialize=False,
                    ),
                ),
                ("precio_aplicado", models.DecimalField(decimal_places=2, max_digits=12)),
                (
                    "cotizacion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="adicionales", to="reservas.cotizacion",
                    ),
                ),
                (
                    "servicio_adicional",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to="catalogo.servicioadicional",
                    ),
                ),
            ],
            options={"db_table": "cotizacion_servicio_adicional"},
        ),
        migrations.RunSQL(RESTAURAR, migrations.RunSQL.noop),
    ]
