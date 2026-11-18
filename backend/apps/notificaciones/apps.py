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
        evento_dominio.connect(services.al_evento, dispatch_uid="notificaciones_al_evento")
