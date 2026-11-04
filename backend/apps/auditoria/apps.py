from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    """SRV-08 Auditoría: Registro de solo inserción de eventos, accesos y fallas."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.auditoria"
    verbose_name = "SRV-08 Auditoría"
