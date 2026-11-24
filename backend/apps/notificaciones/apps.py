"""Configuración de la app SRV-07 Notificaciones (MOD-07) para Django (INSTALLED_APPS).

En ready() conecta su receptor de eventos de dominio (C4 nivel 3).
"""

from django.apps import AppConfig


class NotificacionesConfig(AppConfig):
    """SRV-07 Notificaciones: Notificaciones a partir de eventos de dominio y bandeja del usuario."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notificaciones"
    verbose_name = "SRV-07 Notificaciones"

    def ready(self):
        from apps.comun.eventos import evento_dominio

        from . import services

        # C4 nivel 3: "Entrega las notificaciones a [señal, después de confirmar]"
        evento_dominio.connect(services.recibir_evento_dominio, dispatch_uid="notificaciones_recibir_evento_dominio")
