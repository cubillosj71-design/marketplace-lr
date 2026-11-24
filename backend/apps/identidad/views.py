"""Vistas REST de SRV-01 Identidad (sección 3.4: /api/v1/identidad/...).

Sesión (ADR-005 y C4 nivel 2): el token de ACCESO va en el cuerpo y la aplicación
web lo guarda en memoria; el token de RENOVACIÓN va en una cookie httpOnly que
JavaScript no puede leer. Así, si un script malicioso llega a correr en la página,
no puede llevarse la sesión de 24 horas. La cookie solo viaja a /api/v1/identidad/
y solo desde el mismo sitio (SameSite=Strict), lo que también bloquea el CSRF.
"""

from django.conf import settings
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comun import rbac
from apps.comun.entrada import leer_texto
from apps.comun.errores import ErrorNegocio
from apps.comun.eventos import obtener_ip
from apps.comun.permisos import RequierePermiso

from . import services


class RegistroSerializer(serializers.Serializer):
    """Datos del formulario de registro (POST /identidad/registro). El rol solo puede ser HUESPED o ANFITRION."""
    nombre_completo = serializers.CharField(max_length=120)
    correo = serializers.EmailField(max_length=254)
    telefono = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True)
    rol = serializers.ChoiceField(choices=["HUESPED", "ANFITRION"])
    acepta_datos = serializers.BooleanField()
    ciudad = serializers.CharField(max_length=80, required=False, allow_null=True, allow_blank=True)  # texto opcional


class Registro(APIView):
    """POST /identidad/registro (RF-D-USU-01.1)."""

    permission_classes = [RequierePermiso("cuenta.registrar")]
    throttle_scope = "registro"

    def post(self, request):
        s = RegistroSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        u = services.registrar_usuario(
            nombre_completo=d["nombre_completo"], correo=d["correo"], telefono=d["telefono"], password=d["password"],
            rol=d["rol"], acepta_datos=d["acepta_datos"], ciudad=d.get("ciudad"), ip=obtener_ip(request),
        )
        return Response(services.convertir_usuario_a_dict(u), status=status.HTTP_201_CREATED)


COOKIE = settings.IDENTIDAD_COOKIE_RENOVACION


def _responder_con_sesion(sesion: dict) -> Response:
    """Saca el refresh del cuerpo y lo pone en la cookie httpOnly."""
    refresh = sesion.pop("refresh")
    respuesta = Response(sesion)
    respuesta.set_cookie(
        COOKIE["nombre"], refresh,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=COOKIE["ruta"], secure=COOKIE["segura"], httponly=True, samesite="Strict",
    )
    return respuesta


def _quitar_cookie(respuesta: Response) -> Response:
    """Borra la cookie httpOnly con el token de renovación (al cerrar sesión o si ya no sirve)."""
    respuesta.delete_cookie(COOKIE["nombre"], path=COOKIE["ruta"], samesite="Strict")
    return respuesta


def _obtener_refresh(request) -> str:
    # La cookie es la vía normal. El cuerpo se acepta para clientes sin navegador (pruebas, Postman).
    """Token de renovación de la petición: de la cookie httpOnly o, para clientes sin navegador (pruebas, Postman), del cuerpo."""
    return request.COOKIES.get(COOKIE["nombre"]) or leer_texto(request, "refresh")


class Token(APIView):
    """POST /identidad/token (RF-D-USU-01.2): devuelve access y usuario; el refresh va en la cookie."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "inicio_sesion"

    def post(self, request):
        return _responder_con_sesion(
            services.iniciar_sesion(leer_texto(request, "correo"), leer_texto(request, "password"), ip=obtener_ip(request))
        )


class TokenRenovar(APIView):
    """POST /identidad/token/renovar: rota el refresh (el anterior queda en la lista negra) y
    devuelve un access nuevo y el usuario. La aplicación web la llama al cargar la página para
    recuperar la sesión, porque el access en memoria se pierde al recargar."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        try:
            sesion = services.renovar_sesion(_obtener_refresh(request))
        except ErrorNegocio as error:
            respuesta = Response({"detalle": error.detalle}, status=error.codigo)
            return _quitar_cookie(respuesta)
        return _responder_con_sesion(sesion)


class Salir(APIView):
    """POST /identidad/salir: pone el refresh en la lista negra y borra la cookie.
    No exige un access vigente: cerrar sesión debe funcionar aunque ya haya vencido."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        services.cerrar_sesion(_obtener_refresh(request), ip=obtener_ip(request))
        return _quitar_cookie(Response(status=status.HTTP_204_NO_CONTENT))


class Recuperacion(APIView):
    """POST /identidad/recuperacion (RF-D-USU-01.3, CA-03.1).

    El enlace llega al correo de la cuenta; la API nunca lo devuelve. La respuesta es la misma (202 y el mismo
    mensaje) exista o no la cuenta, y el correo sale en segundo plano para que tampoco el tiempo de respuesta lo
    revele.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "recuperacion"

    def post(self, request):
        services.solicitar_recuperacion(leer_texto(request, "correo"), ip=obtener_ip(request))
        minutos = settings.MINUTOS_ENLACE_RECUPERACION
        return Response({"detalle": "Si el correo está registrado, te enviamos un enlace para cambiar tu contraseña. "
                                    f"Revisa tu bandeja de entrada y la carpeta de spam. El enlace sirve una vez y vence en {minutos} minutos."},
                        status=status.HTTP_202_ACCEPTED)


