from django.apps import AppConfig


class NotificacionesConfig(AppConfig):
    """SRV-07 Notificaciones: Notificaciones a partir de eventos de dominio y bandeja del usuario."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notificaciones"
    verbose_name = "SRV-07 Notificaciones"
