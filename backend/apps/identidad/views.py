"""Vistas REST de SRV-01 Identidad (sección 3.4: /api/v1/identidad/...)."""

from django.conf import settings
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from apps.comun.eventos import ip_de
from apps.comun.permisos import EsAdministrador

from . import services


class RegistroSerializer(serializers.Serializer):
    nombre_completo = serializers.CharField(max_length=120)
    correo = serializers.EmailField(max_length=254)
    telefono = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True)
    rol = serializers.ChoiceField(choices=["HUESPED", "ANFITRION"])
    acepta_datos = serializers.BooleanField()
    ciudad = serializers.IntegerField(required=False, allow_null=True)


class Registro(APIView):
    """POST /identidad/registro (RF-D-USU-01.1)."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        s = RegistroSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        u = services.registrar(
            nombre_completo=d["nombre_completo"], correo=d["correo"], telefono=d["telefono"], password=d["password"],
            rol=d["rol"], acepta_datos=d["acepta_datos"], ciudad_id=d.get("ciudad"), ip=ip_de(request),
        )
        return Response(services.a_dict(u), status=status.HTTP_201_CREATED)


class Token(APIView):
    """POST /identidad/token (RF-D-USU-01.2): devuelve access, refresh y los datos del usuario."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        return Response(services.iniciar_sesion(request.data.get("correo"), request.data.get("password"), ip=ip_de(request)))


class TokenRenovar(TokenRefreshView):
    """POST /identidad/token/renovar: rota el refresh y pone el anterior en la lista negra (ADR-005)."""


class Salir(APIView):
    """POST /identidad/salir: pone el refresh en la lista negra."""

    def post(self, request):
        services.cerrar_sesion(request.data.get("refresh", ""))
        return Response(status=status.HTTP_204_NO_CONTENT)


class Recuperacion(APIView):
    """POST /identidad/recuperacion (RF-D-USU-01.3). La respuesta es igual exista o no el correo."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        token = services.solicitar_recuperacion(request.data.get("correo", ""), ip=ip_de(request))
        cuerpo = {"detalle": "Si el correo está registrado, te enviamos un enlace que vence en 20 minutos."}
        if settings.DEBUG and token:  # solo en desarrollo, para probar sin servidor de correo
            cuerpo["enlace_desarrollo"] = f"{settings.FRONTEND_URL}/#/restablecer/{token}"
        return Response(cuerpo, status=status.HTTP_202_ACCEPTED)


class RecuperacionToken(APIView):
    """GET /identidad/recuperacion/{token}: estado del enlace. POST: nueva contraseña."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request, token):
        return Response({"estado": services.estado_enlace(token)})

    def post(self, request, token):
        services.restablecer_clave(token, request.data.get("password", ""), ip=ip_de(request))
        return Response({"detalle": "Tu contraseña se actualizó. Ya puedes iniciar sesión."})


class PerfilSerializer(serializers.Serializer):
    nombre_completo = serializers.CharField(max_length=120, required=False)
    telefono = serializers.CharField(max_length=20, required=False)
    ciudad = serializers.IntegerField(required=False, allow_null=True)
    password_actual = serializers.CharField(required=False, write_only=True)
    password_nueva = serializers.CharField(required=False, write_only=True)


class Perfil(APIView):
    """GET y PATCH /identidad/perfil (RF-D-USU-01.4). El correo y el rol no se cambian."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.a_dict(request.user))

    def patch(self, request):
        s = PerfilSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        u = services.actualizar_perfil(request.user, s.validated_data, ip=ip_de(request))
        return Response(services.a_dict(u))


class Desactivar(APIView):
    """POST /identidad/perfil/desactivar (CU-USU-05)."""

    def post(self, request):
        services.desactivar_cuenta(request.user, ip=ip_de(request))
        return Response({"detalle": "Tu cuenta quedó desactivada. Se reactiva cuando vuelvas a iniciar sesión."})


class RestriccionSerializer(serializers.Serializer):
    motivo = serializers.CharField()
    fecha_fin = serializers.DateTimeField(required=False, allow_null=True)


class RestriccionAdmin(APIView):
    """POST y DELETE /admin/usuarios/{id}/restriccion (RF-D-ADM-02.1)."""

    permission_classes = [EsAdministrador]

    def post(self, request, usuario_id):
        s = RestriccionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        r = services.restringir(request.user, usuario_id, s.validated_data["motivo"], s.validated_data.get("fecha_fin"), ip=ip_de(request))
        return Response(
            {"id": r.id, "usuario": usuario_id, "motivo": r.motivo, "fecha_inicio": r.fecha_inicio, "fecha_fin": r.fecha_fin},
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request, usuario_id):
        services.levantar_restriccion(request.user, usuario_id, ip=ip_de(request))
        return Response(status=status.HTTP_204_NO_CONTENT)
