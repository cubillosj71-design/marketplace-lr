"""Interfaz pública de SRV-01 Identidad.

Es el único módulo que otros servicios pueden importar de esta app (junto con
``apps.identidad.permisos``, que trae los permisos por rol para sus vistas).
Nadie fuera de apps.identidad debe importar apps.identidad.models (regla verificada
con import-linter en el pipeline, ADR-001).

Aquí vive la lógica de negocio del módulo USU. Las vistas (views.py) solo
traducen HTTP <-> Python y llaman a estas funciones; así las reglas se pueden
probar sin HTTP y otros servicios pueden reutilizarlas.

Contenido:
- Casos de uso del módulo: registrar_usuario, iniciar_sesion, solicitar_recuperacion,
  restablecer_contrasena, actualizar_perfil, desactivar_cuenta.
- Restricciones del Administrador (RF-D-ADM-02.1): restringir, levantar_restriccion.
- Consultas para otros servicios: anfitriones_ocultos_ids, cuenta_habilitada,
  resumen_usuario, contar_por_rol.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as ErrorValidacionDjango
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.auditoria import services as auditoria
from apps.auditoria.services import Accion
from apps.reservas import services as reservas

from .models import EstadoCuenta, RestriccionUsuario, RolUsuario, TokenRecuperacion, Usuario, normalizar_correo

# Roles que un Visitante puede elegir al registrarse. El Administrador no se
# registra: lo carga el equipo (nota de RF-AN-USU-01).
ROLES_DE_REGISTRO = (RolUsuario.HUESPED, RolUsuario.ANFITRION)

VIGENCIA_ENLACE_RECUPERACION = timedelta(minutes=20)  # RNF-P-SEG-03


# --------------------------------------------------------------------------
# Errores de negocio. Las vistas los convierten en respuestas HTTP; aquí no se
# sabe nada de HTTP.
# --------------------------------------------------------------------------


class ErrorIdentidad(Exception):
    """Regla de negocio incumplida. ``codigo`` es estable y lo usa el front-end."""

    codigo = "error_identidad"

    def __init__(self, mensaje: str, campo: str | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.campo = campo


class CorreoYaRegistrado(ErrorIdentidad):
    codigo = "correo_registrado"


class ContrasenaInvalida(ErrorIdentidad):
    codigo = "contrasena_invalida"


class AutorizacionDatosRequerida(ErrorIdentidad):
    codigo = "autorizacion_datos_requerida"


class CredencialesInvalidas(ErrorIdentidad):
    codigo = "credenciales_invalidas"


class CuentaRestringida(ErrorIdentidad):
    codigo = "cuenta_restringida"


class EnlaceInvalido(ErrorIdentidad):
    codigo = "enlace_invalido"


class EnlaceVencido(ErrorIdentidad):
    codigo = "enlace_vencido"


class EnlaceUsado(ErrorIdentidad):
    codigo = "enlace_usado"


class TieneReservasPendientes(ErrorIdentidad):
    codigo = "reservas_pendientes"


class OperacionNoPermitida(ErrorIdentidad):
    codigo = "operacion_no_permitida"


# --------------------------------------------------------------------------
# HU-01 Registrarse (RF-D-USU-01.1, CU-USU-01)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DatosRegistro:
    nombre_completo: str
    correo: str
    telefono: str
    password: str
    rol: str
    acepta_datos: bool


def registrar_usuario(datos: DatosRegistro, ip: str | None = None) -> Usuario:
    correo = normalizar_correo(datos.correo)

    # El orden de las validaciones sigue el flujo de CU-USU-01 (3a, 4a, 4b).
    if not datos.acepta_datos:
        raise AutorizacionDatosRequerida(
            "Debes aceptar la autorización para el tratamiento de tus datos personales (Ley 1581 de 2012).",
            campo="acepta_datos",
        )
    if datos.rol not in ROLES_DE_REGISTRO:
        raise OperacionNoPermitida("Solo puedes registrarte como Huésped o como Anfitrión.", campo="rol")
    if Usuario.objects.filter(correo=correo).exists():
        raise CorreoYaRegistrado("Ya existe una cuenta con este correo electrónico.", campo="correo")
    _validar_contrasena(datos.password)

    try:
        with transaction.atomic():
            usuario = Usuario.objects.create_user(
                correo=correo,
                password=datos.password,
                nombre_completo=datos.nombre_completo.strip(),
                telefono=datos.telefono.strip(),
                rol=datos.rol,
                acepta_datos_en=timezone.now(),
            )
            auditoria.registrar(
                Accion.REGISTRO, exitoso=True, actor_id=usuario.pk, entidad="usuario",
                entidad_id=usuario.pk, detalle={"rol": usuario.rol}, ip=ip,
            )
    except IntegrityError:
        # Dos registros simultáneos con el mismo correo: el primero gana por la
        # restricción UNIQUE de la base y el segundo llega aquí.
        raise CorreoYaRegistrado("Ya existe una cuenta con este correo electrónico.", campo="correo") from None
    return usuario


def _validar_contrasena(password: str, usuario: Usuario | None = None) -> None:
    """Aplica AUTH_PASSWORD_VALIDATORS (en settings: mínimo 8 caracteres)."""
    try:
        validate_password(password, user=usuario)
    except ErrorValidacionDjango as error:
        raise ContrasenaInvalida(" ".join(error.messages), campo="password") from None


# --------------------------------------------------------------------------
# HU-02 Iniciar sesión (RF-D-USU-01.2, CU-USU-02)
# --------------------------------------------------------------------------

# Hash de una contraseña cualquiera. Si el correo no existe se verifica contra
# este hash para que la respuesta tarde lo mismo que con un correo real; así no
# se puede averiguar qué correos están registrados midiendo el tiempo.
_HASH_DE_RELLENO = None


def _hash_de_relleno() -> str:
    global _HASH_DE_RELLENO
    if _HASH_DE_RELLENO is None:
        usuario = Usuario()
        usuario.set_password(secrets.token_urlsafe(16))
        _HASH_DE_RELLENO = usuario.password
    return _HASH_DE_RELLENO


def iniciar_sesion(correo: str, password: str, ip: str | None = None) -> Usuario:
    """Verifica las credenciales y devuelve el usuario con la cuenta lista para usar.

    No usa django.contrib.auth.authenticate() porque esa función rechaza igual
    una cuenta restringida que una desactivada, y aquí cada una tiene un
    tratamiento distinto: la restringida se rechaza con su propio mensaje
    (CA-02.3) y la desactivada se reactiva (flujo 4c de CU-USU-02).
    """
    correo = normalizar_correo(correo)
    usuario = Usuario.objects.filter(correo=correo).first()

    if usuario is None:
        Usuario(password=_hash_de_relleno()).check_password(password)
        auditoria.registrar(Accion.INICIO_SESION, exitoso=False, detalle={"motivo": "correo_no_registrado", "correo": correo}, ip=ip)
        raise CredencialesInvalidas("El correo o la contraseña son incorrectos.")

    if not usuario.check_password(password):
        auditoria.registrar(
            Accion.INICIO_SESION, exitoso=False, actor_id=usuario.pk, entidad="usuario",
            entidad_id=usuario.pk, detalle={"motivo": "contrasena_incorrecta"}, ip=ip,
        )
        # Mismo mensaje que con un correo inexistente, por la misma razón.
        raise CredencialesInvalidas("El correo o la contraseña son incorrectos.")

    if usuario.estado == EstadoCuenta.RESTRINGIDA:
        auditoria.registrar(
            Accion.INICIO_SESION, exitoso=False, actor_id=usuario.pk, entidad="usuario",
            entidad_id=usuario.pk, detalle={"motivo": "cuenta_restringida"}, ip=ip,
        )
        raise CuentaRestringida("Tu cuenta está restringida por la administración de la plataforma.")

    with transaction.atomic():
        if usuario.estado == EstadoCuenta.DESACTIVADA:
            usuario.estado = EstadoCuenta.ACTIVA
            auditoria.registrar(Accion.REACTIVACION, exitoso=True, actor_id=usuario.pk, entidad="usuario", entidad_id=usuario.pk, ip=ip)
        usuario.last_login = timezone.now()
        usuario.save(update_fields=["estado", "last_login"])
        auditoria.registrar(Accion.INICIO_SESION, exitoso=True, actor_id=usuario.pk, entidad="usuario", entidad_id=usuario.pk, ip=ip)
    return usuario


def cuenta_puede_renovar_sesion(usuario_id: int) -> bool:
    """Una sesión solo se renueva si la cuenta sigue ACTIVA (ADR-005)."""
    return Usuario.objects.filter(pk=usuario_id, estado=EstadoCuenta.ACTIVA).exists()


def revocar_sesiones(usuario: Usuario) -> None:
    """Invalida todos los tokens de renovación del usuario.

    Se usa al cambiar la contraseña, al desactivar y al restringir: quien tenga
    una sesión abierta en otro equipo ya no puede renovarla.
    """
    pendientes = OutstandingToken.objects.filter(user=usuario).exclude(blacklistedtoken__isnull=False)
    BlacklistedToken.objects.bulk_create([BlacklistedToken(token=t) for t in pendientes], ignore_conflicts=True)


# --------------------------------------------------------------------------
# HU-03 Recuperar la contraseña (RF-D-USU-01.3, CU-USU-03, RNF-P-SEG-03)
# --------------------------------------------------------------------------


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def solicitar_recuperacion(correo: str, ip: str | None = None) -> str | None:
    """Crea un enlace de recuperación y devuelve el token en claro, o None si el
    correo no está registrado.

    El token en claro solo existe en esta respuesta: en la base queda su hash.
    Como la recuperación es simulada (AMB-08), la vista lo muestra en pantalla
    en lugar de enviarlo por correo.
    """
    correo = normalizar_correo(correo)
    usuario = Usuario.objects.filter(correo=correo).first()
    if usuario is None:
        auditoria.registrar(Accion.SOLICITUD_RECUPERACION, exitoso=False, detalle={"motivo": "correo_no_registrado", "correo": correo}, ip=ip)
        return None

    token = secrets.token_urlsafe(32)  # 256 bits de azar: imposible de adivinar
    ahora = timezone.now()
    with transaction.atomic():
        # Al pedir un enlace nuevo, los anteriores sin usar dejan de servir:
        # así solo hay un enlace vivo por cuenta.
        TokenRecuperacion.objects.filter(usuario=usuario, usado_en__isnull=True, vence__gt=ahora).update(vence=ahora)
        TokenRecuperacion.objects.create(
            usuario=usuario, token_hash=_hash_token(token), creado=ahora, vence=ahora + VIGENCIA_ENLACE_RECUPERACION,
        )
        auditoria.registrar(Accion.SOLICITUD_RECUPERACION, exitoso=True, actor_id=usuario.pk, entidad="usuario", entidad_id=usuario.pk, ip=ip)
    return token


def verificar_enlace(token: str) -> None:
    """Lanza EnlaceInvalido, EnlaceUsado o EnlaceVencido si el enlace no sirve (CA-03.2, CA-03.3)."""
    _verificar(TokenRecuperacion.objects.filter(token_hash=_hash_token(token)).first())


def _verificar(registro: TokenRecuperacion | None) -> TokenRecuperacion:
    if registro is None:
        raise EnlaceInvalido("El enlace de recuperación no es válido.")
    if registro.usado_en is not None:
        raise EnlaceUsado("Este enlace ya se usó. Solicita uno nuevo.")
    if timezone.now() >= registro.vence:
        raise EnlaceVencido("El enlace venció: solo sirve durante 20 minutos. Solicita uno nuevo.")
    return registro


def restablecer_contrasena(token: str, nueva: str, ip: str | None = None) -> None:
    try:
        with transaction.atomic():
            # select_for_update bloquea la fila: si el mismo enlace llega dos
            # veces al mismo tiempo, la segunda petición espera y luego ve que
            # ya se usó. Sin el bloqueo, las dos podrían cambiar la contraseña.
            registro = _verificar(
                TokenRecuperacion.objects.select_for_update().select_related("usuario").filter(token_hash=_hash_token(token)).first()
            )
            usuario = registro.usuario
            _validar_contrasena(nueva, usuario)
            usuario.set_password(nueva)
            usuario.save(update_fields=["password"])
            registro.usado_en = timezone.now()
            registro.save(update_fields=["usado_en"])
            revocar_sesiones(usuario)
            auditoria.registrar(Accion.CAMBIO_CONTRASENA, exitoso=True, actor_id=usuario.pk, entidad="usuario", entidad_id=usuario.pk, ip=ip)
    except ErrorIdentidad as error:
        # Fuera del bloque atómico, para que el intento fallido quede guardado.
        auditoria.registrar(Accion.CAMBIO_CONTRASENA, exitoso=False, detalle={"motivo": error.codigo}, ip=ip)
        raise


# --------------------------------------------------------------------------
# HU-04 Mantener el perfil (RF-D-USU-01.4, CU-USU-04, CU-USU-05)
# --------------------------------------------------------------------------


def actualizar_perfil(usuario: Usuario, *, nombre_completo: str | None = None, telefono: str | None = None, ip: str | None = None) -> Usuario:
    cambios = {}
    if nombre_completo is not None and nombre_completo.strip() != usuario.nombre_completo:
        cambios["nombre_completo"] = nombre_completo.strip()
    if telefono is not None and telefono.strip() != usuario.telefono:
        cambios["telefono"] = telefono.strip()
    if not cambios:
        return usuario

    with transaction.atomic():
        for campo, valor in cambios.items():
            setattr(usuario, campo, valor)
        usuario.save(update_fields=list(cambios))
        # Se registra qué campos cambiaron, no sus valores: el registro dura
        # 10 años y no debe acumular datos personales (Ley 1581).
        auditoria.registrar(
            Accion.ACTUALIZACION_PERFIL, exitoso=True, actor_id=usuario.pk, entidad="usuario",
            entidad_id=usuario.pk, detalle={"campos": sorted(cambios)}, ip=ip,
        )
    return usuario


def desactivar_cuenta(usuario: Usuario, ip: str | None = None) -> None:
    if usuario.rol == RolUsuario.ADMINISTRADOR:
        # Nota de la sección 2: la plataforma nunca debe quedar sin administración.
        raise OperacionNoPermitida("La cuenta de Administrador no se puede desactivar.")

    if reservas.tiene_reservas_confirmadas_pendientes(usuario.pk):
        auditoria.registrar(
            Accion.DESACTIVACION, exitoso=False, actor_id=usuario.pk, entidad="usuario",
            entidad_id=usuario.pk, detalle={"motivo": "reservas_pendientes"}, ip=ip,
        )
        raise TieneReservasPendientes(
            "No puedes desactivar tu cuenta mientras tengas reservas confirmadas pendientes, "
            "como huésped o en tus alojamientos."
        )

    with transaction.atomic():
        usuario.estado = EstadoCuenta.DESACTIVADA
        usuario.save(update_fields=["estado"])
        revocar_sesiones(usuario)
        auditoria.registrar(Accion.DESACTIVACION, exitoso=True, actor_id=usuario.pk, entidad="usuario", entidad_id=usuario.pk, ip=ip)


# --------------------------------------------------------------------------
# Restricciones del Administrador (RF-D-ADM-02.1, HU-21). Viven aquí porque
# SRV-01 es dueño de las tablas usuario y restriccion_usuario.
# --------------------------------------------------------------------------


def restringir(usuario_id: int, administrador: Usuario, motivo: str, ip: str | None = None) -> RestriccionUsuario:
    motivo = (motivo or "").strip()
    if not motivo:
        raise OperacionNoPermitida("Indica el motivo de la restricción.", campo="motivo")

    with transaction.atomic():
        usuario = Usuario.objects.select_for_update().filter(pk=usuario_id).first()
        if usuario is None:
            raise OperacionNoPermitida("El usuario no existe.")
        if usuario.rol == RolUsuario.ADMINISTRADOR:
            raise OperacionNoPermitida("No se puede restringir una cuenta de Administrador.")
        if usuario.estado == EstadoCuenta.RESTRINGIDA:
            raise OperacionNoPermitida("La cuenta ya está restringida.")

        restriccion = RestriccionUsuario.objects.create(usuario=usuario, administrador=administrador, motivo=motivo)
        usuario.estado = EstadoCuenta.RESTRINGIDA
        usuario.save(update_fields=["estado"])
        revocar_sesiones(usuario)
        auditoria.registrar(
            Accion.RESTRICCION, exitoso=True, actor_id=administrador.pk, entidad="usuario",
            entidad_id=usuario.pk, detalle={"motivo": motivo}, ip=ip,
        )
    return restriccion


def levantar_restriccion(usuario_id: int, administrador: Usuario, ip: str | None = None) -> None:
    with transaction.atomic():
        restriccion = (
            RestriccionUsuario.objects.select_for_update().select_related("usuario")
            .filter(usuario_id=usuario_id, fecha_fin__isnull=True).first()
        )
        if restriccion is None:
            raise OperacionNoPermitida("La cuenta no tiene una restricción vigente.")
        restriccion.fecha_fin = timezone.now()
        restriccion.save(update_fields=["fecha_fin"])
        usuario = restriccion.usuario
        usuario.estado = EstadoCuenta.ACTIVA
        usuario.save(update_fields=["estado"])
        auditoria.registrar(Accion.LEVANTAR_RESTRICCION, exitoso=True, actor_id=administrador.pk, entidad="usuario", entidad_id=usuario.pk, ip=ip)


# --------------------------------------------------------------------------
# Consultas para otros servicios (sección 3.3 del diseño). Devuelven datos
# simples (ids, diccionarios), nunca objetos del modelo, para que nadie fuera
# de Identidad dependa de cómo están hechas sus tablas.
# --------------------------------------------------------------------------


def anfitriones_ocultos_ids() -> list[int]:
    """Anfitriones cuyas publicaciones no deben aparecer en las búsquedas:
    cuentas desactivadas (RF-D-USU-01.4) o restringidas (RF-D-ADM-02.1).
    La usa SRV-03 Búsqueda."""
    return list(
        Usuario.objects.filter(rol=RolUsuario.ANFITRION).exclude(estado=EstadoCuenta.ACTIVA).values_list("pk", flat=True)
    )


def cuenta_habilitada(usuario_id: int) -> bool:
    return Usuario.objects.filter(pk=usuario_id, estado=EstadoCuenta.ACTIVA).exists()


def resumen_usuario(usuario_id: int) -> dict | None:
    return Usuario.objects.filter(pk=usuario_id).values("id", "nombre_completo", "correo", "rol", "estado").first()


def contar_por_rol() -> dict[str, int]:
    """Usuarios por rol, para el tablero de SRV-09 (RF-D-ADM-05.1)."""
    filas = Usuario.objects.values("rol").annotate(total=Count("id"))
    conteo = {rol: 0 for rol in RolUsuario.values}
    conteo.update({fila["rol"]: fila["total"] for fila in filas})
    return conteo
