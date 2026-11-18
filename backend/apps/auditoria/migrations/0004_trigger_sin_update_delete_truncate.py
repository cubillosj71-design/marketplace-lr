"""Registro de solo inserción (RNF-E-CON-01, CA-23.2): nadie puede modificar, borrar ni vaciar la tabla.

UPDATE y DELETE se rechazan con un trigger por fila. TRUNCATE no dispara triggers por fila,
así que necesita uno aparte a nivel de sentencia: BEFORE TRUNCATE ... FOR EACH STATEMENT.
"""

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

CREATE TRIGGER evento_auditoria_sin_vaciar
    BEFORE TRUNCATE ON evento_auditoria
    FOR EACH STATEMENT EXECUTE FUNCTION evento_auditoria_solo_insercion();
"""

QUITAR = """
DROP TRIGGER IF EXISTS evento_auditoria_sin_vaciar ON evento_auditoria;
DROP TRIGGER IF EXISTS evento_auditoria_sin_cambios ON evento_auditoria;
DROP FUNCTION IF EXISTS evento_auditoria_solo_insercion();
"""


class Migration(migrations.Migration):
    dependencies = [("auditoria", "0003_actor_exitoso")]
    operations = [migrations.RunSQL(CREAR, QUITAR)]
