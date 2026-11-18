"""Vistas REST de SRV-04 Reservas: tarifa de servicio, calendario, cotización y reserva con pago."""

from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comun.eventos import ip_de
from apps.comun.permisos import EsAdministrador, EsAnfitrion, EsHuesped

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


# ---------------------------------------------------------------- calendario (RF-D-ALO-02.2)

class CalendarioEntrada(serializers.Serializer):
    fecha_inicio = serializers.DateField()
    fecha_fin = serializers.DateField()
    tipo = serializers.ChoiceField(choices=["DISPONIBLE", "NO_DISPONIBLE"])


class RangoCalendario(serializers.Serializer):
    desde = serializers.DateField(required=False)
    hasta = serializers.DateField(required=False)


class Calendario(APIView):
    """GET y POST /catalogo/publicaciones/{id}/calendario. La ruta se conserva para el frontend,
    pero desde MAL-28 la atiende MOD-04 Reservas (periodo_calendario es de Reservas)."""

    permission_classes = [EsAnfitrion]

    def get(self, request, pk):
        s = RangoCalendario(data=request.query_params)
        s.is_valid(raise_exception=True)
        desde = s.validated_data.get("desde") or timezone.localdate()
        hasta = s.validated_data.get("hasta") or desde + timedelta(days=90)
        return Response(services.calendario(request.user, pk, desde, hasta))

    def post(self, request, pk):
        s = CalendarioEntrada(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        return Response(services.modificar_calendario(request.user, pk, d["fecha_inicio"], d["fecha_fin"], d["tipo"]))


# ---------------------------------------------------------------- HU-12 Cotizar

class CotizacionEntrada(serializers.Serializer):
    publicacion = serializers.IntegerField()
    fecha_llegada = serializers.DateField()
    fecha_salida = serializers.DateField()
    num_huespedes = serializers.IntegerField(min_value=1)
    adicionales = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)


class Cotizaciones(APIView):
    """POST /reservas/cotizaciones (RF-D-RES-02.1). Solo Huésped; un Visitante recibe 401 (CA-05.1)."""

    permission_classes = [EsHuesped]

    def post(self, request):
        s = CotizacionEntrada(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        c = services.cotizar(request.user, d["publicacion"], d["fecha_llegada"], d["fecha_salida"], d["num_huespedes"],
                             d["adicionales"], ip=ip_de(request))
        return Response(services.cotizacion_dict(c), status=status.HTTP_201_CREATED)


class CotizacionDetalle(APIView):
    """GET /reservas/cotizaciones/{id}: el desglose de una cotización propia."""

    permission_classes = [EsHuesped]

    def get(self, request, pk):
        return Response(services.cotizacion_dict(services.obtener_cotizacion(request.user, pk)))


# ---------------------------------------------------------------- HU-13 Reservar y pagar

class ReservaEntrada(serializers.Serializer):
    cotizacion = serializers.IntegerField()
    clave_idempotencia = serializers.UUIDField()
    medio_pago = serializers.CharField(max_length=255)


class Reservas(APIView):
    """POST /reservas (RF-D-RES-02.2). 201 si se creó; 200 si la clave ya tenía reserva (CA-13.4);
    409 si las fechas se ocuparon o la cotización cambió; 402 si el pago no se aprobó."""

    permission_classes = [EsHuesped]

    def post(self, request):
        s = ReservaEntrada(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        reserva, creada = services.reservar(request.user, d["cotizacion"], d["clave_idempotencia"], d["medio_pago"], ip=ip_de(request))
        return Response(reserva, status=status.HTTP_201_CREATED if creada else status.HTTP_200_OK)
