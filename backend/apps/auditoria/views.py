"""Vistas REST de SRV-08 Auditoría."""

from rest_framework import serializers
from rest_framework.generics import ListAPIView

from apps.comun.permisos import RequierePermiso

from . import services


class EventoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    fecha = serializers.DateTimeField()
    actor_id = serializers.IntegerField(allow_null=True)
    actor_nombre = serializers.CharField(source="actor.nombre_completo", default=None)
    actor_correo = serializers.CharField(source="actor.correo", default=None)
    actor_rol = serializers.CharField(source="actor.rol", default=None)
    accion = serializers.CharField()
    entidad = serializers.CharField(allow_null=True)
    entidad_id = serializers.IntegerField(allow_null=True)
    exitoso = serializers.BooleanField()
    detalle = serializers.JSONField(allow_null=True)
    ip = serializers.IPAddressField(allow_null=True)


class FiltrosSerializer(serializers.Serializer):
    usuario = serializers.IntegerField(required=False)  # actor_id
    tipo = serializers.ChoiceField(choices=list(services.TIPOS_ACCION), required=False)
    accion = serializers.CharField(required=False)
    exitoso = serializers.BooleanField(required=False, allow_null=True, default=None)
    desde = serializers.DateField(required=False)
    hasta = serializers.DateField(required=False)


class AuditoriaAdmin(ListAPIView):
    """GET /admin/auditoria?usuario&tipo&accion&desde&hasta (RF-D-ADM-04.1, CA-23.1, CA-23.3).

    Devuelve la página de eventos y, en "tipos", los tipos de acción disponibles para el filtro."""

    permission_classes = [RequierePermiso("auditoria.consultar")]
    serializer_class = EventoSerializer

    def get_queryset(self):
        f = FiltrosSerializer(data=self.request.query_params)
        f.is_valid(raise_exception=True)
        d = f.validated_data
        return services.consultar_eventos(
            actor_id=d.get("usuario"), tipo=d.get("tipo"), accion=d.get("accion"), exitoso=d.get("exitoso"),
            desde=d.get("desde"), hasta=d.get("hasta"),
        )

    def list(self, request, *args, **kwargs):
        respuesta = super().list(request, *args, **kwargs)
        respuesta.data["tipos"] = services.listar_tipos_accion()
        return respuesta
