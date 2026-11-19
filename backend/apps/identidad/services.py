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
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auditoria import services as auditoria
from apps.comun.errores import Conflicto, ErrorNegocio, NoEncontrado, SinPermiso

from .models import RestriccionUsuario, RolUsuario, TokenRecuperacion, Usuario

ROLES_REGISTRO = (RolUsuario.HUESPED, RolUsuario.ANFITRION)


# ---------------------------------------------------------------- consultas para otros servicios

def datos_usuario(usuario_id: int) -> dict | None:
    u = Usuario.objects.filter(pk=usuario_id).first()
    return _dict(u) if u else None


def nombres(ids) -> dict[int, str]:
    return dict(Usuario.objects.filter(pk__in=set(ids)).values_list("id", "nombre_completo"))


def _vigentes(ahora=None):
    """Restricciones vigentes en este momento (misma regla que RestriccionUsuario.esta_vigente)."""
    ahora = ahora or timezone.now()
    return RestriccionUsuario.objects.filter(fecha_inicio__lte=ahora).filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gt=ahora))


def cuentas_activas(ids) -> set[int]:
    """Usuarios con la cuenta activa y sin restricción vigente (sus publicaciones son visibles, CA-04.3)."""
    ids = set(ids)
    restringidos = set(_vigentes().filter(usuario_id__in=ids).values_list("usuario_id", flat=True))
    return set(Usuario.objects.filter(pk__in=ids - restringidos, activa=True).values_list("id", flat=True))


def usuarios_registrados(desde=None, hasta=None, rol=None, activa=None, restringida=None) -> list[dict]:
    """Para el reporte de usuarios (RF-D-ADM-05.2)."""
    qs = Usuario.objects.all().order_by("-fecha_registro")
    if desde:
        qs = qs.filter(fecha_registro__date__gte=desde)
    if hasta:
        qs = qs.filter(fecha_registro__date__lte=hasta)
    if rol:
        qs = qs.filter(rol=rol)
    if activa is not None:
        qs = qs.filter(activa=activa)
    vigentes = {r.usuario_id: r for r in _vigentes().filter(usuario__in=qs)}
    lista = [{**_dict(u, u.id in vigentes), "motivo_restriccion": vigentes[u.id].motivo if u.id in vigentes else None} for u in qs]
    return [u for u in lista if restringida is None or u["restringida"] == restringida]


def conteo_por_rol(hasta=None) -> dict[str, int]:
    qs = Usuario.objects.all()
    if hasta:
        qs = qs.filter(fecha_registro__date__lte=hasta)
    base = {r: 0 for r in RolUsuario.values}
    base.update(dict(qs.values_list("rol").annotate(n=Count("id"))))
    return base


def restriccion_vigente(usuario_id: int) -> RestriccionUsuario | None:
    """La cuenta está restringida mientras exista una restricción vigente (no hay columna de estado)."""
    return _vigentes().filter(usuario_id=usuario_id).first()


def usuarios_para_admin(rol: str | None = None, q: str | None = None) -> list[dict]:
    """HU-21: cuentas para el administrador, con activa, restringida y el motivo de la restricción vigente."""
    qs = Usuario.objects.all().order_by("nombre_completo", "id")
    if rol:
        qs = qs.filter(rol=rol)
    if q and q.strip():
        qs = qs.filter(Q(nombre_completo__icontains=q.strip()) | Q(correo__icontains=q.strip()))
    vigentes = {r.usuario_id: r for r in _vigentes().filter(usuario__in=qs)}
    return [{
        **_dict(u, u.id in vigentes),
        "motivo_restriccion": vigentes[u.id].motivo if u.id in vigentes else None,
        "restriccion_hasta": vigentes[u.id].fecha_fin if u.id in vigentes else None,
    } for u in qs]


# ---------------------------------------------------------------- CU-USU-01 Registrarse

