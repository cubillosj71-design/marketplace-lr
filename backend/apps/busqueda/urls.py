from django.urls import path

from . import views

app_name = "busqueda"

# Rutas de SRV-03 Búsqueda bajo /api/v1/busqueda/ (sección 3.4 del documento de diseño). Públicas.
urlpatterns = [
    path("publicaciones", views.Publicaciones.as_view(), name="publicaciones"),
    path("publicaciones/<int:pk>", views.PublicacionDetalle.as_view(), name="publicacion"),
]
