from django.apps import AppConfig


class BusquedaConfig(AppConfig):
    """SRV-03 Búsqueda: Consulta pública de la oferta con filtros y detalle. Solo lectura."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.busqueda"
    verbose_name = "SRV-03 Búsqueda"
