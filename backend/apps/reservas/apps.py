from django.apps import AppConfig


class ReservasConfig(AppConfig):
    """SRV-04 Reservas: Cotización, reserva idempotente sin superposición, cancelación con política, reservas EN_REVISION, cambio a COMPLETADA y tarifa de servicio."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reservas"
    verbose_name = "SRV-04 Reservas"
