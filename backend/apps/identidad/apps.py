from django.apps import AppConfig


class IdentidadConfig(AppConfig):
    """SRV-01 Identidad: Registro, autenticación, roles, perfil, desactivación, recuperación de contraseña y restricciones."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.identidad"
    verbose_name = "SRV-01 Identidad"
