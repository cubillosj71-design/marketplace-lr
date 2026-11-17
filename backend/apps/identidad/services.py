"""Interfaz pública de SRV-01 Identidad.

Es el único módulo que otros servicios pueden importar de esta app.
Nadie fuera de apps.identidad debe importar apps.identidad.models (regla verificada
con import-linter en el pipeline, ADR-001).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.comun.errores import Conflicto, ErrorNegocio, NoEncontrado, SinPermiso
from apps.comun.eventos import publicar

from .models import EstadoCuenta, RestriccionUsuario, RolUsuario, TokenRecuperacion, Usuario

ROLES_REGISTRO = (RolUsuario.HUESPED, RolUsuario.ANFITRION)


# ---------------------------------------------------------------- consultas para otros servicios

def datos_usuario(usuario_id: int) -> dict | None:
    u = Usuario.objects.filter(pk=usuario_id).first()
    return _dict(u) if u else None


def nombres(ids) -> dict[int, str]:
    return dict(Usuario.objects.filter(pk__in=set(ids)).values_list("id", "nombre_completo"))


def cuentas_activas(ids) -> set[int]:
    """Usuarios cuya cuenta está ACTIVA (sus publicaciones son visibles, CA-04.3)."""
    return set(Usuario.objects.filter(pk__in=set(ids), estado=EstadoCuenta.ACTIVA).values_list("id", flat=True))


def usuarios_registrados(desde=None, hasta=None, rol=None, estado=None) -> list[dict]:
    """Para el reporte de usuarios (RF-D-ADM-05.2)."""
    qs = Usuario.objects.all().order_by("-fecha_registro")
    if desde:
        qs = qs.filter(fecha_registro__date__gte=desde)
    if hasta:
        qs = qs.filter(fecha_registro__date__lte=hasta)
    if rol:
        qs = qs.filter(rol=rol)
    if estado:
        qs = qs.filter(estado=estado)
    vigentes = {r.usuario_id: r for r in RestriccionUsuario.objects.filter(usuario__in=qs) if r.esta_vigente()}
    return [{**_dict(u), "motivo_restriccion": vigentes[u.id].motivo if u.id in vigentes else None} for u in qs]


def conteo_por_rol(hasta=None) -> dict[str, int]:
    qs = Usuario.objects.all()
    if hasta:
        qs = qs.filter(fecha_registro__date__lte=hasta)
    base = {r: 0 for r in RolUsuario.values}
    base.update(dict(qs.values_list("rol").annotate(n=Count("id"))))
    return base


def restriccion_vigente(usuario_id: int) -> RestriccionUsuario | None:
    ahora = timezone.now()
    return next((r for r in RestriccionUsuario.objects.filter(usuario_id=usuario_id) if r.esta_vigente(ahora)), None)


def sincronizar_estado(usuario_id: int) -> None:
    """DA-04: el estado RESTRINGIDA se deriva de la restricción vigente."""
    u = Usuario.objects.filter(pk=usuario_id).only("estado").first()
    if not u:
        return
    vigente = restriccion_vigente(usuario_id)
    if vigente and u.estado != EstadoCuenta.RESTRINGIDA:
        Usuario.objects.filter(pk=usuario_id).update(estado=EstadoCuenta.RESTRINGIDA)
    elif not vigente and u.estado == EstadoCuenta.RESTRINGIDA:
        Usuario.objects.filter(pk=usuario_id).update(estado=EstadoCuenta.ACTIVA)


# ---------------------------------------------------------------- CU-USU-01 Registrarse

def registrar(*, nombre_completo, correo, telefono, password, rol, acepta_datos, ciudad_id=None, ip=None) -> Usuario:
    if not acepta_datos:
        raise ErrorNegocio("La autorización de tratamiento de datos es obligatoria.", campo="acepta_datos")
    if rol not in ROLES_REGISTRO:
        raise ErrorNegocio("Solo puedes registrarte como Huésped o Anfitrión.", campo="rol")
    correo = Usuario.objects.normalize_email(correo.strip()).lower()
    if Usuario.objects.filter(correo__iexact=correo).exists():
        raise Conflicto("Este correo ya está registrado.", extra={"campo": "correo"})
    _validar_clave(password, Usuario(correo=correo, nombre_completo=nombre_completo))
    _validar_ciudad(ciudad_id)
    with transaction.atomic():
        u = Usuario.objects.create_user(
            correo=correo, password=password, nombre_completo=nombre_completo.strip(), telefono=telefono.strip(),
            rol=rol, ciudad_id=ciudad_id, acepta_datos_en=timezone.now(),
        )
        publicar("UsuarioRegistrado", usuario_id=u.id, entidad="Usuario", entidad_id=u.id, detalle={"rol": rol}, ip=ip)
    return u


# ---------------------------------------------------------------- CU-USU-02 Iniciar sesión

def iniciar_sesion(correo: str, password: str, ip=None) -> dict:
    u = Usuario.objects.filter(correo__iexact=(correo or "").strip()).first()
    if not u or not u.check_password(password or ""):
        publicar("InicioSesion", usuario_id=u.id if u else None, entidad="Usuario", entidad_id=u.id if u else None,
                 resultado="FALLO", detalle={"motivo": "Credenciales incorrectas", "correo": (correo or "")[:254]}, ip=ip)
        raise ErrorNegocio("Correo o contraseña incorrectos. Revisa los datos e inténtalo de nuevo.", codigo=401)
    sincronizar_estado(u.id)
    vigente = restriccion_vigente(u.id)
    if vigente:
        publicar("InicioSesion", usuario_id=u.id, entidad="Usuario", entidad_id=u.id, resultado="FALLO",
                 detalle={"motivo": "Cuenta restringida"}, ip=ip)
        hasta = f" hasta el {timezone.localtime(vigente.fecha_fin):%d/%m/%Y}" if vigente.fecha_fin else ""
        raise ErrorNegocio(
            f"Tu cuenta está restringida por el administrador{hasta}. Motivo: {vigente.motivo}", codigo=403,
            extra={"motivo": vigente.motivo, "fecha_fin": vigente.fecha_fin.isoformat() if vigente.fecha_fin else None},
        )
    u.refresh_from_db()
    reactivada = u.estado == EstadoCuenta.DESACTIVADA
    with transaction.atomic():
        if reactivada:  # CA-04.4: la cuenta se reactiva al volver a ingresar
            u.estado = EstadoCuenta.ACTIVA
        u.last_login = timezone.now()
        u.save(update_fields=["estado", "last_login"])
        publicar("InicioSesion", usuario_id=u.id, entidad="Usuario", entidad_id=u.id,
                 detalle={"reactivada": reactivada}, ip=ip)
    refresh = RefreshToken.for_user(u)
    return {"access": str(refresh.access_token), "refresh": str(refresh), "usuario": _dict(u),
            **({"aviso": "Tu cuenta se reactivó. ¡Bienvenido de nuevo!"} if reactivada else {})}


def cerrar_sesion(refresh: str) -> None:
    try:
        RefreshToken(refresh).blacklist()
    except Exception as e:  # noqa: BLE001
        raise ErrorNegocio("El token de renovación no es válido.") from e


def _cerrar_todas_las_sesiones(u: Usuario) -> None:
    for t in OutstandingToken.objects.filter(user=u):
        BlacklistedToken.objects.get_or_create(token=t)


# ---------------------------------------------------------------- CU-USU-03 Recuperar contraseña

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def solicitar_recuperacion(correo: str, ip=None) -> str | None:
    """Crea el enlace y lo envía por correo. Devuelve el token (solo para pruebas y desarrollo).
    Si el correo no existe no se revela: la respuesta de la API es la misma."""
    u = Usuario.objects.filter(correo__iexact=(correo or "").strip()).first()
    if not u:
        publicar("RecuperacionSolicitada", resultado="FALLO", detalle={"motivo": "Correo no registrado"}, ip=ip)
        return None
    token = secrets.token_urlsafe(32)
    TokenRecuperacion.objects.create(
        usuario=u, token_hash=_hash(token), vence=timezone.now() + timedelta(minutes=settings.MINUTOS_ENLACE_RECUPERACION)
    )
    enlace = f"{settings.FRONTEND_URL}/#/restablecer/{token}"
    send_mail(
        "Recupera tu contraseña · Alojamientos LR",
        f"Hola, {u.nombre_completo}.\n\nPara crear una nueva contraseña abre este enlace. "
        f"Sirve una sola vez y vence en {settings.MINUTOS_ENLACE_RECUPERACION} minutos:\n\n{enlace}\n\n"
        "Si no lo pediste, ignora este mensaje.",
        settings.DEFAULT_FROM_EMAIL, [u.correo], fail_silently=True,
    )
    publicar("RecuperacionSolicitada", usuario_id=u.id, entidad="Usuario", entidad_id=u.id, ip=ip)
    return token


def estado_enlace(token: str) -> str:
    t = TokenRecuperacion.objects.filter(token_hash=_hash(token)).first()
    if not t:
        return "inexistente"
    if t.usado_en:
        return "usado"
    return "valido" if t.es_valido() else "vencido"


def restablecer_clave(token: str, password: str, ip=None) -> None:
    with transaction.atomic():
        t = TokenRecuperacion.objects.select_for_update().filter(token_hash=_hash(token)).first()
        if not t:
            raise ErrorNegocio("El enlace no es válido.", codigo=404)
        if t.usado_en:
            raise ErrorNegocio("Este enlace ya se usó. Solicita uno nuevo.", codigo=410)
        if not t.es_valido():
            raise ErrorNegocio("Este enlace venció. Solicita uno nuevo.", codigo=410)
        u = Usuario.objects.get(pk=t.usuario_id)
        _validar_clave(password, u)
        u.set_password(password)
        u.save(update_fields=["password"])
        t.usado_en = timezone.now()
        t.save(update_fields=["usado_en"])
        _cerrar_todas_las_sesiones(u)
        publicar("ContrasenaRestablecida", usuario_id=u.id, entidad="Usuario", entidad_id=u.id, ip=ip)


# ---------------------------------------------------------------- CU-USU-04 Perfil

def actualizar_perfil(u: Usuario, datos: dict, ip=None) -> Usuario:
    campos = []
    for campo in ("nombre_completo", "telefono"):
        if campo in datos:
            valor = (datos[campo] or "").strip()
            if not valor:
                raise ErrorNegocio("Este dato no puede quedar vacío.", campo=campo)
            setattr(u, campo, valor)
            campos.append(campo)
    if "ciudad" in datos:
        _validar_ciudad(datos["ciudad"])
        u.ciudad_id = datos["ciudad"]
        campos.append("ciudad")
    if datos.get("password_nueva"):
        if not u.check_password(datos.get("password_actual") or ""):
            raise ErrorNegocio("La contraseña actual no es correcta.", campo="password_actual")
        _validar_clave(datos["password_nueva"], u)
        u.set_password(datos["password_nueva"])
        campos.append("password")
    if campos:
        u.save(update_fields=campos)
        publicar("PerfilActualizado", usuario_id=u.id, entidad="Usuario", entidad_id=u.id,
                 detalle={"campos": [c for c in campos if c != "password"] + (["contraseña"] if "password" in campos else [])}, ip=ip)
    return u


# ---------------------------------------------------------------- CU-USU-05 Desactivar cuenta

def desactivar_cuenta(u: Usuario, ip=None) -> None:
    from apps.reservas import services as reservas

    if u.rol == RolUsuario.ADMINISTRADOR:
        publicar("AccesoDenegado", usuario_id=u.id, resultado="FALLO", detalle={"motivo": "Desactivar cuenta de administrador"}, ip=ip)
        raise SinPermiso("Las cuentas de administrador no se desactivan desde el perfil.")
    pendientes = reservas.confirmadas_pendientes(u.id, es_anfitrion=u.rol == RolUsuario.ANFITRION)
    if pendientes:  # CA-04.2
        raise Conflicto(
            "No puedes desactivar tu cuenta: tienes reservas CONFIRMADAS pendientes.", extra={"reservas": pendientes}
        )
    with transaction.atomic():
        u.estado = EstadoCuenta.DESACTIVADA
        u.save(update_fields=["estado"])
        _cerrar_todas_las_sesiones(u)
        publicar("CuentaDesactivada", usuario_id=u.id, entidad="Usuario", entidad_id=u.id, ip=ip)


# ---------------------------------------------------------------- RF-D-ADM-02.1 Restringir

def restringir(admin: Usuario, usuario_id: int, motivo: str, fecha_fin=None, ip=None) -> RestriccionUsuario:
    u = Usuario.objects.filter(pk=usuario_id).first()
    if not u:
        raise NoEncontrado("El usuario no existe.")
    if u.rol == RolUsuario.ADMINISTRADOR:
        raise ErrorNegocio("No se puede restringir una cuenta de administrador.")
    if not (motivo or "").strip():
        raise ErrorNegocio("Escribe el motivo de la restricción.", campo="motivo")
    if fecha_fin and fecha_fin <= timezone.now():
        raise ErrorNegocio("La fecha de fin debe ser futura.", campo="fecha_fin")
    if restriccion_vigente(u.id):
        raise Conflicto("La cuenta ya tiene una restricción vigente.")
    with transaction.atomic():  # DA-04: restricción y estado en la misma transacción
        r = RestriccionUsuario.objects.create(usuario=u, administrador=admin, motivo=motivo.strip(), fecha_fin=fecha_fin)
        u.estado = EstadoCuenta.RESTRINGIDA
        u.save(update_fields=["estado"])
        _cerrar_todas_las_sesiones(u)
        publicar("CuentaRestringida", usuario_id=admin.id, entidad="Usuario", entidad_id=u.id,
                 detalle={"motivo": r.motivo, "fecha_fin": fecha_fin.isoformat() if fecha_fin else None}, ip=ip)
    return r


def levantar_restriccion(admin: Usuario, usuario_id: int, ip=None) -> None:
    r = restriccion_vigente(usuario_id)
    if not r:
        raise NoEncontrado("La cuenta no tiene una restricción vigente.")
    with transaction.atomic():
        r.fecha_fin = timezone.now()
        r.save(update_fields=["fecha_fin"])
        Usuario.objects.filter(pk=usuario_id).update(estado=EstadoCuenta.ACTIVA)
        publicar("RestriccionLevantada", usuario_id=admin.id, entidad="Usuario", entidad_id=usuario_id, ip=ip)


# ---------------------------------------------------------------- utilidades

def _validar_ciudad(ciudad_id) -> None:
    """La ciudad es una llave foránea al catálogo. Se valida por la relación del modelo,
    sin importar Catálogo (Identidad solo depende de Reservas, sección 3.3)."""
    if ciudad_id is None:
        return
    Ciudad = Usuario._meta.get_field("ciudad").related_model
    if not Ciudad.objects.filter(pk=ciudad_id).exists():
        raise ErrorNegocio("La ciudad no existe.", campo="ciudad")


def _validar_clave(password: str, usuario: Usuario) -> None:
    if not password or len(password) < 8:
        raise ErrorNegocio("La contraseña debe tener al menos 8 caracteres.", campo="password")
    try:
        validate_password(password, usuario)
    except ValidationError as e:
        raise ErrorNegocio(" ".join(e.messages), campo="password") from e


def _dict(u: Usuario) -> dict:
    return {
        "id": u.id, "correo": u.correo, "nombre_completo": u.nombre_completo, "telefono": u.telefono,
        "ciudad": u.ciudad_id, "rol": u.rol, "estado": u.estado,
        "acepta_datos_en": u.acepta_datos_en.isoformat() if u.acepta_datos_en else None,
        "fecha_registro": u.fecha_registro.isoformat() if u.fecha_registro else None,
    }


def a_dict(u: Usuario) -> dict:
    return _dict(u)
