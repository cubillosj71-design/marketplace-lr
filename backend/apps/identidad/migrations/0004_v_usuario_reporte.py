"""Vista de solo lectura v_usuario_reporte (MOD-01 la publica; MOD-09 Reportes la lee).

restringida y motivo_restriccion se derivan de una restriccion_usuario vigente; la vigencia se compara con
statement_timestamp() (hora de la consulta), igual que v_publicacion_buscable.
"""

from django.db import migrations

CREAR = """
CREATE OR REPLACE VIEW v_usuario_reporte AS
SELECT
    u.id,
    u.nombre_completo,
    u.correo,
    u.telefono,
    u.ciudad,
    u.rol,
    u.activa,
    (r.id IS NOT NULL) AS restringida,
    r.motivo AS motivo_restriccion,
    u.autorizacion_datos,
    u.fecha_registro
FROM usuario u
LEFT JOIN LATERAL (
    SELECT rr.id, rr.motivo
    FROM restriccion_usuario rr
    WHERE rr.usuario_id = u.id
      AND rr.fecha_inicio <= statement_timestamp()
      AND (rr.fecha_fin IS NULL OR rr.fecha_fin > statement_timestamp())
    ORDER BY rr.fecha_inicio DESC
    LIMIT 1
) r ON true;
"""

QUITAR = "DROP VIEW IF EXISTS v_usuario_reporte;"


class Migration(migrations.Migration):
    dependencies = [("identidad", "0003_usuario_segun_modelo_relacional")]
    operations = [migrations.RunSQL(CREAR, QUITAR)]
