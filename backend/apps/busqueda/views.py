"""Vistas REST de SRV-03 Búsqueda. Públicas: las usan el Visitante y el Huésped (HU-10, HU-11)."""

from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services


class ListaDeEnteros(serializers.Field):
    """Acepta servicios=1,2 o servicios=1&servicios=2."""

    def to_internal_value(self, data):
        valores = data if isinstance(data, list) else [data]
        try:
            return [int(x) for v in valores for x in str(v).split(",") if x.strip()]
        except ValueError as e:
            raise serializers.ValidationError("Usa ids de servicio separados por comas.") from e


class FiltrosBusqueda(serializers.Serializer):
    ciudad = serializers.IntegerField(required=False)
    llegada = serializers.DateField(required=False)
    salida = serializers.DateField(required=False)
    huespedes = serializers.IntegerField(required=False, default=1)
    tipo = serializers.IntegerField(required=False)
    precio_min = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    precio_max = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    servicios = ListaDeEnteros(required=False)


class Publicaciones(APIView):
    """GET /busqueda/publicaciones?ciudad&llegada&salida&huespedes&tipo&precio_min&precio_max&servicios."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request):
        datos = {k: v for k, v in request.query_params.items() if v != ""}
        if request.query_params.getlist("servicios"):
            datos["servicios"] = request.query_params.getlist("servicios")
        f = FiltrosBusqueda(data=datos)
        f.is_valid(raise_exception=True)
        return Response(services.buscar(**f.validated_data))


class RangoDetalle(serializers.Serializer):
    desde = serializers.DateField(required=False)
    hasta = serializers.DateField(required=False)


class PublicacionDetalle(APIView):
    """GET /busqueda/publicaciones/{id}?desde&hasta."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request, pk):
        f = RangoDetalle(data=request.query_params)
        f.is_valid(raise_exception=True)
        return Response(services.detalle(pk, f.validated_data.get("desde"), f.validated_data.get("hasta")))
