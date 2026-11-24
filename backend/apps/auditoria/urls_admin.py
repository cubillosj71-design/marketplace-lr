"""Rutas de administración de SRV-08 Auditoría (MOD-08).

Se montan en /api/v1/admin/ desde config/urls.py y solo las usa el Administrador: cada vista exige un
permiso que en la matriz de apps/comun/rbac.py solo tiene ese rol.
"""

from django.urls import path

from . import views

urlpatterns = [path("auditoria", views.AuditoriaAdmin.as_view(), name="auditoria")]
