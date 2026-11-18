"""Modelos de SRV-06 Reseñas.

Tablas de este servicio: resena (llega con el módulo de Reseñas).
Vista de solo lectura que publica: v_calificacion_publicacion (migración 0001).
Ver la sección 9 del documento de diseño (docs/diseno).
"""

from django.db import models


class CalificacionPublicacion(models.Model):
    """Vista v_calificacion_publicacion: promedio y total de reseñas visibles por publicación.
    Mientras no exista la tabla resena devuelve promedio NULL y total 0 (ver la migración)."""

    publicacion_id = models.BigIntegerField(primary_key=True)
    promedio = models.DecimalField(max_digits=3, decimal_places=2, null=True)
    total = models.IntegerField()

    class Meta:
        managed = False
        db_table = "v_calificacion_publicacion"
