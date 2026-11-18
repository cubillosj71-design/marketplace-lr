from django.urls import path

from . import views

urlpatterns = [
    path("tarifa-servicio", views.TarifaServicioAdmin.as_view(), name="tarifa-servicio"),
    path("reservas", views.ReservasAdmin.as_view(), name="reservas"),
    path("reservas/<int:pk>/resolver", views.Resolver.as_view(), name="resolver"),
]
