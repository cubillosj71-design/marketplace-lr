"""RF-D-ADM-03.1: la tarifa de servicio rige en un rango [vigente_desde, vigente_hasta).

Se agrega vigente_hasta (NULL = vigente hoy), se llena en las tarifas que ya existen (cada una termina donde empieza
la siguiente; la más reciente queda abierta) y luego se agregan el CHECK y el índice único de "una sola abierta".
"""

from datetime import timedelta

from django.db import migrations, models


def llenar_vigente_hasta(apps, schema_editor):
    TarifaServicio = apps.get_model("reservas", "TarifaServicio")
    tarifas = list(TarifaServicio.objects.order_by("vigente_desde", "id"))
    for actual, siguiente in zip(tarifas, tarifas[1:]):
        # Dos tarifas con el mismo inicio: la primera no llegó a regir; se cierra un microsegundo después para
        # cumplir el CHECK vigente_hasta > vigente_desde.
        actual.vigente_hasta = max(siguiente.vigente_desde, actual.vigente_desde + timedelta(microseconds=1))
        actual.save(update_fields=["vigente_hasta"])


def vaciar_vigente_hasta(apps, schema_editor):
    apps.get_model("reservas", "TarifaServicio").objects.update(vigente_hasta=None)


class Migration(migrations.Migration):
    dependencies = [("reservas", "0007_v_reserva_reporte_y_v_demanda")]

    operations = [
        migrations.AddField(
            model_name="tarifaservicio", name="vigente_hasta", field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(llenar_vigente_hasta, vaciar_vigente_hasta),
        migrations.AddConstraint(
            model_name="tarifaservicio",
            constraint=models.CheckConstraint(
                condition=models.Q(("vigente_hasta__isnull", True), ("vigente_hasta__gt", models.F("vigente_desde")), _connector="OR"),
                name="tarifa_hasta_mayor_que_desde",
            ),
        ),
        migrations.AddConstraint(
            model_name="tarifaservicio",
            constraint=models.UniqueConstraint(
                condition=models.Q(("vigente_hasta__isnull", True)), fields=("vigente_hasta",), nulls_distinct=False,
                name="tarifa_una_sola_vigente",
            ),
        ),
    ]
