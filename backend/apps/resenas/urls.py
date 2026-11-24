"""Rutas de la API de SRV-06 Reseñas (MOD-06): reseñas y calificación.

Se montan en /api/v1/resenas/ desde config/urls.py. Cada vista declara el permiso que exige
(apps.comun.permisos.RequierePermiso), según la matriz de apps/comun/rbac.py.
"""

from django.urls import path

app_name = "resenas"

urlpatterns: list = [
    # Rutas de SRV-06 Reseñas bajo /api/v1/resenas/ (sección 3.4 del documento de diseño).
]
