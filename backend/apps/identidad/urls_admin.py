from django.urls import path

from . import views

urlpatterns = [path("usuarios/<int:usuario_id>/restriccion", views.RestriccionAdmin.as_view(), name="restriccion")]
