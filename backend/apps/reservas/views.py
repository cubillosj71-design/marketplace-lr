"""Vistas REST de SRV-04 Reservas. En este incremento: tarifa de servicio (RF-D-ADM-03.1)."""

from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comun.eventos import ip_de
from apps.comun.permisos import EsAdministrador

from . import services


class TarifaEntrada(serializers.Serializer):
    porcentaje = serializers.DecimalField(max_digits=5, decimal_places=2)


class TarifaServicioAdmin(APIView):
    """GET y PUT /admin/tarifa-servicio (HU-22, CA-22.1)."""

    permission_classes = [EsAdministrador]

    def get(self, request):
        return Response({"porcentaje": f"{services.tarifa_vigente():.2f}", "historial": services.historial_tarifa()})

    def put(self, request):
        s = TarifaEntrada(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(services.cambiar_tarifa(request.user, s.validated_data["porcentaje"], ip=ip_de(request)))
