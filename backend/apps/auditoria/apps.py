from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    """SRV-08 Auditoría: Registro de solo inserción de eventos, accesos y fallas."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.auditoria"
    verbose_name = "SRV-08 Auditoría"

    def ready(self):
        from apps.comun.eventos import evento_dominio

        from . import services

        # Se suscribe a todos los eventos de dominio sin que quien publica lo conozca (ADR-007)
        evento_dominio.connect(services.registrar_evento, dispatch_uid="auditoria_registrar_evento")
