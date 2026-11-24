"""Rutas de administración de SRV-09 Reportes (MOD-09).

Se montan en /api/v1/admin/ desde config/urls.py y solo las usa el Administrador: cada vista exige un
permiso que en la matriz de apps/comun/rbac.py solo tiene ese rol.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("tablero", views.Tablero.as_view(), name="tablero"),
    path("reportes/<str:tipo>", views.ReporteArchivo.as_view(), name="reporte"),
]
