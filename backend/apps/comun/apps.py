from django.apps import AppConfig


class ComunConfig(AppConfig):
    """Piezas transversales: eventos de dominio, permisos, errores y el comando cargar_demo. Sin modelos."""

    name = "apps.comun"
    verbose_name = "Transversal"
