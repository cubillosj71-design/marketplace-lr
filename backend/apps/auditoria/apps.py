from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    """SRV-08 Auditoría: Registro de solo inserción de eventos, accesos y fallas.

    No se suscribe a eventos de dominio: cada módulo llama a auditoria.services.registrar_evento()
    en la misma transacción de su cambio (C4 nivel 3, vista b)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.auditoria"
    verbose_name = "SRV-08 Auditoría"
