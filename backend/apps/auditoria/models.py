"""Modelos de SRV-08 Auditoría.

Tablas de este servicio: evento_auditoria.
Ver la sección 10 del documento de diseño (docs/diseno).

El registro es de solo inserción (RNF-E-CON-01): la migración 0002 crea un
trigger que rechaza UPDATE, DELETE y TRUNCATE, así que ni siquiera un
administrador con acceso a la base puede alterar lo que ya quedó registrado.
"""

from django.conf import settings
from django.db import models


class EventoAuditoria(models.Model):
    # Se referencia al usuario por AUTH_USER_MODEL (una cadena), no importando
    # apps.identidad.models: así se respeta la frontera de ADR-001.
    # PROTECT: un usuario con eventos registrados no se puede borrar.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    accion = models.CharField(max_length=50)
    entidad = models.CharField(max_length=30, null=True, blank=True)
    entidad_id = models.BigIntegerField(null=True, blank=True)
    exitoso = models.BooleanField()
    detalle = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "evento_auditoria"
        indexes = [
            models.Index(fields=["actor", "fecha"], name="evento_actor_fecha_idx"),
            models.Index(fields=["accion", "fecha"], name="evento_accion_fecha_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.fecha:%Y-%m-%d %H:%M} {self.accion} ({'ok' if self.exitoso else 'fallo'})"