def registrar(*, nombre_completo, correo, telefono, password, rol, acepta_datos, ciudad=None, ip=None) -> Usuario:
    if not acepta_datos:
        raise ErrorNegocio("La autorización de tratamiento de datos es obligatoria.", campo="acepta_datos")
    if rol not in ROLES_REGISTRO:
        raise ErrorNegocio("Solo puedes registrarte como Huésped o Anfitrión.", campo="rol")
    correo = Usuario.objects.normalize_email(correo.strip()).lower()
    if Usuario.objects.filter(correo__iexact=correo).exists():
        raise Conflicto("Este correo ya está registrado.", extra={"campo": "correo"})
    _validar_clave(password, Usuario(correo=correo, nombre_completo=nombre_completo))
    ciudad = _limpiar_ciudad(ciudad)
    with transaction.atomic():
        u = Usuario.registrar(correo, password, rol, nombre_completo=nombre_completo.strip(), telefono=telefono.strip(),
                              ciudad=ciudad)
        auditoria.registrar(u.id, "UsuarioRegistrado", entidad="Usuario", entidad_id=u.id, detalle={"rol": rol}, ip=ip)
    return u


# ---------------------------------------------------------------- CU-USU-02 Iniciar sesión

def iniciar_sesion(correo: str, password: str, ip=None) -> dict:
    u = Usuario.objects.filter(correo__iexact=(correo or "").strip()).first()
    # Los intentos fallidos se registran fuera de transaction.atomic ("transacción propia"):
    # quedan en la auditoría aunque la petición termine en error.
    if not u or not u.iniciar_sesion(correo, password):
        auditoria.registrar(u.id if u else None, "InicioSesion", entidad="Usuario", entidad_id=u.id if u else None,
                            exitoso=False, detalle={"motivo": "Credenciales incorrectas", "correo": (correo or "")[:254]}, ip=ip)
        raise ErrorNegocio("Correo o contraseña incorrectos. Revisa los datos e inténtalo de nuevo.", codigo=401)
    vigente = restriccion_vigente(u.id)
    if vigente:  # CA-02.3, CA-21.1
        auditoria.registrar(u.id, "InicioSesion", entidad="Usuario", entidad_id=u.id, exitoso=False,
                            detalle={"motivo": "Cuenta restringida"}, ip=ip)
        hasta = f" hasta el {timezone.localtime(vigente.fecha_fin):%d/%m/%Y}" if vigente.fecha_fin else ""
        raise ErrorNegocio(
            f"Tu cuenta está restringida por el administrador{hasta}. Motivo: {vigente.motivo}", codigo=403,
            extra={"motivo": vigente.motivo, "fecha_fin": vigente.fecha_fin.isoformat() if vigente.fecha_fin else None},
        )
    reactivada = not u.activa
    with transaction.atomic():
        if reactivada:  # CA-04.4: la cuenta se reactiva al volver a ingresar
            u.reactivar()
        u.last_login = timezone.now()
        u.save(update_fields=["last_login"])
        auditoria.registrar(u.id, "InicioSesion", entidad="Usuario", entidad_id=u.id, detalle={"reactivada": reactivada}, ip=ip)
    refresh = RefreshToken.for_user(u)
    return {"access": str(refresh.access_token), "refresh": str(refresh), "usuario": _dict(u),
            **({"aviso": "Tu cuenta se reactivó. ¡Bienvenido de nuevo!"} if reactivada else {})}


