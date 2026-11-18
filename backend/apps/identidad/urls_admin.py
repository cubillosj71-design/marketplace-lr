from django.urls import path

from . import views

urlpatterns = [
    path("usuarios", views.UsuariosAdmin.as_view(), name="usuarios"),
    path("usuarios/<int:usuario_id>/restriccion", views.RestriccionAdmin.as_view(), name="restriccion"),
]
