"""Registro de modelos de SRV-01 Identidad (MOD-01) en el sitio de administración de Django (/admin/).

Solo lo usa el equipo para la carga inicial y el soporte (ADR-002); los usuarios trabajan en la aplicación web.
"""

from django.contrib import admin

from .models import RestriccionUsuario, Usuario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    """Usuarios en el sitio de administración de Django.

    La contraseña nunca se muestra: Django solo guarda su hash (RNF-P-SEG-01).
    """
    list_display = ("correo", "nombre_completo", "rol", "activa", "fecha_registro")
    list_filter = ("rol", "activa")
    search_fields = ("correo", "nombre_completo")
    exclude = ("password",)


@admin.register(RestriccionUsuario)
class RestriccionAdmin(admin.ModelAdmin):
    """Restricciones de cuentas en el sitio de administración de Django (RF-D-ADM-02.1)."""
    list_display = ("usuario", "motivo", "fecha_inicio", "fecha_fin")