def renovar_sesion(refresh: str) -> dict:
    """Rota el token de renovación (ADR-005). Solo renueva si la cuenta sigue activa y sin restricción
    vigente: así una cuenta restringida o desactivada no recupera la sesión aunque conserve la cookie."""
    if not isinstance(refresh, str) or not refresh:  # RefreshToken(None) no falla: crea un token nuevo y vacío
        raise ErrorNegocio("Tu sesión terminó. Inicia sesión de nuevo.", codigo=401)
    try:
        anterior = RefreshToken(refresh)  # verifica firma, vencimiento y lista negra
    except TokenError as e:
        raise ErrorNegocio("Tu sesión terminó. Inicia sesión de nuevo.", codigo=401) from e
    u = Usuario.objects.filter(pk=int(anterior["user_id"])).first()
    anterior.blacklist()
    if not u or not u.is_active:
        raise ErrorNegocio("Tu sesión terminó. Inicia sesión de nuevo.", codigo=401)
    nuevo = RefreshToken.for_user(u)
    return {"access": str(nuevo.access_token), "refresh": str(nuevo), "usuario": _dict(u)}


def cerrar_sesion(refresh: str, ip=None) -> None:
    """Pone el refresh en la lista negra. Si ya no servía, no hay nada que cerrar."""
    if not isinstance(refresh, str) or not refresh:  # RefreshToken(None) crearía un token nuevo sin usuario
        return
    try:
        token = RefreshToken(refresh)
    except TokenError:
        return
    usuario_id = int(token["user_id"])
    with transaction.atomic():
        token.blacklist()
        auditoria.registrar(usuario_id, "CierreSesion", entidad="Usuario", entidad_id=usuario_id, ip=ip)


def _cerrar_todas_las_sesiones(u: Usuario) -> None:
    for t in OutstandingToken.objects.filter(user=u):
        BlacklistedToken.objects.get_or_create(token=t)


# ---------------------------------------------------------------- CU-USU-03 Recuperar contraseña

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def solicitar_recuperacion(correo: str, ip=None) -> str | None:
    """Crea el enlace de recuperación y devuelve el token en claro (en la base solo queda su hash).
    Si el correo no existe devuelve None."""
    u = Usuario.objects.filter(correo__iexact=(correo or "").strip()).first()
    if not u:
        auditoria.registrar(None, "RecuperacionSolicitada", exitoso=False, detalle={"motivo": "Correo no registrado"}, ip=ip)
        return None
    token = secrets.token_urlsafe(32)
    ahora = timezone.now()
    with transaction.atomic():
        # Un solo enlace vivo por cuenta: los anteriores sin usar dejan de servir.
        TokenRecuperacion.objects.filter(usuario=u, usado_en__isnull=True, vence__gt=ahora).update(vence=ahora)
        TokenRecuperacion.objects.create(
            usuario=u, token_hash=_hash(token), vence=ahora + timedelta(minutes=settings.MINUTOS_ENLACE_RECUPERACION)
        )
        auditoria.registrar(u.id, "RecuperacionSolicitada", entidad="Usuario", entidad_id=u.id, ip=ip)
    # No se envía correo: la recuperación es simulada y el enlace se muestra en pantalla
    # (AMB-08, AMB-12, CA-03.1). La vista lo devuelve en la respuesta.
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
        auditoria.registrar(u.id, "ContrasenaRestablecida", entidad="Usuario", entidad_id=u.id, ip=ip)


# ---------------------------------------------------------------- CU-USU-04 Perfil

def actualizar_perfil(u: Usuario, datos: dict, ip=None) -> Usuario:
    campos = u.actualizar_perfil(**{arg: datos[campo] for arg, campo in (("nombre", "nombre_completo"), ("telefono", "telefono"))
                                    if campo in datos})
    if "ciudad" in datos:  # texto opcional: vacío o null la quita (CA-04.1)
        u.ciudad = _limpiar_ciudad(datos["ciudad"])
        campos.append("ciudad")
    if datos.get("password_nueva"):
        if not u.check_password(datos.get("password_actual") or ""):
            raise ErrorNegocio("La contraseña actual no es correcta.", campo="password_actual")
        _validar_clave(datos["password_nueva"], u)
        u.set_password(datos["password_nueva"])
        campos.append("password")
    if campos:
        with transaction.atomic():
            u.save(update_fields=campos)
            auditoria.registrar(u.id, "PerfilActualizado", entidad="Usuario", entidad_id=u.id, ip=ip,
                                detalle={"campos": [c for c in campos if c != "password"] + (["contraseña"] if "password" in campos else [])})
    return u


