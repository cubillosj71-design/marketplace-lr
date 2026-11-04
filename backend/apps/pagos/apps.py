from django.apps import AppConfig


class PagosConfig(AppConfig):
    """SRV-05 Pagos: Adaptador de Stripe en modo prueba: cobros y devoluciones (interfaz IPagos)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.pagos"
    verbose_name = "SRV-05 Pagos"
