"""Trigger de solo inserción en evento_auditoria (RNF-E-CON-01, sección 10.1 del diseño).

La regla se pone en la base de datos y no solo en el código porque debe cumplirse
también para quien entre directo a PostgreSQL, incluido un administrador.
"""

from django.db import migrations

CREAR = """
CREATE OR REPLACE FUNCTION evento_auditoria_solo_insercion() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'evento_auditoria es de solo inserción: no se permite %', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER evento_auditoria_sin_cambios
    BEFORE UPDATE OR DELETE ON evento_auditoria
    FOR EACH ROW EXECUTE FUNCTION evento_auditoria_solo_insercion();

CREATE TRIGGER evento_auditoria_sin_truncate
    BEFORE TRUNCATE ON evento_auditoria
    FOR EACH STATEMENT EXECUTE FUNCTION evento_auditoria_solo_insercion();
"""

QUITAR = """
DROP TRIGGER IF EXISTS evento_auditoria_sin_truncate ON evento_auditoria;
DROP TRIGGER IF EXISTS evento_auditoria_sin_cambios ON evento_auditoria;
DROP FUNCTION IF EXISTS evento_auditoria_solo_insercion();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("auditoria", "0001_evento_auditoria"),
    ]

    operations = [
        migrations.RunSQL(CREAR, reverse_sql=QUITAR),
    ]
