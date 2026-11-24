"""Rutas de la API de SRV-05 Pagos (MOD-05): cobros y devoluciones.

Se montan en /api/v1/pagos/ desde config/urls.py. Cada vista declara el permiso que exige
(apps.comun.permisos.RequierePermiso), según la matriz de apps/comun/rbac.py.
"""

from django.urls import path

app_name = "pagos"

urlpatterns: list = [
    # Rutas de SRV-05 Pagos bajo /api/v1/pagos/ (sección 3.4 del documento de diseño).
]