# ---------------------------------------------------------------- CU-USU-05 Desactivar cuenta

def desactivar_cuenta(u: Usuario, ip=None) -> None:
    from apps.reservas import services as reservas

    if u.rol == RolUsuario.ADMINISTRADOR:
        auditoria.registrar(u.id, "AccesoDenegado", exitoso=False, detalle={"motivo": "Desactivar cuenta de administrador"}, ip=ip)
        raise SinPermiso("Las cuentas de administrador no se desactivan desde el perfil.")
    pendientes = reservas.reservas_pendientes(u.id, es_anfitrion=u.rol == RolUsuario.ANFITRION)
    if pendientes:  # CA-04.2, CA-04.5
        raise Conflicto(
            "No puedes desactivar tu cuenta: tienes reservas confirmadas o en revisión pendientes.", extra={"reservas": pendientes}
        )
    with transaction.atomic():
        u.desactivar()
        _cerrar_todas_las_sesiones(u)
        auditoria.registrar(u.id, "CuentaDesactivada", entidad="Usuario", entidad_id=u.id, ip=ip)


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
    # RF-D-ADM-02.1: restringir NO modifica la cuenta ni sus reservas; solo crea la restricción.
    # El acceso se corta porque is_active la tiene en cuenta desde la siguiente petición (ADR-005).
    with transaction.atomic():
        r = RestriccionUsuario.objects.create(usuario=u, administrador=admin, motivo=motivo.strip(), fecha_fin=fecha_fin)
        auditoria.registrar(admin.id, "CuentaRestringida", entidad="Usuario", entidad_id=u.id, ip=ip,
                            detalle={"motivo": r.motivo, "fecha_fin": fecha_fin.isoformat() if fecha_fin else None})
    return r


def levantar_restriccion(admin: Usuario, usuario_id: int, ip=None) -> None:
    r = restriccion_vigente(usuario_id)
    if not r:
        raise NoEncontrado("La cuenta no tiene una restricción vigente.")
    with transaction.atomic():  # levantarla pone fecha_fin = ahora
        r.fecha_fin = timezone.now()
        r.save(update_fields=["fecha_fin"])
        auditoria.registrar(admin.id, "RestriccionLevantada", entidad="Usuario", entidad_id=usuario_id, ip=ip)


# ---------------------------------------------------------------- utilidades

def _limpiar_ciudad(ciudad) -> str | None:
    """usuario.ciudad es texto opcional VARCHAR(80) (MOD-01). Vacío o null = sin ciudad."""
    ciudad = (ciudad or "").strip()
    if len(ciudad) > 80:
        raise ErrorNegocio("La ciudad admite máximo 80 caracteres.", campo="ciudad")
    return ciudad or None


def _validar_clave(password: str, usuario: Usuario) -> None:
    if not password or len(password) < 8:
        raise ErrorNegocio("La contraseña debe tener al menos 8 caracteres.", campo="password")
    try:
        validate_password(password, usuario)
    except ValidationError as e:
        raise ErrorNegocio(" ".join(e.messages), campo="password") from e


def _dict(u: Usuario, restringida: bool | None = None) -> dict:
    return {
        "id": u.id, "correo": u.correo, "nombre_completo": u.nombre_completo, "telefono": u.telefono,
        "ciudad": u.ciudad, "rol": u.rol, "activa": u.activa,
        "restringida": u.restringida if restringida is None else restringida,  # derivado de RestriccionUsuario
        "autorizacion_datos": u.autorizacion_datos.isoformat() if u.autorizacion_datos else None,
        "fecha_registro": u.fecha_registro.isoformat() if u.fecha_registro else None,
    }


def a_dict(u: Usuario) -> dict:
    return _dict(u)
