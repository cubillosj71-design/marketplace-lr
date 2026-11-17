from django.urls import path

from . import views

urlpatterns = [path("auditoria", views.AuditoriaAdmin.as_view(), name="auditoria")]
