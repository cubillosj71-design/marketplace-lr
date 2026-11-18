from django.urls import path

from . import views

app_name = "identidad-admin"

# Rutas de administración de SRV-01 bajo /api/v1/admin/ (exigen el rol ADMINISTRADOR).
urlpatterns = [
    path("usuarios/<int:usuario_id>/restriccion", views.RestriccionVista.as_view(), name="restriccion"),
]