class RecuperacionToken(APIView):
    """GET /identidad/recuperacion/{token}: estado del enlace. POST: nueva contraseña."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    # Límite propio y más amplio: abrir y usar un enlace hace varias peticiones seguidas,
    # y adivinar un token de 256 bits es imposible aunque no hubiera límite.
    throttle_scope = "recuperacion_enlace"

    def get(self, request, token):
        return Response({"estado": services.consultar_estado_enlace(token)})

    def post(self, request, token):
        services.restablecer_clave(token, leer_texto(request, "password"), ip=obtener_ip(request))
        return Response({"detalle": "Tu contraseña se actualizó. Ya puedes iniciar sesión."})


class Permisos(APIView):
    """GET /identidad/permisos (RF-D-USU-02.1): el rol y los permisos de quien llama, según apps.comun.rbac.
    Sin sesión responde los del VISITANTE. Es pública porque describe la propia matriz."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"rol": rbac.obtener_rol(request.user), "permisos": sorted(rbac.obtener_permisos(request.user))})


class Roles(APIView):
    """GET /identidad/roles (RF-D-USU-02.1): la matriz completa de apps.comun.rbac, para la pantalla "Roles y
    permisos". Solo la ve el Administrador (usuarios.ver): describe cómo está protegida la plataforma, y eso no
    es información para huéspedes, anfitriones ni visitantes. Cada quien ve sus propios permisos en /permisos."""

    permission_classes = [RequierePermiso("usuarios.ver")]

    def get(self, request):
        orden = [rbac.VISITANTE, "HUESPED", "ANFITRION", "ADMINISTRADOR"]
        return Response({"roles": [{"rol": r, "permisos": sorted(rbac.PERMISOS[r])} for r in orden]})


class PerfilSerializer(serializers.Serializer):
    """Datos que se pueden cambiar en Mi perfil (PATCH /identidad/perfil). Todos son opcionales.

    Para cambiar la contraseña hay que mandar password_actual y password_nueva.
    """
    nombre_completo = serializers.CharField(max_length=120, required=False)
    telefono = serializers.CharField(max_length=20, required=False)
    ciudad = serializers.CharField(max_length=80, required=False, allow_null=True, allow_blank=True)  # texto opcional
    password_actual = serializers.CharField(required=False, write_only=True)
    password_nueva = serializers.CharField(required=False, write_only=True)


class Perfil(APIView):
    """GET y PATCH /identidad/perfil (RF-D-USU-01.4). El correo y el rol no se cambian."""

    permission_classes = [RequierePermiso("perfil.gestionar")]

    def get(self, request):
        return Response(services.convertir_usuario_a_dict(request.user))

    def patch(self, request):
        s = PerfilSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        u = services.actualizar_perfil(request.user, s.validated_data, ip=obtener_ip(request))
        return Response(services.convertir_usuario_a_dict(u))


class Desactivar(APIView):
    """POST /identidad/perfil/desactivar (CU-USU-05)."""

    permission_classes = [RequierePermiso("cuenta.desactivar")]

    def post(self, request):
        services.desactivar_cuenta(request.user, ip=obtener_ip(request))
        return Response({"detalle": "Tu cuenta quedó desactivada. Se reactiva cuando vuelvas a iniciar sesión."})


class RestriccionSerializer(serializers.Serializer):
    """Datos para restringir una cuenta: motivo obligatorio y fecha de fin opcional."""
    motivo = serializers.CharField()
    fecha_fin = serializers.DateTimeField(required=False, allow_null=True)


class RestriccionAdmin(APIView):
    """POST y DELETE /admin/usuarios/{id}/restriccion (RF-D-ADM-02.1)."""

    permission_classes = [RequierePermiso("usuarios.restringir")]

    def post(self, request, usuario_id):
        s = RestriccionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        r = services.restringir_usuario(request.user, usuario_id, s.validated_data["motivo"], s.validated_data.get("fecha_fin"), ip=obtener_ip(request))
        return Response(
            {"id": r.id, "usuario": usuario_id, "motivo": r.motivo, "fecha_inicio": r.fecha_inicio, "fecha_fin": r.fecha_fin},
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request, usuario_id):
        services.levantar_restriccion(request.user, usuario_id, ip=obtener_ip(request))
        return Response(status=status.HTTP_204_NO_CONTENT)


class UsuariosAdmin(APIView):
    """GET /admin/usuarios?rol&q (HU-21): buscar por nombre o correo, con activa, restringida y motivo."""

    permission_classes = [RequierePermiso("usuarios.ver")]

    def get(self, request):
        rol = request.query_params.get("rol") or None
        if rol and rol not in ("HUESPED", "ANFITRION", "ADMINISTRADOR"):
            raise ErrorNegocio("El rol debe ser HUESPED, ANFITRION o ADMINISTRADOR.", campo="rol")
        return Response(services.listar_usuarios_para_admin(rol, request.query_params.get("q")))
