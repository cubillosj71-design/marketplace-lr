"""Vistas REST de SRV-01 Identidad (rutas de la sección 3.4 del diseño).

Cada vista hace tres cosas y nada más: valida la forma de la entrada con un
serializador, llama a una función de services.py y convierte el resultado (o el
error de negocio) en una respuesta HTTP.

Sesión (ADR-005 y C4 nivel 2):
- El token de ACCESO (30 min) va en el cuerpo de la respuesta. El front-end lo
  guarda en memoria, nunca en localStorage, porque cualquier script inyectado
  en la página puede leer localStorage.
- El token de RENOVACIÓN (24 h) va en una cookie httpOnly: JavaScript no la
  puede leer, así que un script malicioso no puede robar la sesión larga. El
  navegador la envía solo a /api/v1/identidad/ y solo desde el mismo sitio
  (SameSite=Strict), lo que también impide que otra página la use (CSRF).
"""

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auditoria import services as auditoria
from apps.auditoria.services import Accion

from . import services
from .models import Usuario
from .permisos import EsAdministrador, EsHuespedOAnfitrion
from .serializers import (
    InicioSesionSerializer,
    NuevaContrasenaSerializer,
    PerfilSerializer,
    RegistroSerializer,
    RestriccionSerializer,
    SolicitudRecuperacionSerializer,
    UsuarioSerializer,
)

COOKIE = settings.IDENTIDAD_COOKIE_RENOVACION

# Código de error de negocio -> estado HTTP.
ESTADO_HTTP = {
    "correo_registrado": status.HTTP_409_CONFLICT,
    "reservas_pendientes": status.HTTP_409_CONFLICT,
    "credenciales_invalidas": status.HTTP_401_UNAUTHORIZED,
    "cuenta_restringida": status.HTTP_403_FORBIDDEN,
}


def respuesta_de_error(error: services.ErrorIdentidad) -> Response:
    cuerpo = {"codigo": error.codigo, "mensaje": error.mensaje}
    if error.campo:
        cuerpo["campo"] = error.campo
    return Response(cuerpo, status=ESTADO_HTTP.get(error.codigo, status.HTTP_400_BAD_REQUEST))


def poner_cookie_renovacion(respuesta: Response, refresh: str) -> None:
    respuesta.set_cookie(
        COOKIE["nombre"],
        refresh,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=COOKIE["ruta"],
        secure=COOKIE["segura"],
        httponly=True,
        samesite="Strict",
    )


def quitar_cookie_renovacion(respuesta: Response) -> None:
    respuesta.delete_cookie(COOKIE["nombre"], path=COOKIE["ruta"], samesite="Strict")


def respuesta_de_sesion(usuario: Usuario, refresh: RefreshToken, estado: int = status.HTTP_200_OK) -> Response:
    respuesta = Response({"access": str(refresh.access_token), "usuario": UsuarioSerializer(usuario).data}, status=estado)
    poner_cookie_renovacion(respuesta, str(refresh))
    return respuesta


class VistaPublica(APIView):
    """Rutas que usa quien no ha iniciado sesión. Se desactiva la autenticación
    para que un token vencido en el encabezado no cause un 401 aquí."""

    permission_classes = [AllowAny]
    authentication_classes: list = []


# ---------------------------------------------------------------- HU-01


