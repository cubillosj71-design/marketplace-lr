from django.urls import path

from . import views

app_name = "identidad"

# Rutas de SRV-01 Identidad bajo /api/v1/identidad/ (sección 3.4 del documento de diseño)
urlpatterns = [
    path("registro", views.Registro.as_view(), name="registro"),
    path("token", views.Token.as_view(), name="token"),
    path("token/renovar", views.TokenRenovar.as_view(), name="token-renovar"),
    path("salir", views.Salir.as_view(), name="salir"),
    path("recuperacion", views.Recuperacion.as_view(), name="recuperacion"),
    path("recuperacion/<str:token>", views.RecuperacionToken.as_view(), name="recuperacion-token"),
    path("perfil", views.Perfil.as_view(), name="perfil"),
    path("perfil/desactivar", views.Desactivar.as_view(), name="desactivar"),
]
