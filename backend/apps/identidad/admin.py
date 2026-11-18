from django.contrib import admin

from .models import RestriccionUsuario, Usuario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ("correo", "nombre_completo", "rol", "activa", "fecha_registro")
    list_filter = ("rol", "activa")
    search_fields = ("correo", "nombre_completo")
    exclude = ("password",)


@admin.register(RestriccionUsuario)
class RestriccionAdmin(admin.ModelAdmin):
    list_display = ("usuario", "motivo", "fecha_inicio", "fecha_fin")
