"""usuario y token_recuperacion iguales al modelo relacional (MOD-01).

- estado -> activa (BOOLEAN). activa = (estado != 'DESACTIVADA'). "Restringida" deja de ser una
  columna: se deriva de una restricción vigente.
- acepta_datos_en -> autorizacion_datos.
- ciudad pasa de llave foránea al catálogo a texto opcional VARCHAR(80) con el nombre de la ciudad.
- token_recuperacion: CHECK vence > creado.
"""

from django.db import migrations, models


def estado_a_activa(apps, schema_editor):
    Usuario = apps.get_model("identidad", "Usuario")
    Usuario.objects.filter(estado="DESACTIVADA").update(activa=False)
    Usuario.objects.exclude(estado="DESACTIVADA").update(activa=True)


def activa_a_estado(apps, schema_editor):
    Usuario = apps.get_model("identidad", "Usuario")
    Usuario.objects.filter(activa=False).update(estado="DESACTIVADA")
    Usuario.objects.filter(activa=True).update(estado="ACTIVA")


def ciudad_a_texto(apps, schema_editor):
    Usuario = apps.get_model("identidad", "Usuario")
    Ciudad = apps.get_model("catalogo", "Ciudad")
    nombres = dict(Ciudad.objects.values_list("id", "nombre"))
    for u in Usuario.objects.exclude(ciudad__isnull=True).only("id", "ciudad_id"):
        Usuario.objects.filter(pk=u.pk).update(ciudad_texto=nombres.get(u.ciudad_id))


def texto_a_ciudad(apps, schema_editor):
    Usuario = apps.get_model("identidad", "Usuario")
    Ciudad = apps.get_model("catalogo", "Ciudad")
    ids = {n: i for i, n in Ciudad.objects.values_list("id", "nombre")}
    for pk, nombre in Usuario.objects.exclude(ciudad_texto__isnull=True).values_list("id", "ciudad_texto"):
        Usuario.objects.filter(pk=pk).update(ciudad_id=ids.get(nombre))


class Migration(migrations.Migration):
    dependencies = [
        ("catalogo", "0002_catalogos_iniciales"),
        ("identidad", "0002_alter_usuario_ciudad_tokenrecuperacion_and_more"),
    ]

    operations = [
        # estado -> activa
        migrations.AddField(model_name="usuario", name="activa", field=models.BooleanField(default=True)),
        migrations.RunPython(estado_a_activa, activa_a_estado),
        migrations.RemoveConstraint(model_name="usuario", name="usuario_estado_valido"),
        migrations.RemoveField(model_name="usuario", name="estado"),
        # acepta_datos_en -> autorizacion_datos
        migrations.RenameField(model_name="usuario", old_name="acepta_datos_en", new_name="autorizacion_datos"),
        # ciudad: llave foránea -> texto opcional con el nombre de la ciudad que tenía
        migrations.AddField(model_name="usuario", name="ciudad_texto", field=models.CharField(blank=True, max_length=80, null=True)),
        migrations.RunPython(ciudad_a_texto, texto_a_ciudad),
        migrations.RemoveField(model_name="usuario", name="ciudad"),
        migrations.RenameField(model_name="usuario", old_name="ciudad_texto", new_name="ciudad"),
        # token_recuperacion: CHECK vence > creado
        migrations.AddConstraint(
            model_name="tokenrecuperacion",
            constraint=models.CheckConstraint(condition=models.Q(("vence__gt", models.F("creado"))), name="token_vence_despues_de_creado"),
        ),
    ]
