from django.urls import path

from . import views

urlpatterns = [
    path("publicaciones", views.PublicacionesAdmin.as_view(), name="publicaciones"),
    path("publicaciones/<int:pk>/revision", views.RevisionAdmin.as_view(), name="revision"),
    path("publicaciones/<int:pk>/bloqueo", views.BloqueoAdmin.as_view(), name="bloqueo"),
]
