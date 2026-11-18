"""Vistas de solo lectura para MOD-09 Reportes (las publica MOD-04 Reservas) y creada con el reloj de la aplicación.

v_reserva_reporte: una fila por reserva, con las dos columnas calculadas de la nota de RF-D-ADM-05:
    monto_bruto        = total                                  si estado IN (CONFIRMADA, COMPLETADA, EN_REVISION)
                         total - valor_devolucion               si CANCELADA
    ingreso_plataforma = tarifa_servicio                        si estado IN (CONFIRMADA, COMPLETADA, EN_REVISION)
                         tarifa_servicio * (1 - valor_devolucion / total)   si CANCELADA
  Ejemplo (CA-24.4): $740.000 con servicio de $60.000, cancelada con devolución de $370.000 -> suma $370.000 al
  bruto y $30.000 a la plataforma.

v_demanda: v_reserva_reporte agrupada por ciudad, tipo y DÍA de creación (hora de Colombia). Se agrupa por día y no
  por periodo porque una vista no recibe parámetros: Reportes filtra los días del periodo y suma. Es la forma más
  simple de que la demanda use la misma regla de periodo (fecha de creación) que el tablero.

reserva.creada y cotizacion.creada toman la hora de apps.comun.reloj (antes auto_now_add): así las pruebas y la carga
de demostración crean reservas "en octubre" por los services reales, sin tocar filas protegidas por el trigger.
"""

import apps.comun.reloj
from django.db import migrations, models

VISTAS = """
CREATE OR REPLACE VIEW v_reserva_reporte AS
SELECT
    r.id,
    r.publicacion_id,
    p.titulo,
    COALESCE(c.nombre, 'Sin ciudad') AS ciudad,
    COALESCE(t.nombre, 'Sin tipo') AS tipo,
    r.huesped_id,
    u.nombre_completo AS huesped,
    r.creada,
    r.fecha_llegada,
    r.fecha_salida,
    co.noches,
    r.estado,
    r.total,
    co.tarifa_servicio,
    COALESCE(ca.valor_devolucion, 0)::numeric(12,2) AS valor_devolucion,
    (CASE
        WHEN r.estado IN ('CONFIRMADA', 'COMPLETADA', 'EN_REVISION') THEN r.total
        WHEN r.estado = 'CANCELADA' THEN r.total - COALESCE(ca.valor_devolucion, 0)
        ELSE 0
    END)::numeric(12,2) AS monto_bruto,
    (CASE
        WHEN r.estado IN ('CONFIRMADA', 'COMPLETADA', 'EN_REVISION') THEN co.tarifa_servicio
        WHEN r.estado = 'CANCELADA' THEN ROUND(co.tarifa_servicio * (1 - COALESCE(ca.valor_devolucion, 0) / NULLIF(r.total, 0)), 2)
        ELSE 0
    END)::numeric(12,2) AS ingreso_plataforma
FROM reserva r
JOIN cotizacion co ON co.id = r.cotizacion_id
JOIN publicacion p ON p.id = r.publicacion_id
LEFT JOIN ciudad c ON c.id = p.ciudad_id
LEFT JOIN tipo_alojamiento t ON t.id = p.tipo_alojamiento_id
JOIN usuario u ON u.id = r.huesped_id
LEFT JOIN cancelacion ca ON ca.reserva_id = r.id;

CREATE OR REPLACE VIEW v_demanda AS
SELECT
    ciudad,
    tipo,
    (creada AT TIME ZONE 'America/Bogota')::date AS fecha,
    COUNT(*)::integer AS reservas,
    SUM(monto_bruto)::numeric(14,2) AS monto_bruto,
    SUM(ingreso_plataforma)::numeric(14,2) AS ingreso_plataforma
FROM v_reserva_reporte
GROUP BY ciudad, tipo, (creada AT TIME ZONE 'America/Bogota')::date;
"""

QUITAR = """
DROP VIEW IF EXISTS v_demanda;
DROP VIEW IF EXISTS v_reserva_reporte;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("reservas", "0006_cancelacion"),
        ("catalogo", "0005_v_publicacion_reporte"),
    ]

    operations = [
        migrations.AlterField(model_name="cotizacion", name="creada", field=models.DateTimeField(default=apps.comun.reloj.ahora)),
        migrations.AlterField(model_name="reserva", name="creada", field=models.DateTimeField(default=apps.comun.reloj.ahora)),
        migrations.RunSQL(VISTAS, QUITAR),
    ]
