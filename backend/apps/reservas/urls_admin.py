"""Rutas de administración de SRV-04 Reservas (MOD-04).

Se montan en /api/v1/admin/ desde config/urls.py y solo las usa el Administrador: cada vista exige un
permiso que en la matriz de apps/comun/rbac.py solo tiene ese rol.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("tarifa-servicio", views.TarifaServicioAdmin.as_view(), name="tarifa-servicio"),
    path("reservas", views.ReservasAdmin.as_view(), name="reservas"),
    path("reservas/resueltas", views.ReservasResueltasAdmin.as_view(), name="reservas-resueltas"),
    path("reservas/<int:pk>", views.ReservaEnRevisionAdmin.as_view(), name="reserva-admin"),
    path("reservas/<int:pk>/resolver", views.Resolver.as_view(), name="resolver"),
]
