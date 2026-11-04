from django.apps import AppConfig


class ReportesConfig(AppConfig):
    """SRV-09 Reportes: Indicadores del tablero y exportación a PDF o Excel. Solo lectura."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reportes"
    verbose_name = "SRV-09 Reportes"
