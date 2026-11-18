"""Vista de solo lectura v_publicacion_buscable (MOD-02 la publica; MOD-03 Búsqueda y MOD-04 Reservas la leen).

Publicaciones ACTIVAS cuyo anfitrión tiene usuario.activa = true y ninguna restriccion_usuario vigente
(CA-04.3, CA-21.2). servicios es el arreglo de ids de servicio; imagen_principal es la de menor orden.
"""

from django.db import migrations

CREAR = """
CREATE OR REPLACE VIEW v_publicacion_buscable AS
SELECT
    p.id,
    p.titulo,
    p.ciudad_id,
    c.nombre AS ciudad,
    p.tipo_alojamiento_id,
    t.nombre AS tipo,
    p.capacidad,
    p.precio_noche,
    p.tarifa_limpieza,
    p.descuento_porcentaje,
    p.descuento_min_noches,
    p.politica_id,
    ARRAY(SELECT ps.servicio_id FROM publicacion_servicio ps WHERE ps.publicacion_id = p.id ORDER BY ps.servicio_id)
        AS servicios,
    (SELECT i.ruta FROM imagen_publicacion i WHERE i.publicacion_id = p.id ORDER BY i.orden, i.id LIMIT 1)
        AS imagen_principal
FROM publicacion p
JOIN ciudad c ON c.id = p.ciudad_id
JOIN tipo_alojamiento t ON t.id = p.tipo_alojamiento_id
JOIN usuario u ON u.id = p.anfitrion_id
WHERE p.estado = 'ACTIVA'
  AND u.activa
  AND NOT EXISTS (
      SELECT 1 FROM restriccion_usuario r
      WHERE r.usuario_id = u.id
        AND r.fecha_inicio <= statement_timestamp()
        AND (r.fecha_fin IS NULL OR r.fecha_fin > statement_timestamp())
  );
"""

QUITAR = "DROP VIEW IF EXISTS v_publicacion_buscable;"


class Migration(migrations.Migration):
    dependencies = [
        ("catalogo", "0003_periodo_calendario_a_reservas"),
        ("identidad", "0003_usuario_segun_modelo_relacional"),
    ]
    operations = [migrations.RunSQL(CREAR, QUITAR)]
