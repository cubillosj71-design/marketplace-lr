"""periodo_calendario es de MOD-04 Reservas (diagrama de clases y modelo relacional).

1. Reservas toma la tabla que creó catalogo.0001 (solo cambia el estado, se conservan las filas).
2. tipo VARCHAR(15) pasa a disponible BOOLEAN: NO_DISPONIBLE -> false, DISPONIBLE -> true.
   Se mantiene CHECK fecha_fin > fecha_inicio.
"""

import django.db.models.deletion
from django.db import migrations, models


def tipo_a_disponible(apps, schema_editor):
    PeriodoCalendario = apps.get_model("reservas", "PeriodoCalendario")
    PeriodoCalendario.objects.filter(tipo="DISPONIBLE").update(disponible=True)
    PeriodoCalendario.objects.filter(tipo="NO_DISPONIBLE").update(disponible=False)


def disponible_a_tipo(apps, schema_editor):
    PeriodoCalendario = apps.get_model("reservas", "PeriodoCalendario")
    PeriodoCalendario.objects.filter(disponible=True).update(tipo="DISPONIBLE")
    PeriodoCalendario.objects.filter(disponible=False).update(tipo="NO_DISPONIBLE")


class Migration(migrations.Migration):
    dependencies = [
        ("catalogo", "0003_periodo_calendario_a_reservas"),
        ("reservas", "0002_tarifa_inicial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="PeriodoCalendario",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("fecha_inicio", models.DateField()),
                        ("fecha_fin", models.DateField()),
                        ("tipo", models.CharField(max_length=15)),
                        (
                            "publicacion",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE, related_name="+", to="catalogo.publicacion",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "periodo_calendario",
                        "ordering": ["fecha_inicio"],
                        "constraints": [
                            models.CheckConstraint(
                                condition=models.Q(("fecha_fin__gt", models.F("fecha_inicio"))), name="periodo_rango_valido",
                            ),
                            models.CheckConstraint(
                                condition=models.Q(("tipo__in", ["DISPONIBLE", "NO_DISPONIBLE"])), name="periodo_tipo_valido",
                            ),
                        ],
                    },
                ),
            ],
            database_operations=[],
        ),
        migrations.AddField(
            model_name="periodocalendario", name="disponible", field=models.BooleanField(default=False), preserve_default=False,
        ),
        migrations.RunPython(tipo_a_disponible, disponible_a_tipo),
        migrations.RemoveConstraint(model_name="periodocalendario", name="periodo_tipo_valido"),
        # Default temporal para que la reversa pueda volver a crear la columna NOT NULL con filas
        migrations.AlterField(model_name="periodocalendario", name="tipo", field=models.CharField(default="NO_DISPONIBLE", max_length=15)),
        migrations.RemoveField(model_name="periodocalendario", name="tipo"),
    ]
