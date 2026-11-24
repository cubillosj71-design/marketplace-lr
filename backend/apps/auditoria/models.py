"""Modelos de SRV-08 Auditoría (MOD-08).

Tablas de este servicio: evento_auditoria. Es un registro de solo inserción: la migración 0004
crea los triggers que rechazan UPDATE, DELETE y TRUNCATE (RNF-E-CON-01, CA-23.2).
"""

from django.conf import settings
from django.db import models


class EventoAuditoria(models.Model):
    # actor_id BIGINT NULL: quien hizo la acción (nulo si no se identificó, p. ej. un correo inexistente)
    """Evento del registro de acciones (tabla evento_auditoria, MOD-08).

    Registro de solo inserción: triggers de la base rechazan UPDATE, DELETE y TRUNCATE
    (RNF-E-CON-01, conservación por 10 años).

    Attributes:
        actor: usuario que hizo la acción; nulo si no se identificó (por ejemplo, un correo inexistente).
        accion: nombre de la acción (InicioSesion, ReservaCancelada, AccesoDenegado...).
        entidad, entidad_id: objeto afectado, si lo hay.
        exitoso: False para intentos fallidos o negados.
        detalle: datos de la acción en JSON (motivo, montos, ruta...).
        ip: IP del cliente.
        fecha: momento del registro.
    """
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    accion = models.CharField(max_length=50)
    entidad = models.CharField(max_length=30, blank=True, null=True)
    entidad_id = models.BigIntegerField(blank=True, null=True)
    exitoso = models.BooleanField()
    detalle = models.JSONField(blank=True, null=True)
    ip = models.GenericIPAddressField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "evento_auditoria"
        ordering = ["-fecha", "-id"]
        indexes = [models.Index(fields=["fecha"], name="evento_fecha"), models.Index(fields=["accion"], name="evento_accion")]
