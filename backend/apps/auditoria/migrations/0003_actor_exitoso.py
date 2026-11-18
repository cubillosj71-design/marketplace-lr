"""evento_auditoria igual al modelo relacional (MOD-08): usuario -> actor y resultado -> exitoso.

El trigger de solo inserción se quita mientras se convierten los datos (la conversión es un UPDATE)
y la migración 0004 lo vuelve a crear, ahora también contra TRUNCATE.
"""

from django.db import migrations, models

QUITAR_TRIGGER = """
DROP TRIGGER IF EXISTS evento_auditoria_sin_cambios ON evento_auditoria;
DROP FUNCTION IF EXISTS evento_auditoria_solo_insercion();
"""

TRIGGER_ANTERIOR = """
CREATE OR REPLACE FUNCTION evento_auditoria_solo_insercion() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'evento_auditoria es de solo inserción: % no permitido', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER evento_auditoria_sin_cambios
    BEFORE UPDATE OR DELETE ON evento_auditoria
    FOR EACH ROW EXECUTE FUNCTION evento_auditoria_solo_insercion();
"""


class Migration(migrations.Migration):
    dependencies = [("auditoria", "0002_trigger_solo_insercion")]

    operations = [
        migrations.RunSQL(QUITAR_TRIGGER, TRIGGER_ANTERIOR),
        migrations.RenameField(model_name="eventoauditoria", old_name="usuario", new_name="actor"),
        migrations.RemoveConstraint(model_name="eventoauditoria", name="evento_resultado_valido"),
        migrations.AddField(
            model_name="eventoauditoria", name="exitoso", field=models.BooleanField(default=True), preserve_default=False,
        ),
        migrations.RunSQL(
            "UPDATE evento_auditoria SET exitoso = (resultado = 'EXITO');",
            "UPDATE evento_auditoria SET resultado = CASE WHEN exitoso THEN 'EXITO' ELSE 'FALLO' END;",
        ),
        # Default temporal para que la reversa pueda volver a crear la columna NOT NULL con filas.
        migrations.AlterField(
            model_name="eventoauditoria", name="resultado",
            field=models.CharField(choices=[("EXITO", "Éxito"), ("FALLO", "Fallo")], default="EXITO", max_length=10),
        ),
        migrations.RemoveField(model_name="eventoauditoria", name="resultado"),
    ]
