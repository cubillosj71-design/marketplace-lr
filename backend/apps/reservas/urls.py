from django.urls import path

from . import views

app_name = "reservas"

# Rutas de SRV-04 Reservas bajo /api/v1/reservas/ (sección 3.4 del documento de diseño).
# POST /api/v1/reservas (sin barra final) y GET/POST /api/v1/catalogo/publicaciones/{id}/calendario
# se declaran en config/urls.py.
urlpatterns = [
    path("cotizaciones", views.Cotizaciones.as_view(), name="cotizaciones"),
    path("cotizaciones/<int:pk>", views.CotizacionDetalle.as_view(), name="cotizacion"),
    path("mias", views.MisReservas.as_view(), name="mias"),
    path("de-mis-alojamientos", views.DeMisAlojamientos.as_view(), name="de-mis-alojamientos"),
    path("<int:pk>", views.ReservaDetalle.as_view(), name="reserva"),
    path("<int:pk>/cancelar", views.Cancelar.as_view(), name="cancelar"),
]
