"""Modelos de SRV-07 Notificaciones (MOD-07).

Tablas de este servicio: notificacion. Los avisos se crean a partir de los eventos de dominio, después de
confirmar la transacción que los produjo (C4 nivel 3).
"""

from django.conf import settings
from django.db import models


class Notificacion(models.Model):
    """Aviso dentro de la plataforma para un usuario (tabla notificacion, MOD-07).

    Se crea a partir de un evento de dominio después de confirmar la transacción que lo produjo.

    Attributes:
        destinatario: usuario que recibe el aviso.
        tipo: evento que lo originó (por ejemplo, ReservaConfirmada).
        mensaje: texto que ve el usuario (máximo 300 caracteres).
        entidad, entidad_id: objeto al que se refiere, para enlazarlo.
        leida: si el usuario ya lo vio.
        fecha: momento en que se creó.
    """
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
        """Marca el aviso como leído (no hace nada si ya lo estaba)."""
        if not self.leida:
            self.leida = True
            self.save(update_fields=["leida"])
