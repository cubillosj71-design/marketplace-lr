"""Panel de Django para la carga inicial y la consulta rápida (ADR-002).

Es solo de consulta: las cuentas se crean por la API (registro) o con
createsuperuser (Administrador), y los cambios de estado pasan por services.py
para que queden en el registro de acciones.
"""

from django.contrib import admin

from .models import RestriccionUsuario, Usuario


class SoloLectura(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Usuario)
class UsuarioAdmin(SoloLectura):
    list_display = ["correo", "nombre_completo", "rol", "estado", "fecha_registro", "last_login"]
    list_filter = ["rol", "estado"]
    search_fields = ["correo", "nombre_completo"]
    exclude = ["password"]


@admin.register(RestriccionUsuario)
class RestriccionUsuarioAdmin(SoloLectura):
    list_display = ["usuario", "administrador", "fecha_inicio", "fecha_fin"]
