"""Modelos de SRV-08 Auditoría.

Tablas de este servicio: evento_auditoria. Es un registro de solo inserción: la migración 0002
crea un trigger que rechaza UPDATE y DELETE (RNF-E-CON-01).
"""

from django.conf import settings
from django.db import models
from django.db.models import Q


class ResultadoEvento(models.TextChoices):
    EXITO = "EXITO", "Éxito"
    FALLO = "FALLO", "Fallo"


class EventoAuditoria(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    accion = models.CharField(max_length=50)
    entidad = models.CharField(max_length=30, blank=True, null=True)
    entidad_id = models.BigIntegerField(blank=True, null=True)
    resultado = models.CharField(max_length=10, choices=ResultadoEvento.choices)
    detalle = models.JSONField(blank=True, null=True)
    ip = models.GenericIPAddressField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "evento_auditoria"
        ordering = ["-fecha", "-id"]
        indexes = [models.Index(fields=["fecha"], name="evento_fecha"), models.Index(fields=["accion"], name="evento_accion")]
        constraints = [models.CheckConstraint(condition=Q(resultado__in=ResultadoEvento.values), name="evento_resultado_valido")]
