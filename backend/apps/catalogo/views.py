"""Vistas REST de SRV-02 Catálogo (sección 3.4: /api/v1/catalogo/... y /api/v1/admin/publicaciones/...)."""

from datetime import date, timedelta

from rest_framework import serializers, status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comun.permisos import EsAdministrador, EsAnfitrion, EsAnfitrionOAdministrador

from . import services
from .models import EstadoPublicacion, Publicacion, TipoPeriodo

# ---------------------------------------------------------------- serializadores

class AdicionalSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=60, allow_blank=True)
    precio = serializers.DecimalField(max_digits=12, decimal_places=2)


class PublicacionEntrada(serializers.Serializer):
    titulo = serializers.CharField(max_length=120, allow_blank=True)
    descripcion = serializers.CharField(allow_blank=True, required=False)
    ciudad = serializers.IntegerField(allow_null=True, required=False)
    tipo_alojamiento = serializers.IntegerField(allow_null=True, required=False)
    politica = serializers.IntegerField(allow_null=True, required=False)
    ubicacion_textual = serializers.CharField(max_length=200, allow_blank=True, required=False)
    capacidad = serializers.IntegerField(allow_null=True, required=False)
    precio_noche = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True, required=False)
    tarifa_limpieza = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True, required=False)
    descuento_porcentaje = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True, required=False)
    descuento_min_noches = serializers.IntegerField(allow_null=True, required=False)
    servicios = serializers.ListField(child=serializers.IntegerField(), required=False)
    servicios_adicionales = AdicionalSerializer(many=True, required=False)
    reglas = serializers.ListField(child=serializers.CharField(max_length=200, allow_blank=True), required=False)
    imagenes = serializers.ListField(child=serializers.CharField(max_length=500), required=False)


class PublicacionSalida(serializers.ModelSerializer):
    ciudad_nombre = serializers.CharField(source="ciudad.nombre", default=None)
    tipo_nombre = serializers.CharField(source="tipo_alojamiento.nombre", default=None)
    politica_nombre = serializers.CharField(source="politica.nombre", default=None)
    servicios = serializers.SerializerMethodField()
    servicios_adicionales = serializers.SerializerMethodField()
    reglas = serializers.SerializerMethodField()
    imagenes = serializers.SerializerMethodField()
    revisiones = serializers.SerializerMethodField()
    faltantes = serializers.SerializerMethodField()

    class Meta:
        model = Publicacion
        fields = [
            "id", "anfitrion", "titulo", "descripcion", "ciudad", "ciudad_nombre", "tipo_alojamiento", "tipo_nombre",
            "politica", "politica_nombre", "ubicacion_textual", "capacidad", "precio_noche", "tarifa_limpieza",
            "descuento_porcentaje", "descuento_min_noches", "estado", "servicios", "servicios_adicionales", "reglas",
            "imagenes", "revisiones", "faltantes", "creada", "actualizada",
        ]

    def get_servicios(self, p):
        return list(p.servicios.values("id", "nombre"))

    def get_servicios_adicionales(self, p):
        return [{"id": a.id, "nombre": a.nombre, "precio": a.precio} for a in p.servicios_adicionales.filter(activo=True)]

    def get_reglas(self, p):
        return [{"descripcion": r.descripcion, "orden": r.orden} for r in p.reglas.all()]

    def get_imagenes(self, p):
        return [{"ruta": i.ruta, "orden": i.orden} for i in p.imagenes.all()]

    def get_revisiones(self, p):
        return [{"accion": r.accion, "observacion": r.observacion, "fecha": r.fecha, "administrador": r.administrador_id} for r in p.revisiones.all()]

    def get_faltantes(self, p):
        return services.faltantes(p) if p.estado == EstadoPublicacion.BORRADOR else []


class PublicacionLista(serializers.ModelSerializer):
    ciudad_nombre = serializers.CharField(source="ciudad.nombre", default=None)
    tipo_nombre = serializers.CharField(source="tipo_alojamiento.nombre", default=None)

    class Meta:
        model = Publicacion
        fields = ["id", "anfitrion", "titulo", "ciudad", "ciudad_nombre", "tipo_alojamiento", "tipo_nombre", "precio_noche", "estado", "actualizada"]


def _salida(p):
    return PublicacionSalida(Publicacion.objects.get(pk=p.pk)).data


# ---------------------------------------------------------------- Anfitrión

