from django.apps import AppConfig


class CatalogoConfig(AppConfig):
    """SRV-02 Catálogo: Ciclo de vida de la publicación: creación, revisión, estados, servicios, reglas, imágenes, política de cancelación, calendario y moderación."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalogo"
    verbose_name = "SRV-02 Catálogo"