class RegistroVista(VistaPublica):
    throttle_scope = "registro"

    def post(self, request):
        entrada = RegistroSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        try:
            usuario = services.registrar_usuario(
                services.DatosRegistro(**entrada.validated_data), ip=auditoria.ip_de_la_peticion(request)
            )
        except services.ErrorIdentidad as error:
            return respuesta_de_error(error)
        return Response(
            {"mensaje": "Tu cuenta quedó creada. Ya puedes iniciar sesión.", "usuario": UsuarioSerializer(usuario).data},
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------- HU-02


class TokenVista(VistaPublica):
    """Iniciar sesión: devuelve el token de acceso y pone la cookie de renovación."""

    throttle_scope = "inicio_sesion"

    def post(self, request):
        entrada = InicioSesionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        try:
            usuario = services.iniciar_sesion(**entrada.validated_data, ip=auditoria.ip_de_la_peticion(request))
        except services.ErrorIdentidad as error:
            return respuesta_de_error(error)
        return respuesta_de_sesion(usuario, RefreshToken.for_user(usuario))


class RenovarVista(VistaPublica):
    """Entrega un token de acceso nuevo usando la cookie de renovación.

    El front-end la llama al cargar la página (para recuperar la sesión, porque
    el token de acceso en memoria se pierde al recargar) y cuando un token de
    acceso vence. Con ROTATE_REFRESH_TOKENS, cada renovación cambia también la
    cookie y la anterior queda en la lista negra: un token de renovación robado
    sirve una sola vez.
    """

    def post(self, request):
        valor = request.COOKIES.get(COOKIE["nombre"])
        sin_sesion = Response({"codigo": "sin_sesion", "mensaje": "Inicia sesión para continuar."}, status=status.HTTP_401_UNAUTHORIZED)
        if not valor:
            return sin_sesion
        try:
            anterior = RefreshToken(valor)  # verifica firma, vencimiento y lista negra
        except TokenError:
            quitar_cookie_renovacion(sin_sesion)
            return sin_sesion

        usuario = Usuario.objects.filter(pk=anterior["user_id"]).first()
        if usuario is None or not services.cuenta_puede_renovar_sesion(usuario.pk):
            anterior.blacklist()
            quitar_cookie_renovacion(sin_sesion)
            return sin_sesion

        anterior.blacklist()
        return respuesta_de_sesion(usuario, RefreshToken.for_user(usuario))


class SalirVista(VistaPublica):
    """Cerrar sesión: el token de renovación pasa a la lista negra."""

    def post(self, request):
        valor = request.COOKIES.get(COOKIE["nombre"])
        if valor:
            try:
                token = RefreshToken(valor)
                token.blacklist()
                auditoria.registrar(Accion.CIERRE_SESION, exitoso=True, actor_id=token["user_id"], ip=auditoria.ip_de_la_peticion(request))
            except TokenError:
                pass  # ya no servía: no hay nada que invalidar
        respuesta = Response(status=status.HTTP_204_NO_CONTENT)
        quitar_cookie_renovacion(respuesta)
        return respuesta


# ---------------------------------------------------------------- HU-03


class RecuperacionVista(VistaPublica):
    throttle_scope = "recuperacion"

    def post(self, request):
        entrada = SolicitudRecuperacionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        token = services.solicitar_recuperacion(entrada.validated_data["correo"], ip=auditoria.ip_de_la_peticion(request))
        if token is None:
            return Response(
                {"mensaje": "No encontramos una cuenta con ese correo electrónico.", "enlace": None},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Recuperación simulada (AMB-08): el enlace se muestra en pantalla.
        return Response(
            {
                "mensaje": "Usa este enlace para definir tu nueva contraseña. Sirve una sola vez durante 20 minutos.",
                "enlace": f"/recuperar/{token}",
            }
        )


class RecuperacionTokenVista(VistaPublica):
    """GET: ¿el enlace todavía sirve? (para avisar apenas se abre, CA-03.2). POST: definir la nueva contraseña."""

    # Límite propio y más amplio que el de pedir enlaces: abrir y usar un enlace
    # hace varias peticiones seguidas, y adivinar un token de 256 bits es
    # imposible aunque no hubiera límite.
    throttle_scope = "recuperacion_enlace"

    def get(self, request, token: str):
        try:
            services.verificar_enlace(token)
        except services.ErrorIdentidad as error:
            return respuesta_de_error(error)
        return Response({"valido": True})

    def post(self, request, token: str):
        entrada = NuevaContrasenaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        try:
            services.restablecer_contrasena(token, entrada.validated_data["password"], ip=auditoria.ip_de_la_peticion(request))
        except services.ErrorIdentidad as error:
            return respuesta_de_error(error)
        return Response({"mensaje": "Tu contraseña quedó actualizada. Ya puedes iniciar sesión."})


# ---------------------------------------------------------------- HU-04


class PerfilVista(APIView):
    permission_classes = [EsHuespedOAnfitrion]

    def get(self, request):
        return Response(UsuarioSerializer(request.user).data)

    def patch(self, request):
        entrada = PerfilSerializer(data=request.data, partial=True)
        entrada.is_valid(raise_exception=True)
        usuario = services.actualizar_perfil(request.user, **entrada.validated_data, ip=auditoria.ip_de_la_peticion(request))
        return Response(UsuarioSerializer(usuario).data)


class DesactivarVista(APIView):
    permission_classes = [EsHuespedOAnfitrion]

    def post(self, request):
        try:
            services.desactivar_cuenta(request.user, ip=auditoria.ip_de_la_peticion(request))
        except services.ErrorIdentidad as error:
            return respuesta_de_error(error)
        respuesta = Response({"mensaje": "Tu cuenta quedó desactivada. Para reactivarla, vuelve a iniciar sesión."})
        quitar_cookie_renovacion(respuesta)
        return respuesta


# ---------------------------------------------------------------- HU-21 (administración)


class RestriccionVista(APIView):
    permission_classes = [EsAdministrador]

    def post(self, request, usuario_id: int):
        entrada = RestriccionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        try:
            services.restringir(usuario_id, request.user, entrada.validated_data["motivo"], ip=auditoria.ip_de_la_peticion(request))
        except services.ErrorIdentidad as error:
            return respuesta_de_error(error)
        return Response({"mensaje": "La cuenta quedó restringida."}, status=status.HTTP_201_CREATED)

    def delete(self, request, usuario_id: int):
        try:
            services.levantar_restriccion(usuario_id, request.user, ip=auditoria.ip_de_la_peticion(request))
        except services.ErrorIdentidad as error:
            return respuesta_de_error(error)
        return Response(status=status.HTTP_204_NO_CONTENT)
