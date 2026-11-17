from django.urls import path

from . import views

urlpatterns = [path("tarifa-servicio", views.TarifaServicioAdmin.as_view(), name="tarifa-servicio")]
