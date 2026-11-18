"""periodo_calendario pasa a MOD-04 Reservas (diagrama de clases y modelo relacional).

Solo cambia el estado de las migraciones: la tabla se conserva con su nombre y sus datos, y
reservas.0003 la toma. También se declara el modelo de solo lectura de v_publicacion_buscable
(la vista se crea en la migración 0004).
"""

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalogo", "0002_catalogos_iniciales")]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[migrations.DeleteModel(name="PeriodoCalendario")],
            database_operations=[],
        ),
        migrations.CreateModel(
            name="PublicacionBuscable",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=120)),
                ("ciudad_id", models.BigIntegerField()),
                ("ciudad", models.CharField(max_length=80)),
                ("tipo_alojamiento_id", models.BigIntegerField()),
                ("tipo", models.CharField(max_length=40)),
                ("capacidad", models.SmallIntegerField()),
                ("precio_noche", models.DecimalField(decimal_places=2, max_digits=12)),
                ("tarifa_limpieza", models.DecimalField(decimal_places=2, max_digits=12)),
                ("descuento_porcentaje", models.DecimalField(decimal_places=2, max_digits=5, null=True)),
                ("descuento_min_noches", models.SmallIntegerField(null=True)),
                ("politica_id", models.BigIntegerField()),
                ("servicios", django.contrib.postgres.fields.ArrayField(base_field=models.BigIntegerField(), size=None)),
                ("imagen_principal", models.CharField(max_length=500, null=True)),
            ],
            options={"db_table": "v_publicacion_buscable", "managed": False},
        ),
    ]
