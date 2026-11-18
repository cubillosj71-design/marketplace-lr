from django.urls import path

from . import views

urlpatterns = [
    path("tablero", views.Tablero.as_view(), name="tablero"),
    path("reportes/<str:tipo>", views.ReporteArchivo.as_view(), name="reporte"),
]
