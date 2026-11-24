"""Rutas de la API de SRV-09 Reportes (MOD-09): tablero y reportes descargables.

Se montan en /api/v1/reportes/ desde config/urls.py. Cada vista declara el permiso que exige
(apps.comun.permisos.RequierePermiso), según la matriz de apps/comun/rbac.py.
"""

from django.urls import path

app_name = "reportes"

urlpatterns: list = [
    # Rutas de SRV-09 Reportes bajo /api/v1/reportes/ (sección 3.4 del documento de diseño).
]
