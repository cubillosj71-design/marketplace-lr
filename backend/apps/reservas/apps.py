from django.apps import AppConfig


class ReservasConfig(AppConfig):
    """SRV-04 Reservas: Cotización, reserva idempotente sin superposición, cancelación con política,
    reservas EN_REVISION, cambio a COMPLETADA y tarifa de servicio."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reservas"
    verbose_name = "SRV-04 Reservas"

    def ready(self):
        from apps.comun.eventos import evento_dominio_en_transaccion

        from . import services

        # C4 nivel 3: "Entrega PublicacionBloqueada a [señal, misma transacción]" (CA-20.1)
        evento_dominio_en_transaccion.connect(services.al_bloquear_publicacion, dispatch_uid="reservas_al_bloquear_publicacion")
