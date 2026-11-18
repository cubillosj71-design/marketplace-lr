from django.urls import path

from . import views

app_name = "reservas"

# Rutas de SRV-04 Reservas bajo /api/v1/reservas/ (sección 3.4 del documento de diseño).
# POST /api/v1/reservas (sin barra final) y GET/POST /api/v1/catalogo/publicaciones/{id}/calendario
# se declaran en config/urls.py.
urlpatterns = [
    path("cotizaciones", views.Cotizaciones.as_view(), name="cotizaciones"),
    path("cotizaciones/<int:pk>", views.CotizacionDetalle.as_view(), name="cotizacion"),
]
