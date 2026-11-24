"""Vistas REST de SRV-09 Reportes (RF-D-ADM-05.1 y 05.2)."""

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comun.eventos import obtener_ip
from apps.comun.permisos import RequierePermiso

from . import services


class Periodo(serializers.Serializer):
    """Parámetros del tablero y de los reportes: periodo (desde y hasta), formato y filtros opcionales.

    Sin periodo se usa el año en curso. El formato es pdf o xlsx; los filtros dependen del reporte
    (rol y estado de la cuenta; estado, ciudad y tipo de alojamiento).
    """
    desde = serializers.DateField(required=False)
    hasta = serializers.DateField(required=False)
    formato = serializers.ChoiceField(choices=services.FORMATOS, required=False)
    rol = serializers.ChoiceField(choices=["HUESPED", "ANFITRION", "ADMINISTRADOR"], required=False)
    estado = serializers.CharField(required=False)
    ciudad = serializers.CharField(required=False)  # nombre, como lo expone v_publicacion_reporte
    tipo = serializers.CharField(required=False)

    def validate(self, d):
        """Completa el periodo con el año en curso cuando no llega desde o hasta."""
        hoy = timezone.localdate()
        d.setdefault("desde", hoy.replace(month=1, day=1))  # por defecto, el año en curso
        d.setdefault("hasta", hoy.replace(month=12, day=31))
        return d


class Tablero(APIView):
    """GET /admin/tablero?desde&hasta."""

    permission_classes = [RequierePermiso("tablero.ver")]

    def get(self, request):
        p = Periodo(data=request.query_params)
        p.is_valid(raise_exception=True)
        return Response(services.consultar_tablero(p.validated_data["desde"], p.validated_data["hasta"]))


class ReporteArchivo(APIView):
    """GET /admin/reportes/{tipo}?formato=pdf|xlsx&desde&hasta (tipos: usuarios, publicaciones, reservas, ingresos, demanda)."""

    permission_classes = [RequierePermiso("reportes.descargar")]

    def get(self, request, tipo):
        p = Periodo(data=request.query_params)
        p.is_valid(raise_exception=True)
        d = p.validated_data
        filtros = {k: d[k] for k in ("rol", "estado", "ciudad", "tipo") if k in d}
        contenido, nombre, mime = services.generar_reporte(request.user, tipo, d.get("formato", "pdf"), d["desde"], d["hasta"], filtros, ip=obtener_ip(request))
        respuesta = HttpResponse(contenido, content_type=mime)
        respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
        respuesta["Access-Control-Expose-Headers"] = "Content-Disposition"
        return respuesta
