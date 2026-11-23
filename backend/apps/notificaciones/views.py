"""Vistas REST de SRV-07 Notificaciones (HU-16). Cada usuario con sesión ve solo sus avisos."""

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comun.permisos import RequierePermiso

from . import services


class Bandeja(APIView):
    """GET /notificaciones: primero las no leídas y luego por fecha (CA-16.2), con el conteo de no leídas."""

    permission_classes = [RequierePermiso("notificaciones.ver")]

    def get(self, request):
        return Response(services.consultar_bandeja(request.user))


class MarcarLeida(APIView):
    """POST /notificaciones/{id}/leida."""

    permission_classes = [RequierePermiso("notificaciones.ver")]

    def post(self, request, pk):
        return Response(services.marcar_leida(request.user, pk))


class MarcarTodas(APIView):
    """POST /notificaciones/leidas: marca todas como leídas."""

    permission_classes = [RequierePermiso("notificaciones.ver")]

    def post(self, request):
        return Response({"marcadas": services.marcar_todas_leidas(request.user)})
