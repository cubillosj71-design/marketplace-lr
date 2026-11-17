"""Vistas REST de SRV-08 Auditoría."""

from rest_framework import serializers
from rest_framework.generics import ListAPIView

from apps.comun.permisos import EsAdministrador

from . import services


class EventoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    fecha = serializers.DateTimeField()
    usuario_id = serializers.IntegerField(allow_null=True)
    accion = serializers.CharField()
    entidad = serializers.CharField(allow_null=True)
    entidad_id = serializers.IntegerField(allow_null=True)
    resultado = serializers.CharField()
    detalle = serializers.JSONField(allow_null=True)
    ip = serializers.IPAddressField(allow_null=True)


class FiltrosSerializer(serializers.Serializer):
    usuario = serializers.IntegerField(required=False)
    accion = serializers.CharField(required=False)
    resultado = serializers.ChoiceField(choices=["EXITO", "FALLO"], required=False)
    desde = serializers.DateField(required=False)
    hasta = serializers.DateField(required=False)


class AuditoriaAdmin(ListAPIView):
    """GET /admin/auditoria?usuario&accion&desde&hasta (RF-D-ADM-04.1)."""

    permission_classes = [EsAdministrador]
    serializer_class = EventoSerializer

    def get_queryset(self):
        f = FiltrosSerializer(data=self.request.query_params)
        f.is_valid(raise_exception=True)
        d = f.validated_data
        return services.consultar(
            usuario_id=d.get("usuario"), accion=d.get("accion"), resultado=d.get("resultado"),
            desde=d.get("desde"), hasta=d.get("hasta"),
        )
