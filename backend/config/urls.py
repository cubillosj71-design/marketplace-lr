"""Rutas del proyecto. Todas las rutas REST van bajo /api/v1 (sección 3.4 del documento de diseño)."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from apps.comun import interno
from apps.notificaciones import views as notificaciones
from apps.reservas import views as reservas


def salud(request):
    """Ruta de salud que consulta el monitor externo (RNF-P-FIA-01)."""
    return JsonResponse({"estado": "ok"})


SERVICIOS = ["identidad", "catalogo", "busqueda", "reservas", "resenas", "notificaciones", "auditoria", "reportes"]

# Rutas de administración: prefijo /api/v1/admin y rol ADMINISTRADOR (sección 3.4)
ADMIN = ["identidad", "catalogo", "reservas", "auditoria", "reportes"]

urlpatterns = (
    [
        path("admin/", admin.site.urls),
        path("api/v1/salud", salud),
        # POST /api/v1/reservas (RF-D-RES-02.2)
        path("api/v1/reservas", reservas.Reservas.as_view(), name="reservas"),
        # El calendario conserva su ruta de Catálogo para el frontend, pero lo atiende MOD-04 Reservas
        path("api/v1/catalogo/publicaciones/<int:pk>/calendario", reservas.Calendario.as_view(), name="calendario"),
        # GET /api/v1/notificaciones (HU-16)
        path("api/v1/notificaciones", notificaciones.Bandeja.as_view(), name="notificaciones"),
        # Operación interna: tareas programadas protegidas con X-Token-Tareas (C4 nivel 3)
        path("api/v1/interno/tareas/diarias", interno.TareasDiarias.as_view(), name="tareas-diarias"),
    ]
    + [path(f"api/v1/{s}/", include(f"apps.{s}.urls")) for s in SERVICIOS]
    + [path("api/v1/admin/", include((f"apps.{s}.urls_admin", f"admin-{s}"))) for s in ADMIN]
)
