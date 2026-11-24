"""Rutas de administración de SRV-02 Catálogo (MOD-02).

Se montan en /api/v1/admin/ desde config/urls.py y solo las usa el Administrador: cada vista exige un
permiso que en la matriz de apps/comun/rbac.py solo tiene ese rol.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("publicaciones", views.PublicacionesAdmin.as_view(), name="publicaciones"),
    path("publicaciones/<int:pk>/revision", views.RevisionAdmin.as_view(), name="revision"),
    path("publicaciones/<int:pk>/bloqueo", views.BloqueoAdmin.as_view(), name="bloqueo"),
]
