from django.urls import path

from . import views

app_name = "catalogo"

# Rutas de SRV-02 Catálogo bajo /api/v1/catalogo/ (sección 3.4 del documento de diseño)
urlpatterns = [
    path("publicaciones", views.Publicaciones.as_view(), name="publicaciones"),
    path("mis-publicaciones", views.MisPublicaciones.as_view(), name="mis-publicaciones"),
    path("publicaciones/<int:pk>", views.PublicacionDetalle.as_view(), name="publicacion"),
    path("publicaciones/<int:pk>/pausar", views.Pausar.as_view(), name="pausar"),
    path("publicaciones/<int:pk>/reactivar", views.Reactivar.as_view(), name="reactivar"),
    path("publicaciones/<int:pk>/enviar-revision", views.EnviarRevision.as_view(), name="enviar-revision"),
    path("ciudades", views.Catalogos.as_view(clave="ciudades"), name="ciudades"),
    path("tipos-alojamiento", views.Catalogos.as_view(clave="tipos"), name="tipos"),
    path("servicios", views.Catalogos.as_view(clave="servicios"), name="servicios"),
    path("politicas", views.Catalogos.as_view(clave="politicas"), name="politicas"),
]
