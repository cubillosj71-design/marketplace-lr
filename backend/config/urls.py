"""Rutas del proyecto. Todas las rutas REST van bajo /api/v1 (sección 3.4 del documento de diseño)."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def salud(request):
    """Ruta de salud que consulta el monitor externo (RNF-P-FIA-01)."""
    return JsonResponse({"estado": "ok"})


SERVICIOS = ["identidad", "catalogo", "busqueda", "reservas", "resenas", "notificaciones", "auditoria", "reportes"]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/salud", salud),
] + [path(f"api/v1/{s}/", include(f"apps.{s}.urls")) for s in SERVICIOS]
