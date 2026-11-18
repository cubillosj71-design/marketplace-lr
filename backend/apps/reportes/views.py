"""Vistas REST de SRV-09 Reportes (RF-D-ADM-05.1 y 05.2)."""

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comun.eventos import ip_de
from apps.comun.permisos import EsAdministrador

from . import services


class Periodo(serializers.Serializer):
    desde = serializers.DateField(required=False)
    hasta = serializers.DateField(required=False)
    formato = serializers.ChoiceField(choices=services.FORMATOS, required=False)
    rol = serializers.ChoiceField(choices=["HUESPED", "ANFITRION", "ADMINISTRADOR"], required=False)
    estado = serializers.CharField(required=False)
    ciudad = serializers.IntegerField(required=False)
    tipo = serializers.IntegerField(required=False)

    def validate(self, d):
        hoy = timezone.localdate()
        d.setdefault("desde", hoy.replace(month=1, day=1))  # por defecto, el año en curso
        d.setdefault("hasta", hoy.replace(month=12, day=31))
        return d


class Tablero(APIView):
    """GET /admin/tablero?desde&hasta."""

    permission_classes = [EsAdministrador]

    def get(self, request):
        p = Periodo(data=request.query_params)
        p.is_valid(raise_exception=True)
        return Response(services.tablero(p.validated_data["desde"], p.validated_data["hasta"]))


class ReporteArchivo(APIView):
    """GET /admin/reportes/{tipo}?formato=pdf|xlsx&desde&hasta (tipos: usuarios, publicaciones, reservas, ingresos, demanda)."""

    permission_classes = [EsAdministrador]

    def get(self, request, tipo):
        p = Periodo(data=request.query_params)
        p.is_valid(raise_exception=True)
        d = p.validated_data
        filtros = {k: d[k] for k in ("rol", "estado", "ciudad", "tipo") if k in d}
        contenido, nombre, mime = services.generar(request.user, tipo, d.get("formato", "pdf"), d["desde"], d["hasta"], filtros, ip=ip_de(request))
        respuesta = HttpResponse(contenido, content_type=mime)
        respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
        respuesta["Access-Control-Expose-Headers"] = "Content-Disposition"
        return respuesta
