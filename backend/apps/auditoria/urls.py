"""Rutas de la API de SRV-08 Auditoría (MOD-08): registro de acciones.

Se montan en /api/v1/auditoria/ desde config/urls.py. Cada vista declara el permiso que exige
(apps.comun.permisos.RequierePermiso), según la matriz de apps/comun/rbac.py.
"""

from django.urls import path

app_name = "auditoria"

urlpatterns: list = [
    # Rutas de SRV-08 Auditoría bajo /api/v1/auditoria/ (sección 3.4 del documento de diseño).
]
