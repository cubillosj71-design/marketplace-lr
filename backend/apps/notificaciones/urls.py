from django.urls import path

from . import views

app_name = "notificaciones"

# Rutas de SRV-07 Notificaciones bajo /api/v1/notificaciones/. GET /api/v1/notificaciones (sin barra final)
# se declara en config/urls.py.
urlpatterns = [
    path("leidas", views.MarcarTodas.as_view(), name="leidas"),
    path("<int:pk>/leida", views.MarcarLeida.as_view(), name="leida"),
]
