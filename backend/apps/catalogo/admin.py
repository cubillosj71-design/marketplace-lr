from django.contrib import admin

from .models import Ciudad, PoliticaCancelacion, Publicacion, Servicio, TipoAlojamiento

admin.site.register([Ciudad, TipoAlojamiento, Servicio, PoliticaCancelacion])


@admin.register(Publicacion)
class PublicacionAdmin(admin.ModelAdmin):
    list_display = ("titulo", "anfitrion", "ciudad", "estado", "actualizada")
    list_filter = ("estado", "ciudad")
    search_fields = ("titulo",)
