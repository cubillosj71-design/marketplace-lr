"""Modelos de SRV-07 Notificaciones (MOD-07).

Tablas de este servicio: notificacion. Los avisos se crean a partir de los eventos de dominio, después de
confirmar la transacción que los produjo (C4 nivel 3).
"""

from django.conf import settings
from django.db import models


class Notificacion(models.Model):
    destinatario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    tipo = models.CharField(max_length=40)
    mensaje = models.CharField(max_length=300)
    entidad = models.CharField(max_length=30, null=True, blank=True)
    entidad_id = models.BigIntegerField(null=True, blank=True)
    leida = models.BooleanField(default=False)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notificacion"
        ordering = ["leida", "-fecha", "-id"]  # primero las no leídas (CA-16.2)
        indexes = [models.Index(fields=["destinatario", "leida", "fecha"], name="notificacion_bandeja")]

    def marcar_leida(self) -> None:
        """marcarLeida() del diagrama."""
        if not self.leida:
            self.leida = True
            self.save(update_fields=["leida"])
