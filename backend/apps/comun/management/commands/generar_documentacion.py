"""Genera la documentación del código fuente del backend en HTML: python manage.py generar_documentacion

Usa pdoc, que lee los docstrings (formato Google) de cada módulo, clase y función. La salida queda en
docs/codigo/ (una página por módulo e index.html). Se excluyen las migraciones, las pruebas y config.settings
(para no publicar valores de configuración).
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

# config.settings NO se documenta: pdoc mostraría los valores de la configuración (correo, base de datos, llaves).
MODULOS = ["apps", "config", r"!apps\..*\.migrations.*", r"!apps\..*\.tests.*", r"!config\.(wsgi|asgi|settings)"]


class Command(BaseCommand):
    """Comando `python manage.py generar_documentacion`: genera docs/codigo/ con pdoc (requirements-dev.txt)."""

    help = "Genera la documentación HTML del código fuente del backend en docs/codigo/ (requiere pdoc)."

    def add_arguments(self, parser):
        parser.add_argument("--salida", default=str(Path(settings.BASE_DIR).parent / "docs" / "codigo"),
                            help="Carpeta de salida (por defecto docs/codigo en la raíz del repositorio).")

    def handle(self, *args, salida, **_):
        import pdoc
        import pdoc.render

        # Django ya está configurado (el comando corre dentro de manage.py), así que pdoc puede importar los modelos
        pdoc.render.configure(docformat="google", footer_text="Alojamientos LR · Inversiones LR", search=True, show_source=True)
        destino = Path(salida)
        pdoc.pdoc(*MODULOS, output_directory=destino)
        paginas = len(list(destino.rglob("*.html")))
        self.stdout.write(self.style.SUCCESS(f"Documentación generada en {destino} ({paginas} páginas). Abre index.html."))
