"""Rutas de administración de SRV-01 Identidad (MOD-01).

Se montan en /api/v1/admin/ desde config/urls.py y solo las usa el Administrador: cada vista exige un
permiso que en la matriz de apps/comun/rbac.py solo tiene ese rol.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("usuarios", views.UsuariosAdmin.as_view(), name="usuarios"),
    path("usuarios/<int:usuario_id>/restriccion", views.RestriccionAdmin.as_view(), name="restriccion"),
]
