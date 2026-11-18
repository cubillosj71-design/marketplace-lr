"""Tarifa de servicio inicial del 10 % (ejemplos del SRS, CA-12.1).

tarifa_servicio.administrador_id es NOT NULL (migración 0004): la tarifa la fija un administrador. Si al
migrar todavía no hay ninguno (base nueva), no se crea aquí; la crea `cargar_demo` junto con el
administrador, o el administrador desde PUT /admin/tarifa-servicio.
"""

from decimal import Decimal

from django.db import migrations
from django.utils import timezone


def cargar(apps, schema_editor):
    TarifaServicio = apps.get_model("reservas", "TarifaServicio")
    admin = apps.get_model("identidad", "Usuario").objects.filter(rol="ADMINISTRADOR").order_by("id").first()
    if admin and not TarifaServicio.objects.exists():
        TarifaServicio.objects.create(
            administrador=admin, porcentaje=Decimal("10"),
            vigente_desde=timezone.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0),
        )


class Migration(migrations.Migration):
    dependencies = [("reservas", "0001_initial"), ("identidad", "0001_initial")]
    operations = [migrations.RunPython(cargar, migrations.RunPython.noop)]
