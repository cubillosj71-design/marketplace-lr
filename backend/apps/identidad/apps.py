from django.apps import AppConfig


class IdentidadConfig(AppConfig):
    """SRV-01 Identidad: Registro, autenticación, roles, perfil, desactivación, recuperación de contraseña y restricciones."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.identidad"
    verbose_name = "SRV-01 Identidad"

    def ready(self):
        from django.db.models.signals import post_migrate

        from apps.comun import rbac

        from . import services

        # RBAC dinámico (ADR-010): rbac lee de aquí los permisos de cada rol, y la matriz inicial se carga después
        # de migrate y de flush.
        rbac.registrar_fuente(services.permisos_del_rol)
        post_migrate.connect(services.asegurar_matriz, sender=self, dispatch_uid="identidad_asegurar_matriz")
