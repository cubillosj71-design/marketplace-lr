"""Tarifa de servicio inicial del 10 % (ejemplos del SRS, CA-12.1)."""

from decimal import Decimal

from django.db import migrations
from django.utils import timezone


def cargar(apps, schema_editor):
    TarifaServicio = apps.get_model("reservas", "TarifaServicio")
    if not TarifaServicio.objects.exists():
        TarifaServicio.objects.create(porcentaje=Decimal("10"), vigente_desde=timezone.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0))


class Migration(migrations.Migration):
    dependencies = [("reservas", "0001_initial")]
    operations = [migrations.RunPython(cargar, migrations.RunPython.noop)]
