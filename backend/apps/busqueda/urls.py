"""Rutas de la API de SRV-03 Búsqueda (MOD-03): búsqueda pública de alojamientos.

Se montan en /api/v1/busqueda/ desde config/urls.py. Cada vista declara el permiso que exige
(apps.comun.permisos.RequierePermiso), según la matriz de apps/comun/rbac.py.
"""

from django.urls import path

from . import views

app_name = "busqueda"

# Rutas de SRV-03 Búsqueda bajo /api/v1/busqueda/ (sección 3.4 del documento de diseño). Públicas.
urlpatterns = [
    path("publicaciones", views.Publicaciones.as_view(), name="publicaciones"),
    path("publicaciones/<int:pk>", views.PublicacionDetalle.as_view(), name="publicacion"),
]
