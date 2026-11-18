from django.apps import AppConfig


class ReservasConfig(AppConfig):
    """SRV-04 Reservas: Cotización, reserva idempotente sin superposición, cancelación con política,
    reservas EN_REVISION, cambio a COMPLETADA y tarifa de servicio."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reservas"
    verbose_name = "SRV-04 Reservas"

    def ready(self):
        from apps.comun.eventos import evento_dominio

        from . import services

        evento_dominio.connect(services.al_bloquear_publicacion, dispatch_uid="reservas_al_bloquear_publicacion")