class Publicaciones(APIView):
    """POST /catalogo/publicaciones (RF-D-ALO-01.1). Se crea como BORRADOR."""

    permission_classes = [EsAnfitrion]

    def post(self, request):
        s = PublicacionEntrada(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(_salida(services.crear(request.user, s.validated_data)), status=status.HTTP_201_CREATED)


class MisPublicaciones(ListAPIView):
    """GET /catalogo/mis-publicaciones?estado= (RF-D-ALO-02.1)."""

    permission_classes = [EsAnfitrion]
    serializer_class = PublicacionLista

    def get_queryset(self):
        return services.mis_publicaciones(self.request.user, self.request.query_params.get("estado"))


class PublicacionDetalle(APIView):
    """GET y PATCH /catalogo/publicaciones/{id}: anfitrión dueño o administrador (RF-D-ALO-02.1, ADM-01.1)."""

    permission_classes = [EsAnfitrionOAdministrador]

    def get(self, request, pk):
        return Response(_salida(services.obtener(request.user, pk)))

    def patch(self, request, pk):
        s = PublicacionEntrada(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        return Response(_salida(services.actualizar(request.user, pk, s.validated_data)))


class _CambioEstado(APIView):
    permission_classes = [EsAnfitrionOAdministrador]
    destino: str = ""

    def post(self, request, pk):
        return Response(_salida(services.cambiar_estado(request.user, pk, self.destino)))


class Pausar(_CambioEstado):
    destino = EstadoPublicacion.PAUSADA


class Reactivar(_CambioEstado):
    destino = EstadoPublicacion.ACTIVA


class EnviarRevision(_CambioEstado):
    """POST /catalogo/publicaciones/{id}/enviar-revision (RF-D-ALO-01.2)."""

    permission_classes = [EsAnfitrion]
    destino = EstadoPublicacion.PENDIENTE_REVISION


class CalendarioEntrada(serializers.Serializer):
    fecha_inicio = serializers.DateField()
    fecha_fin = serializers.DateField()
    tipo = serializers.ChoiceField(choices=TipoPeriodo.choices)


class Calendario(APIView):
    """GET y POST /catalogo/publicaciones/{id}/calendario (RF-D-ALO-02.2)."""

    permission_classes = [EsAnfitrion]

    def get(self, request, pk):
        desde = serializers.DateField().to_internal_value(request.query_params.get("desde") or date.today().isoformat())
        hasta = serializers.DateField().to_internal_value(request.query_params.get("hasta") or (desde + timedelta(days=90)).isoformat())
        return Response(services.calendario(request.user, pk, desde, hasta))

    def post(self, request, pk):
        s = CalendarioEntrada(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        return Response(services.modificar_calendario(request.user, pk, d["fecha_inicio"], d["fecha_fin"], d["tipo"]))


class Catalogos(APIView):
    """GET /catalogo/ciudades · /tipos-alojamiento · /servicios (todos)."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    clave = ""

    def get(self, request):
        return Response(services.catalogos()[self.clave])


# ---------------------------------------------------------------- Administrador

class PublicacionesAdmin(ListAPIView):
    """GET /admin/publicaciones?estado= : todas menos borradores (apoya RF-D-ADM-01.1)."""

    permission_classes = [EsAdministrador]
    serializer_class = PublicacionLista

    def get_queryset(self):
        return services.listar_admin(self.request.query_params.get("estado"))


class RevisionEntrada(serializers.Serializer):
    accion = serializers.ChoiceField(choices=["APROBAR", "DEVOLVER"])
    observacion = serializers.CharField(required=False, allow_blank=True)


class RevisionAdmin(APIView):
    """POST /admin/publicaciones/{id}/revision (RF-D-ADM-01.1)."""

    permission_classes = [EsAdministrador]

    def post(self, request, pk):
        s = RevisionEntrada(data=request.data)
        s.is_valid(raise_exception=True)
        p = services.revisar(request.user, pk, s.validated_data["accion"], s.validated_data.get("observacion"))
        return Response(_salida(p))


class BloqueoAdmin(APIView):
    """POST y DELETE /admin/publicaciones/{id}/bloqueo (RF-D-ADM-01.2)."""

    permission_classes = [EsAdministrador]

    def post(self, request, pk):
        return Response(_salida(services.bloquear(request.user, pk, request.data.get("motivo", ""))))

    def delete(self, request, pk):
        return Response(_salida(services.desbloquear(request.user, pk)))
