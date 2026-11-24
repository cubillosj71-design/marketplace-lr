"""Registro de modelos de SRV-02 Catálogo (MOD-02) en el sitio de administración de Django (/admin/).

Solo lo usa el equipo para la carga inicial y el soporte (ADR-002); los usuarios trabajan en la aplicación web.
"""

from django.contrib import admin

from .models import Ciudad, PoliticaCancelacion, Publicacion, Servicio, TipoAlojamiento

admin.site.register([Ciudad, TipoAlojamiento, Servicio, PoliticaCancelacion])


@admin.register(Publicacion)
class PublicacionAdmin(admin.ModelAdmin):
    """Publicaciones en el sitio de administración de Django: lista con título, anfitrión, ciudad y estado."""
    list_display = ("titulo", "anfitrion", "ciudad", "estado", "actualizada")
    list_filter = ("estado", "ciudad")
    search_fields = ("titulo",)
