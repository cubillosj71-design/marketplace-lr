from django.urls import path

from . import views

app_name = "identidad"

# Rutas de SRV-01 Identidad bajo /api/v1/identidad/ (sección 3.4 del documento de diseño).
urlpatterns = [
    path("registro", views.RegistroVista.as_view(), name="registro"),
    path("token", views.TokenVista.as_view(), name="token"),
    path("token/renovar", views.RenovarVista.as_view(), name="renovar"),
    path("salir", views.SalirVista.as_view(), name="salir"),
    path("recuperacion", views.RecuperacionVista.as_view(), name="recuperacion"),
    path("recuperacion/<str:token>", views.RecuperacionTokenVista.as_view(), name="recuperacion-token"),
    path("perfil", views.PerfilVista.as_view(), name="perfil"),
    path("perfil/desactivar", views.DesactivarVista.as_view(), name="desactivar"),
]
