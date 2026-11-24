"""Interfaz pública de SRV-01 Identidad.

Es el único módulo que otros servicios pueden importar de esta app.
Nadie fuera de apps.identidad debe importar apps.identidad.models (regla verificada
con import-linter en el pipeline, ADR-001).
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import threading
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.mail import EmailMultiAlternatives
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.html import escape
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auditoria import services as auditoria
from apps.comun.errores import Conflicto, ErrorNegocio, NoEncontrado, SinPermiso

from .models import RestriccionUsuario, RolUsuario, TokenRecuperacion, Usuario, validar_telefono

log = logging.getLogger("marketplace")
ROLES_REGISTRO = (RolUsuario.HUESPED, RolUsuario.ANFITRION)


# ---------------------------------------------------------------- consultas para otros servicios

def obtener_datos_usuario(usuario_id: int) -> dict | None:
    """Datos públicos de un usuario para otros módulos (nunca la contraseña).

    Args:
        usuario_id: id del usuario.

    Returns:
        El diccionario del usuario, o None si no existe.
    """
    u = Usuario.objects.filter(pk=usuario_id).first()
    return _serializar_usuario(u) if u else None


def obtener_nombres_usuarios(ids) -> dict[int, str]:
    """Nombres completos de varios usuarios en una sola consulta (para listas y reportes).

    Args:
        ids: ids de los usuarios.

    Returns:
        {id: nombre_completo}.
    """
    return dict(Usuario.objects.filter(pk__in=set(ids)).values_list("id", "nombre_completo"))


def _filtrar_vigentes(ahora=None):
    """Restricciones vigentes en este momento (misma regla que RestriccionUsuario.esta_vigente)."""
    ahora = ahora or timezone.now()
    return RestriccionUsuario.objects.filter(fecha_inicio__lte=ahora).filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gt=ahora))


def listar_cuentas_activas(ids) -> set[int]:
    """Usuarios con la cuenta activa y sin restricción vigente (sus publicaciones son visibles, CA-04.3)."""
    ids = set(ids)
    restringidos = set(_filtrar_vigentes().filter(usuario_id__in=ids).values_list("usuario_id", flat=True))
    return set(Usuario.objects.filter(pk__in=ids - restringidos, activa=True).values_list("id", flat=True))


def listar_usuarios_registrados(desde=None, hasta=None, rol=None, activa=None, restringida=None) -> list[dict]:
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
    vigentes = {r.usuario_id: r for r in _filtrar_vigentes().filter(usuario__in=qs)}
    lista = [{**_serializar_usuario(u, u.id in vigentes), "motivo_restriccion": vigentes[u.id].motivo if u.id in vigentes else None} for u in qs]
    return [u for u in lista if restringida is None or u["restringida"] == restringida]


def contar_usuarios_por_rol(hasta=None) -> dict[str, int]:
    """Cuenta las cuentas por rol, opcionalmente hasta una fecha de registro.

    Args:
        hasta: fecha de corte (inclusive); sin ella, todas.

    Returns:
        {rol: cantidad} con los tres roles.
    """
    qs = Usuario.objects.all()
    if hasta:
        qs = qs.filter(fecha_registro__date__lte=hasta)
    base = {r: 0 for r in RolUsuario.values}
    base.update(dict(qs.values_list("rol").annotate(n=Count("id"))))
    return base


def obtener_restriccion_vigente(usuario_id: int) -> RestriccionUsuario | None:
    """La cuenta está restringida mientras exista una restricción vigente (no hay columna de estado)."""
    return _filtrar_vigentes().filter(usuario_id=usuario_id).first()


def listar_usuarios_para_admin(rol: str | None = None, q: str | None = None) -> list[dict]:
    """HU-21: cuentas para el administrador, con activa, restringida y el motivo de la restricción vigente."""
    qs = Usuario.objects.all().order_by("nombre_completo", "id")
    if rol:
        qs = qs.filter(rol=rol)
    if q and q.strip():
        qs = qs.filter(Q(nombre_completo__icontains=q.strip()) | Q(correo__icontains=q.strip()))
    vigentes = {r.usuario_id: r for r in _filtrar_vigentes().filter(usuario__in=qs)}
    return [{
        **_serializar_usuario(u, u.id in vigentes),
        "motivo_restriccion": vigentes[u.id].motivo if u.id in vigentes else None,
        "restriccion_hasta": vigentes[u.id].fecha_fin if u.id in vigentes else None,
    } for u in qs]


# ---------------------------------------------------------------- CU-USU-01 Registrarse

def registrar_usuario(*, nombre_completo, correo, telefono, password, rol, acepta_datos, ciudad=None, ip=None) -> Usuario:
    """Registra una cuenta de Huésped o Anfitrión (RF-D-USU-01.1, HU-01).

    Valida la autorización de datos, el rol, que el correo no esté registrado, el teléfono y la
    contraseña (8 o más caracteres y validadores de Django). Guarda la fecha de la autorización
    (Ley 1581) y registra UsuarioRegistrado en la auditoría.

    Args:
        nombre_completo, correo, telefono, password: datos del formulario.
        rol: HUESPED o ANFITRION (el Administrador no se crea por registro).
        acepta_datos: si aceptó el tratamiento de sus datos personales.
        ciudad: texto opcional.
        ip: IP del cliente, para la auditoría.

    Returns:
        El usuario creado.

    Raises:
        ErrorNegocio: sin autorización de datos, rol no permitido, teléfono o contraseña inválidos.
        Conflicto: el correo ya está registrado (CA-01.2).
    """
    if not acepta_datos:
        raise ErrorNegocio("La autorización de tratamiento de datos es obligatoria.", campo="acepta_datos")
    if rol not in ROLES_REGISTRO:
        raise ErrorNegocio("Solo puedes registrarte como Huésped o Anfitrión.", campo="rol")
    correo = Usuario.objects.normalize_email(correo.strip()).lower()
    if Usuario.objects.filter(correo__iexact=correo).exists():
        raise Conflicto("Este correo ya está registrado.", extra={"campo": "correo"})
    telefono = validar_telefono(telefono)
    _validar_clave(password, Usuario(correo=correo, nombre_completo=nombre_completo))
    ciudad = _limpiar_ciudad(ciudad)
    with transaction.atomic():
        u = Usuario.registrar_usuario(correo, password, rol, nombre_completo=nombre_completo.strip(), telefono=telefono,
                              ciudad=ciudad)
        auditoria.registrar_evento(u.id, "UsuarioRegistrado", entidad="Usuario", entidad_id=u.id, detalle={"rol": rol}, ip=ip)
    return u


# ---------------------------------------------------------------- CU-USU-02 Iniciar sesión

def iniciar_sesion(correo: str, password: str, ip=None) -> dict:
    """Inicia sesión con correo y contraseña (RF-D-USU-01.2, HU-02).

    Rechaza credenciales incorrectas con un mensaje que no dice cuál de los dos falló, y una cuenta
    restringida con el motivo (CA-02.3). Si la cuenta estaba desactivada, la reactiva (CA-04.4).
    Cada intento, exitoso o no, queda en la auditoría.

    Args:
        correo: correo de la cuenta (sin distinguir mayúsculas).
        password: contraseña.
        ip: IP del cliente.

    Returns:
        {"access", "refresh", "usuario"} y, si se reactivó la cuenta, un "aviso". La vista pone el
        refresh en una cookie httpOnly (ADR-005).

    Raises:
        ErrorNegocio: 401 si las credenciales no coinciden; 403 si la cuenta está restringida.
    """
    u = Usuario.objects.filter(correo__iexact=(correo or "").strip()).first()
    # Los intentos fallidos se registran fuera de transaction.atomic ("transacción propia"):
    # quedan en la auditoría aunque la petición termine en error.
    if not u or not u.iniciar_sesion(correo, password):
        auditoria.registrar_evento(u.id if u else None, "InicioSesion", entidad="Usuario", entidad_id=u.id if u else None,
                            exitoso=False, detalle={"motivo": "Credenciales incorrectas", "correo": (correo or "")[:254]}, ip=ip)
        raise ErrorNegocio("Correo o contraseña incorrectos. Revisa los datos e inténtalo de nuevo.", codigo=401)
    vigente = obtener_restriccion_vigente(u.id)
    if vigente:  # CA-02.3, CA-21.1
        auditoria.registrar_evento(u.id, "InicioSesion", entidad="Usuario", entidad_id=u.id, exitoso=False,
                            detalle={"motivo": "Cuenta restringida"}, ip=ip)
        hasta = f" hasta el {timezone.localtime(vigente.fecha_fin):%d/%m/%Y}" if vigente.fecha_fin else ""
        raise ErrorNegocio(
            f"Tu cuenta está restringida por el administrador{hasta}. Motivo: {vigente.motivo}", codigo=403,
            extra={"motivo": vigente.motivo, "fecha_fin": vigente.fecha_fin.isoformat() if vigente.fecha_fin else None},
        )
    reactivada = not u.activa
    with transaction.atomic():
        if reactivada:  # CA-04.4: la cuenta se reactiva al volver a ingresar
            u.reactivar_cuenta()
        u.last_login = timezone.now()
        u.save(update_fields=["last_login"])
        auditoria.registrar_evento(u.id, "InicioSesion", entidad="Usuario", entidad_id=u.id, detalle={"reactivada": reactivada}, ip=ip)
    refresh = RefreshToken.for_user(u)
    return {"access": str(refresh.access_token), "refresh": str(refresh), "usuario": _serializar_usuario(u),
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
    return {"access": str(nuevo.access_token), "refresh": str(nuevo), "usuario": _serializar_usuario(u)}


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
        auditoria.registrar_evento(usuario_id, "CierreSesion", entidad="Usuario", entidad_id=usuario_id, ip=ip)


def _cerrar_todas_las_sesiones(u: Usuario) -> None:
    """Pone en la lista negra todos los tokens de renovación del usuario: ninguna sesión abierta podrá renovarse."""
    for t in OutstandingToken.objects.filter(user=u):
        BlacklistedToken.objects.get_or_create(token=t)


# ---------------------------------------------------------------- CU-USU-03 Recuperar contraseña

def _calcular_hash(token: str) -> str:
    """SHA-256 del token de recuperación: en la base solo se guarda el hash, nunca el enlace (RNF-P-SEG-03)."""
    return hashlib.sha256(token.encode()).hexdigest()


def solicitar_recuperacion(correo: str, ip=None) -> str | None:
    """Crea el enlace de recuperación y lo envía al correo de la cuenta (RF-D-USU-01.3). En la base solo queda el hash
    del token. Devuelve el token en claro solo para las pruebas: la API nunca lo muestra. Si el correo no existe no
    envía nada y devuelve None; la vista responde igual en los dos casos (no revela qué correos están registrados)."""
    u = Usuario.objects.filter(correo__iexact=(correo or "").strip()).first()
    if not u:
        auditoria.registrar_evento(None, "RecuperacionSolicitada", exitoso=False, detalle={"motivo": "Correo no registrado"}, ip=ip)
        return None
    token = secrets.token_urlsafe(32)
    ahora = timezone.now()
    with transaction.atomic():
        # Un solo enlace vivo por cuenta: los anteriores sin usar dejan de servir.
        TokenRecuperacion.objects.filter(usuario=u, usado_en__isnull=True, vence__gt=ahora).update(vence=ahora)
        TokenRecuperacion.objects.create(
            usuario=u, token_hash=_calcular_hash(token), vence=ahora + timedelta(minutes=settings.MINUTOS_ENLACE_RECUPERACION)
        )
        auditoria.registrar_evento(u.id, "RecuperacionSolicitada", entidad="Usuario", entidad_id=u.id, ip=ip)
    enlace = f"{settings.FRONTEND_URL}/#/restablecer/{token}"
    if settings.CORREO_EN_SEGUNDO_PLANO:
        # La respuesta no espera al servidor de correo: tarda lo mismo exista o no la cuenta
        threading.Thread(target=_enviar_correo_recuperacion, args=(u.id, u.correo, u.nombre_completo, enlace, ip),
                         daemon=True).start()
    else:
        _enviar_correo_recuperacion(u.id, u.correo, u.nombre_completo, enlace, ip)
    return token


def _enviar_correo_recuperacion(usuario_id: int, correo: str, nombre: str, enlace: str, ip=None) -> None:
    """Envía el enlace por correo (texto y HTML). Si el servidor de correo falla, el usuario ve la misma respuesta y la
    falla queda en el log y en la auditoría (CorreoRecuperacionNoEnviado) para que el equipo la revise."""
    minutos = settings.MINUTOS_ENLACE_RECUPERACION
    texto = (
        f"Hola, {nombre}:\n\n"
        "Recibimos una solicitud para cambiar la contraseña de tu cuenta en Alojamientos LR.\n"
        f"Abre este enlace para definir una nueva (sirve una sola vez y vence en {minutos} minutos):\n\n{enlace}\n\n"
        "Si no fuiste tú, ignora este correo: tu contraseña no cambia.\n\nAlojamientos LR · Inversiones LR"
    )
    html = (
        '<div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;color:#1f2b29">'
        '<h2 style="color:#134e4a;margin-bottom:8px">Cambia tu contraseña</h2>'
        f"<p>Hola, {escape(nombre)}:</p>"
        "<p>Recibimos una solicitud para cambiar la contraseña de tu cuenta en <b>Alojamientos LR</b>.</p>"
        f'<p style="margin:24px 0"><a href="{escape(enlace)}" style="background:#c2410c;color:#fff;padding:12px 20px;'
        'border-radius:8px;text-decoration:none;font-weight:bold">Definir una nueva contraseña</a></p>'
        f"<p style=\"color:#57534e;font-size:14px\">El enlace sirve una sola vez y vence en {minutos} minutos. Si el botón no "
        f'funciona, copia esta dirección en el navegador:<br><span style="word-break:break-all">{escape(enlace)}</span></p>'
        '<p style="color:#57534e;font-size:14px">Si no fuiste tú, ignora este correo: tu contraseña no cambia.</p>'
        '<p style="color:#8a8f8d;font-size:12px">Alojamientos LR · Inversiones LR</p></div>'
    )
    try:
        mensaje = EmailMultiAlternatives("Cambia tu contraseña · Alojamientos LR", texto, settings.DEFAULT_FROM_EMAIL, [correo])
        mensaje.attach_alternative(html, "text/html")
        mensaje.send(fail_silently=False)
    except Exception as e:  # noqa: BLE001  el usuario no debe ver el error del servidor de correo
        log.exception("No se pudo enviar el correo de recuperación", extra={"usuario": usuario_id})
        try:
            auditoria.registrar_evento(usuario_id, "CorreoRecuperacionNoEnviado", entidad="Usuario", entidad_id=usuario_id,
                                       exitoso=False, ip=ip, detalle={"error": type(e).__name__, "mensaje": str(e)[:300]})
        except Exception:  # noqa: BLE001
            log.exception("Tampoco se pudo registrar la falla del correo en la auditoría")
    finally:
        if settings.CORREO_EN_SEGUNDO_PLANO:
            connection.close()  # el hilo abrió su propia conexión a la base


def consultar_estado_enlace(token: str) -> str:
    """Estado de un enlace de recuperación, para avisar apenas se abre (CA-03.2, CA-03.3).

    Args:
        token: el token del enlace.

    Returns:
        "valido", "usado", "vencido" o "inexistente".
    """
    t = TokenRecuperacion.objects.filter(token_hash=_calcular_hash(token)).first()
    if not t:
        return "inexistente"
    if t.usado_en:
        return "usado"
    return "valido" if t.es_valido() else "vencido"


def restablecer_clave(token: str, password: str, ip=None) -> None:
    """Define la nueva contraseña con un enlace de recuperación (RF-D-USU-01.3).

    Marca el enlace como usado, cierra todas las sesiones abiertas de la cuenta y registra
    ContrasenaRestablecida en la auditoría, todo en una transacción.

    Args:
        token: el token del enlace.
        password: la nueva contraseña.
        ip: IP del cliente.

    Raises:
        ErrorNegocio: 404 si el enlace no existe; 410 si ya se usó o venció; 400 si la contraseña no es válida.
    """
    with transaction.atomic():
        t = TokenRecuperacion.objects.select_for_update().filter(token_hash=_calcular_hash(token)).first()
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
        auditoria.registrar_evento(u.id, "ContrasenaRestablecida", entidad="Usuario", entidad_id=u.id, ip=ip)


# ---------------------------------------------------------------- CU-USU-04 Perfil

def actualizar_perfil(u: Usuario, datos: dict, ip=None) -> Usuario:
    """Actualiza el perfil del usuario (RF-D-USU-01.4, CA-04.1).

    Cambia solo los datos que llegan: nombre, teléfono, ciudad y, si se pide, la contraseña (exige la
    actual). Registra PerfilActualizado con los campos cambiados, sin valores.

    Args:
        u: el usuario que llama.
        datos: nombre_completo, telefono, ciudad, password_actual y password_nueva (todos opcionales).
        ip: IP del cliente.

    Returns:
        El usuario actualizado.

    Raises:
        ErrorNegocio: dato vacío, teléfono inválido, contraseña actual incorrecta o nueva contraseña no válida.
    """
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
            auditoria.registrar_evento(u.id, "PerfilActualizado", entidad="Usuario", entidad_id=u.id, ip=ip,
                                detalle={"campos": [c for c in campos if c != "password"] + (["contraseña"] if "password" in campos else [])})
    return u


# ---------------------------------------------------------------- CU-USU-05 Desactivar cuenta

def desactivar_cuenta(u: Usuario, ip=None) -> None:
    """Desactiva la cuenta del usuario (RF-D-USU-01.4, HU-04).

    No se permite si es Administrador ni si tiene reservas confirmadas o en revisión pendientes, como
    huésped o en sus alojamientos (CA-04.2, CA-04.5). Al desactivar se cierran todas sus sesiones;
    la cuenta se reactiva al volver a iniciar sesión.

    Args:
        u: el usuario que llama.
        ip: IP del cliente.

    Raises:
        SinPermiso: si es una cuenta de Administrador.
        Conflicto: si tiene reservas pendientes (la respuesta trae cuáles son).
    """
    from apps.reservas import services as reservas

    if u.rol == RolUsuario.ADMINISTRADOR:
        auditoria.registrar_evento(u.id, "AccesoDenegado", exitoso=False, detalle={"motivo": "Desactivar cuenta de administrador"}, ip=ip)
        raise SinPermiso("Las cuentas de administrador no se desactivan desde el perfil.")
    pendientes = reservas.listar_reservas_pendientes(u.id, es_anfitrion=u.rol == RolUsuario.ANFITRION)
    if pendientes:  # CA-04.2, CA-04.5
        raise Conflicto(
            "No puedes desactivar tu cuenta: tienes reservas confirmadas o en revisión pendientes.", extra={"reservas": pendientes}
        )
    with transaction.atomic():
        u.desactivar_cuenta()
        _cerrar_todas_las_sesiones(u)
        auditoria.registrar_evento(u.id, "CuentaDesactivada", entidad="Usuario", entidad_id=u.id, ip=ip)


# ---------------------------------------------------------------- RF-D-ADM-02.1 Restringir

def restringir_usuario(admin: Usuario, usuario_id: int, motivo: str, fecha_fin=None, ip=None) -> RestriccionUsuario:
    """El Administrador restringe una cuenta (RF-D-ADM-02.1, HU-21).

    No modifica la cuenta ni sus reservas: solo crea la restricción, y el acceso se corta desde la
    siguiente petición porque is_active la tiene en cuenta (ADR-005).

    Args:
        admin: el Administrador que restringe.
        usuario_id: cuenta a restringir.
        motivo: motivo obligatorio; el usuario lo ve al intentar entrar.
        fecha_fin: fin opcional (debe ser futura); sin ella, la restricción es indefinida.
        ip: IP del cliente.

    Returns:
        La restricción creada.

    Raises:
        NoEncontrado: si la cuenta no existe.
        ErrorNegocio: cuenta de Administrador, motivo vacío o fecha de fin pasada.
        Conflicto: si ya tiene una restricción vigente.
    """
    u = Usuario.objects.filter(pk=usuario_id).first()
    if not u:
        raise NoEncontrado("El usuario no existe.")
    if u.rol == RolUsuario.ADMINISTRADOR:
        raise ErrorNegocio("No se puede restringir una cuenta de administrador.")
    if not (motivo or "").strip():
        raise ErrorNegocio("Escribe el motivo de la restricción.", campo="motivo")
    if fecha_fin and fecha_fin <= timezone.now():
        raise ErrorNegocio("La fecha de fin debe ser futura.", campo="fecha_fin")
    if obtener_restriccion_vigente(u.id):
        raise Conflicto("La cuenta ya tiene una restricción vigente.")
    # RF-D-ADM-02.1: restringir NO modifica la cuenta ni sus reservas; solo crea la restricción.
    # El acceso se corta porque is_active la tiene en cuenta desde la siguiente petición (ADR-005).
    with transaction.atomic():
        r = RestriccionUsuario.objects.create(usuario=u, administrador=admin, motivo=motivo.strip(), fecha_fin=fecha_fin)
        auditoria.registrar_evento(admin.id, "CuentaRestringida", entidad="Usuario", entidad_id=u.id, ip=ip,
                            detalle={"motivo": r.motivo, "fecha_fin": fecha_fin.isoformat() if fecha_fin else None})
    return r


def levantar_restriccion(admin: Usuario, usuario_id: int, ip=None) -> None:
    """El Administrador levanta la restricción vigente de una cuenta (pone su fecha de fin en este momento).

    Raises:
        NoEncontrado: si la cuenta no tiene una restricción vigente.
    """
    r = obtener_restriccion_vigente(usuario_id)
    if not r:
        raise NoEncontrado("La cuenta no tiene una restricción vigente.")
    with transaction.atomic():  # levantarla pone fecha_fin = ahora
        r.fecha_fin = timezone.now()
        r.save(update_fields=["fecha_fin"])
        auditoria.registrar_evento(admin.id, "RestriccionLevantada", entidad="Usuario", entidad_id=usuario_id, ip=ip)


# ---------------------------------------------------------------- utilidades

def _limpiar_ciudad(ciudad) -> str | None:
    """usuario.ciudad es texto opcional VARCHAR(80) (MOD-01). Vacío o null = sin ciudad."""
    ciudad = (ciudad or "").strip()
    if len(ciudad) > 80:
        raise ErrorNegocio("La ciudad admite máximo 80 caracteres.", campo="ciudad")
    return ciudad or None


def _validar_clave(password: str, usuario: Usuario) -> None:
    """Valida una contraseña: al menos 8 caracteres (RF-D-USU-01.1) y los validadores de Django.

    Raises:
        ErrorNegocio: con el motivo y campo "password".
    """
    if not password or len(password) < 8:
        raise ErrorNegocio("La contraseña debe tener al menos 8 caracteres.", campo="password")
    try:
        validate_password(password, usuario)
    except ValidationError as e:
        raise ErrorNegocio(" ".join(e.messages), campo="password") from e


def _serializar_usuario(u: Usuario, restringida: bool | None = None) -> dict:
    """Convierte un usuario en el diccionario que devuelve la API (sin la contraseña).

    Args:
        u: el usuario.
        restringida: si ya se calculó, se usa ese valor para no volver a consultar las restricciones.
    """
    return {
        "id": u.id, "correo": u.correo, "nombre_completo": u.nombre_completo, "telefono": u.telefono,
        "ciudad": u.ciudad, "rol": u.rol, "activa": u.activa,
        "restringida": u.esta_restringida if restringida is None else restringida,  # derivado de RestriccionUsuario
        "autorizacion_datos": u.autorizacion_datos.isoformat() if u.autorizacion_datos else None,
        "fecha_registro": u.fecha_registro.isoformat() if u.fecha_registro else None,
    }


def convertir_usuario_a_dict(u: Usuario) -> dict:
    """Interfaz pública de _serializar_usuario para las vistas: el usuario como lo devuelve la API."""
    return _serializar_usuario(u)
