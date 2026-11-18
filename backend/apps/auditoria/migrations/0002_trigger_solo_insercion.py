"""Registro de solo inserción (RNF-E-CON-01): nadie puede modificar ni borrar un evento."""

from django.db import migrations

CREAR = """
CREATE OR REPLACE FUNCTION evento_auditoria_solo_insercion() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'evento_auditoria es de solo inserción: % no permitido', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER evento_auditoria_sin_cambios
    BEFORE UPDATE OR DELETE ON evento_auditoria
    FOR EACH ROW EXECUTE FUNCTION evento_auditoria_solo_insercion();
"""

QUITAR = """
DROP TRIGGER IF EXISTS evento_auditoria_sin_cambios ON evento_auditoria;
DROP FUNCTION IF EXISTS evento_auditoria_solo_insercion();
"""


class Migration(migrations.Migration):
    dependencies = [("auditoria", "0001_initial")]
    operations = [migrations.RunSQL(CREAR, QUITAR)]
