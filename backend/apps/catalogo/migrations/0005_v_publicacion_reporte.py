"""Vista de solo lectura v_publicacion_reporte (MOD-02 la publica; MOD-09 Reportes la lee).

Publicaciones sin BORRADOR (los borradores solo los ve su dueño), con el nombre del anfitrión, la ciudad y el tipo.
"""

from django.db import migrations

CREAR = """
CREATE OR REPLACE VIEW v_publicacion_reporte AS
SELECT
    p.id,
    p.titulo,
    p.anfitrion_id,
    u.nombre_completo AS anfitrion,
    c.nombre AS ciudad,
    t.nombre AS tipo,
    p.precio_noche,
    p.estado,
    p.creada
FROM publicacion p
JOIN usuario u ON u.id = p.anfitrion_id
LEFT JOIN ciudad c ON c.id = p.ciudad_id
LEFT JOIN tipo_alojamiento t ON t.id = p.tipo_alojamiento_id
WHERE p.estado <> 'BORRADOR';
"""

QUITAR = "DROP VIEW IF EXISTS v_publicacion_reporte;"


class Migration(migrations.Migration):
    dependencies = [
        ("catalogo", "0004_v_publicacion_buscable"),
        ("identidad", "0003_usuario_segun_modelo_relacional"),
    ]
    operations = [migrations.RunSQL(CREAR, QUITAR)]
