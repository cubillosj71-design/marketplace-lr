from django.apps import AppConfig


class ResenasConfig(AppConfig):
    """SRV-06 Reseñas: Reseña de una reserva completada, ocultamiento por moderación y calificación promedio."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.resenas"
    verbose_name = "SRV-06 Reseñas"
