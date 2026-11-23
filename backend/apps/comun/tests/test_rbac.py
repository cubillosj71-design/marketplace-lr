"""RBAC con la matriz de permisos por rol (RF-D-USU-02.1, HU-05: CA-05.1 a CA-05.3).

1. Toda ruta de config.urls declara RequierePermiso, salvo la lista blanca.
2. Cada ruta con cada rol (y sin sesión): 200 o 201 si el rol tiene el permiso, 403 si no y 401 sin sesión.
3. GET /identidad/permisos para cada rol.
4. Ninguna vista usa TieneRol ni sus alias.

La demo se carga una vez por módulo dentro de una transacción que se revierte al final; cada prueba corre en un
savepoint propio (pytest-django), así lo que una prueba cambia no lo ve la siguiente.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Callable

import pytest
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.db import transaction
from django.test import override_settings
from django.urls import URLResolver, get_resolver
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.comun import permisos, rbac
from apps.comun.permisos import RequierePermiso

pytestmark = pytest.mark.django_db

V, H, A, ADM = "VISITANTE", "HUESPED", "ANFITRION", "ADMINISTRADOR"
ROLES = (V, H, A, ADM)
TODOS = frozenset(ROLES)
CON_CUENTA = frozenset({H, A, ADM})
CORREO = {H: "huesped@correo.com", A: "anfitrion@correo.com", ADM: "admin@inversioneslr.com"}

# Rutas que no declaran RequierePermiso, cada una con su razón.
LISTA_BLANCA = {
    "api/v1/salud": "monitor externo (RNF-P-FIA-01)",
    "api/v1/identidad/token": "iniciar sesión: todavía no hay rol",
    "api/v1/identidad/token/renovar": "renovar la sesión con la cookie, sin access vigente",
    "api/v1/identidad/salir": "cerrar sesión aunque el access ya venció",
    "api/v1/identidad/recuperacion": "recuperar la contraseña sin sesión (RF-D-USU-01.3)",
    "api/v1/identidad/recuperacion/<str:token>": "usar el enlace de recuperación sin sesión",
    "api/v1/identidad/permisos": "describe la propia matriz; sin sesión devuelve la del VISITANTE",
    "api/v1/interno/tareas/diarias": "tareas programadas con su propio token (X-Token-Tareas)",
}
PREFIJOS_FUERA_DE_DRF = ("admin/",)  # sitio de Django: no es parte de la API y exige is_staff


# ---------------------------------------------------------------- datos del módulo

def _datos_publicacion(titulo: str) -> dict:
    from apps.catalogo import services as catalogo

    cat = catalogo.listar_catalogos()
    return {
        "titulo": titulo, "descripcion": "Alojamiento de prueba.", "ciudad": cat["ciudades"][0]["id"],
        "tipo_alojamiento": cat["tipos"][0]["id"],
        "politica": apps.get_model("catalogo", "PoliticaCancelacion").objects.get(nombre="Moderada").id,
        "ubicacion_textual": "Centro", "capacidad": 4, "precio_noche": Decimal(200000), "tarifa_limpieza": Decimal(50000),
        "servicios": [], "servicios_adicionales": [], "reglas": ["No fumar"],
        "imagenes": ["https://placehold.co/600x400?text=RBAC"],
    }


def _activa(dueno, admin, titulo: str) -> int:
    from apps.catalogo import services as catalogo

    p = catalogo.crear_publicacion(dueno, _datos_publicacion(titulo))
    catalogo.cambiar_estado(dueno, p.id, "PENDIENTE_REVISION")
    catalogo.revisar_publicacion(admin, p.id, "APROBAR", None)
    return p.id


def _dias(n: int):
    return timezone.localdate() + timedelta(days=n)


def _reservar(huesped, pid: int, desde: int, hasta: int) -> int:
    from apps.reservas import services as reservas

    cot = reservas.cotizar_estancia(huesped, pid, _dias(desde), _dias(hasta), 2)
    reserva, _ = reservas.reservar_alojamiento(huesped, cot.id, uuid.uuid4(), "simulado")
    return reserva["id"]


def _preparar() -> dict:
    from apps.catalogo import services as catalogo

    Usuario = apps.get_model("identidad", "Usuario")
    Publicacion = apps.get_model("catalogo", "Publicacion")
    Notificacion = apps.get_model("notificaciones", "Notificacion")
    usuarios = {rol: Usuario.objects.get(correo=correo) for rol, correo in CORREO.items()}
    h, a, adm = usuarios[H], usuarios[A], usuarios[ADM]

    pub = _activa(a, adm, "RBAC activa")
    reserva = _reservar(h, pub, 30, 33)
    # Una reserva futura en una publicación que luego se bloquea: queda EN_REVISION (RF-D-ADM-01.2)
    pub_bloqueada = _activa(a, adm, "RBAC para bloquear")
    en_revision = _reservar(h, pub_bloqueada, 60, 62)
    catalogo.bloquear_publicacion(adm, pub_bloqueada, "Prueba de RBAC")
    assert apps.get_model("reservas", "Reserva").objects.get(pk=en_revision).estado == "EN_REVISION"

    por_titulo = {p.titulo: p.id for p in Publicacion.objects.all()}
    return {
        "usuarios": usuarios,
        "pub": pub,
        "reserva": reserva,
        "en_revision": en_revision,
        "borrador": catalogo.crear_publicacion(a, _datos_publicacion("RBAC borrador completo")).id,
        "pausada": por_titulo["Cabaña El Roble"],
        "pendiente": por_titulo["Habitación cerca al centro"],
        "bloqueada": por_titulo["Loft Chapinero"],
        "pedro": Usuario.objects.get(correo="pedro@correo.com").id,
        "restringido": Usuario.objects.get(correo="restringido@correo.com").id,
        "notificacion": {rol: Notificacion.objects.create(destinatario=u, tipo="Prueba", mensaje="Aviso de prueba").id
                         for rol, u in usuarios.items()},
    }


@pytest.fixture(scope="module")
def ctx(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        externa = transaction.atomic()
        externa.__enter__()
        try:
            with override_settings(STRIPE_SECRET_KEY=""):
                call_command("cargar_demo", verbosity=0)
                datos = _preparar()
            yield datos
        finally:
            transaction.set_rollback(True)
            externa.__exit__(None, None, None)


def _cliente(usuario=None) -> APIClient:
    c = APIClient()
    if usuario is not None:
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(usuario).access_token}")
    return c


# ---------------------------------------------------------------- casos rol x ruta

@dataclass(frozen=True)
class Caso:
    metodo: str
    patron: str                   # tal como queda en config.urls
    roles: frozenset              # roles que tienen el permiso (respuesta esperada: exito)
    peticion: Callable            # (ctx, rol) -> (ruta, cuerpo)
    exito: int = 200
    cuenta_nueva: bool = False    # la prueba usa una cuenta recién creada de ese rol

    @property
    def id(self):
        return f"{self.metodo} {self.patron}"


def _borrador_nuevo(ctx) -> int:
    from apps.catalogo import services as catalogo

    return catalogo.crear_publicacion(ctx["usuarios"][A], {"titulo": "Borrador para eliminar"}).id


def _fija(ruta, cuerpo=None):
    return lambda ctx, rol: (ruta, cuerpo)


def _cotizacion(ctx, desde, hasta) -> int:
    from apps.reservas import services as reservas

    return reservas.cotizar_estancia(ctx["usuarios"][H], ctx["pub"], _dias(desde), _dias(hasta), 2).id


CASOS = [
    # Búsqueda (RF-D-RES-01.x): Visitante y Huésped
    Caso("GET", "api/v1/busqueda/publicaciones", frozenset({V, H}), _fija("/api/v1/busqueda/publicaciones")),
    Caso("GET", "api/v1/busqueda/publicaciones/<int:pk>", frozenset({V, H}),
         lambda c, r: (f"/api/v1/busqueda/publicaciones/{c['pub']}", None)),
    # Catálogos fijos: todos
    Caso("GET", "api/v1/catalogo/ciudades", TODOS, _fija("/api/v1/catalogo/ciudades")),
    Caso("GET", "api/v1/catalogo/tipos-alojamiento", TODOS, _fija("/api/v1/catalogo/tipos-alojamiento")),
    Caso("GET", "api/v1/catalogo/servicios", TODOS, _fija("/api/v1/catalogo/servicios")),
    Caso("GET", "api/v1/catalogo/politicas", TODOS, _fija("/api/v1/catalogo/politicas")),
    # Publicaciones del anfitrión (RF-D-ALO-01.x, 02.1); el administrador modifica cualquiera (ALO-02.1, ADM-01.x)
    Caso("POST", "api/v1/catalogo/publicaciones", frozenset({A}), _fija("/api/v1/catalogo/publicaciones", {"titulo": "Nueva"}), 201),
    Caso("GET", "api/v1/catalogo/mis-publicaciones", frozenset({A}), _fija("/api/v1/catalogo/mis-publicaciones")),
    Caso("DELETE", "api/v1/catalogo/mis-publicaciones/<int:pk>", frozenset({A}),
         lambda c, r: (f"/api/v1/catalogo/mis-publicaciones/{_borrador_nuevo(c)}", None), 204),
    Caso("GET", "api/v1/catalogo/publicaciones/<int:pk>", frozenset({A, ADM}),
         lambda c, r: (f"/api/v1/catalogo/publicaciones/{c['pub']}", None)),
    Caso("PATCH", "api/v1/catalogo/publicaciones/<int:pk>", frozenset({A, ADM}),
         lambda c, r: (f"/api/v1/catalogo/publicaciones/{c['pub']}", {"titulo": "Título nuevo"})),
    Caso("POST", "api/v1/catalogo/publicaciones/<int:pk>/pausar", frozenset({A, ADM}),
         lambda c, r: (f"/api/v1/catalogo/publicaciones/{c['pub']}/pausar", None)),
    Caso("POST", "api/v1/catalogo/publicaciones/<int:pk>/reactivar", frozenset({A, ADM}),
         lambda c, r: (f"/api/v1/catalogo/publicaciones/{c['pausada']}/reactivar", None)),
    Caso("POST", "api/v1/catalogo/publicaciones/<int:pk>/enviar-revision", frozenset({A}),
         lambda c, r: (f"/api/v1/catalogo/publicaciones/{c['borrador']}/enviar-revision", None)),
    Caso("GET", "api/v1/catalogo/publicaciones/<int:pk>/calendario", frozenset({A}),
         lambda c, r: (f"/api/v1/catalogo/publicaciones/{c['pub']}/calendario", None)),
    Caso("POST", "api/v1/catalogo/publicaciones/<int:pk>/calendario", frozenset({A}),
         lambda c, r: (f"/api/v1/catalogo/publicaciones/{c['pub']}/calendario",
                       {"fecha_inicio": _dias(100).isoformat(), "fecha_fin": _dias(102).isoformat(), "tipo": "NO_DISPONIBLE"})),
    # Cotizar, reservar, consultar y cancelar (RF-D-RES-02.x, 03.1): Huésped
    Caso("POST", "api/v1/reservas/cotizaciones", frozenset({H}),
         lambda c, r: ("/api/v1/reservas/cotizaciones", {"publicacion": c["pub"], "fecha_llegada": _dias(10).isoformat(),
                                                         "fecha_salida": _dias(12).isoformat(), "num_huespedes": 2}), 201),
    Caso("GET", "api/v1/reservas/cotizaciones/<int:pk>", frozenset({H}),
         lambda c, r: (f"/api/v1/reservas/cotizaciones/{_cotizacion(c, 10, 12)}", None)),
    Caso("POST", "api/v1/reservas", frozenset({H}),
         lambda c, r: ("/api/v1/reservas", {"cotizacion": _cotizacion(c, 14, 16), "clave_idempotencia": str(uuid.uuid4()),
                                            "medio_pago": "simulado"}), 201),
    Caso("GET", "api/v1/reservas/mias", frozenset({H}), _fija("/api/v1/reservas/mias")),
    Caso("GET", "api/v1/reservas/de-mis-alojamientos", frozenset({A}), _fija("/api/v1/reservas/de-mis-alojamientos")),
    Caso("GET", "api/v1/reservas/<int:pk>", frozenset({H, A, ADM}), lambda c, r: (f"/api/v1/reservas/{c['reserva']}", None)),
    Caso("GET", "api/v1/reservas/<int:pk>/cancelar", frozenset({H}), lambda c, r: (f"/api/v1/reservas/{c['reserva']}/cancelar", None)),
    Caso("POST", "api/v1/reservas/<int:pk>/cancelar", frozenset({H}),
         lambda c, r: (f"/api/v1/reservas/{c['reserva']}/cancelar", {"motivo": "Cambio de planes"})),
    # Notificaciones (RF-D-RES-04.1)
    Caso("GET", "api/v1/notificaciones", CON_CUENTA, _fija("/api/v1/notificaciones")),
    Caso("POST", "api/v1/notificaciones/leidas", CON_CUENTA, _fija("/api/v1/notificaciones/leidas")),
    Caso("POST", "api/v1/notificaciones/<int:pk>/leida", CON_CUENTA,
         lambda c, r: (f"/api/v1/notificaciones/{c['notificacion'].get(r, c['notificacion'][H])}/leida", None)),
    # Cuenta y perfil (RF-D-USU-01.1, 01.4)
    Caso("POST", "api/v1/identidad/registro", frozenset({V}),
         _fija("/api/v1/identidad/registro", {"nombre_completo": "Marta Ríos", "correo": "marta@correo.com", "telefono": "300 111 2233",
                                              "password": "Segura2026", "rol": "HUESPED", "acepta_datos": True}), 201),
    Caso("GET", "api/v1/identidad/perfil", CON_CUENTA, _fija("/api/v1/identidad/perfil")),
    Caso("PATCH", "api/v1/identidad/perfil", CON_CUENTA, _fija("/api/v1/identidad/perfil", {"nombre_completo": "Nombre Nuevo"})),
    Caso("POST", "api/v1/identidad/perfil/desactivar", frozenset({H, A}), _fija("/api/v1/identidad/perfil/desactivar"),
         cuenta_nueva=True),
    # Administración (RF-D-ADM-01.x a 05.x)
    Caso("GET", "api/v1/admin/publicaciones", frozenset({ADM}), _fija("/api/v1/admin/publicaciones")),
    Caso("POST", "api/v1/admin/publicaciones/<int:pk>/revision", frozenset({ADM}),
         lambda c, r: (f"/api/v1/admin/publicaciones/{c['pendiente']}/revision", {"accion": "APROBAR"})),
    Caso("POST", "api/v1/admin/publicaciones/<int:pk>/bloqueo", frozenset({ADM}),
         lambda c, r: (f"/api/v1/admin/publicaciones/{c['pub']}/bloqueo", {"motivo": "Dirección falsa"})),
    Caso("DELETE", "api/v1/admin/publicaciones/<int:pk>/bloqueo", frozenset({ADM}),
         lambda c, r: (f"/api/v1/admin/publicaciones/{c['bloqueada']}/bloqueo", None)),
    Caso("GET", "api/v1/admin/usuarios", frozenset({ADM}), _fija("/api/v1/admin/usuarios")),
    Caso("GET", "api/v1/identidad/roles", frozenset({ADM}), _fija("/api/v1/identidad/roles")),
    Caso("POST", "api/v1/admin/usuarios/<int:usuario_id>/restriccion", frozenset({ADM}),
         lambda c, r: (f"/api/v1/admin/usuarios/{c['pedro']}/restriccion", {"motivo": "Cobros por fuera"}), 201),
    Caso("DELETE", "api/v1/admin/usuarios/<int:usuario_id>/restriccion", frozenset({ADM}),
         lambda c, r: (f"/api/v1/admin/usuarios/{c['restringido']}/restriccion", None), 204),
    Caso("GET", "api/v1/admin/tarifa-servicio", frozenset({ADM}), _fija("/api/v1/admin/tarifa-servicio")),
    Caso("PUT", "api/v1/admin/tarifa-servicio", frozenset({ADM}), _fija("/api/v1/admin/tarifa-servicio", {"porcentaje": "12.00"})),
    Caso("GET", "api/v1/admin/reservas", frozenset({ADM}), _fija("/api/v1/admin/reservas")),
    Caso("GET", "api/v1/admin/reservas/resueltas", frozenset({ADM}), _fija("/api/v1/admin/reservas/resueltas")),
    Caso("GET", "api/v1/admin/reservas/<int:pk>", frozenset({ADM}), lambda c, r: (f"/api/v1/admin/reservas/{c['en_revision']}", None)),
    Caso("POST", "api/v1/admin/reservas/<int:pk>/resolver", frozenset({ADM}),
         lambda c, r: (f"/api/v1/admin/reservas/{c['en_revision']}/resolver", {"mantener": False, "motivo": "Publicación engañosa"})),
    Caso("GET", "api/v1/admin/auditoria", frozenset({ADM}), _fija("/api/v1/admin/auditoria")),
    Caso("GET", "api/v1/admin/tablero", frozenset({ADM}), _fija("/api/v1/admin/tablero")),
    Caso("GET", "api/v1/admin/reportes/<str:tipo>", frozenset({ADM}), _fija("/api/v1/admin/reportes/reservas?formato=pdf")),
]


def _usuario(ctx, caso: Caso, rol: str):
    if rol == V:
        return None
    if not caso.cuenta_nueva:
        return ctx["usuarios"][rol]
    return apps.get_model("identidad", "Usuario").objects.create_user(
        correo=f"nueva.{rol.lower()}@correo.com", password="Clave1234", nombre_completo=f"Cuenta {rol}", telefono="300 000 0000",
        rol=rol, autorizacion_datos=timezone.now(),
    )


@pytest.mark.parametrize("rol", ROLES)
@pytest.mark.parametrize("caso", CASOS, ids=lambda c: c.id)
def test_rol_por_ruta(ctx, caso, rol):
    usuario = _usuario(ctx, caso, rol)
    ruta, cuerpo = caso.peticion(ctx, rol)
    r = getattr(_cliente(usuario), caso.metodo.lower())(ruta, cuerpo, format="json")

    if rol in caso.roles:
        assert r.status_code == caso.exito, r.content
    elif rol == V:
        assert r.status_code == 401, r.content  # CA-05.1: sin sesión se pide iniciar sesión
    else:
        assert r.status_code == 403, r.content
        # CA-05.2: el intento queda registrado con la ruta y el permiso que faltó
        evento = apps.get_model("auditoria", "EventoAuditoria").objects.filter(actor_id=usuario.id, accion="AccesoDenegado").latest("id")
        assert evento.exitoso is False and evento.detalle["ruta"] == ruta.split("?")[0]
        assert evento.detalle["rol"] == rol and evento.detalle["permiso"]


# ---------------------------------------------------------------- todas las rutas declaran su permiso

def _rutas(patrones=None, prefijo=""):
    for p in get_resolver().url_patterns if patrones is None else patrones:
        if isinstance(p, URLResolver):
            yield from _rutas(p.url_patterns, prefijo + str(p.pattern))
        else:
            yield prefijo + str(p.pattern), p.callback


def _metodos(vista) -> set[str]:
    return {m.upper() for m in vista.http_method_names if m not in ("options", "head") and hasattr(vista, m)}


def _rutas_de_la_api():
    for patron, callback in _rutas():
        if not patron.startswith(PREFIJOS_FUERA_DE_DRF):
            yield patron, getattr(callback, "cls", None)


def test_toda_ruta_declara_requiere_permiso_salvo_la_lista_blanca():
    sin_permiso = []
    for patron, vista in _rutas_de_la_api():
        if patron in LISTA_BLANCA:
            continue
        if vista is None or not any(isinstance(p, RequierePermiso) for p in vista.permission_classes):
            sin_permiso.append(patron)
    assert sin_permiso == []
    rutas = {patron for patron, _ in _rutas_de_la_api()}
    assert set(LISTA_BLANCA) <= rutas, "La lista blanca nombra rutas que ya no existen"


def test_la_prueba_rol_por_ruta_cubre_todas_las_rutas_y_metodos():
    declaradas = {(m, patron) for patron, vista in _rutas_de_la_api() if patron not in LISTA_BLANCA for m in _metodos(vista)}
    probadas = {(c.metodo, c.patron) for c in CASOS}
    assert declaradas == probadas


def test_los_roles_esperados_coinciden_con_la_matriz():
    """Los casos dicen qué roles pasan según el SRS; la vista lo decide con la matriz. Deben coincidir."""
    vistas = {}
    for patron, vista in _rutas_de_la_api():
        vistas[patron] = vista
    for caso in CASOS:
        requeridos = next(p for p in vistas[caso.patron].permission_classes if isinstance(p, RequierePermiso)).permisos
        segun_matriz = {rol for rol in ROLES if not rbac.PERMISOS[rol].isdisjoint(requeridos)}
        assert segun_matriz == caso.roles, caso.id


def test_cada_permiso_de_la_matriz_lo_usa_alguna_ruta():
    usados = set()
    for _, vista in _rutas_de_la_api():
        for p in getattr(vista, "permission_classes", []):
            if isinstance(p, RequierePermiso):
                usados.update(p.permisos)
    assert usados == rbac.TODOS


def test_los_roles_de_la_matriz_son_los_de_usuario_mas_el_visitante():
    roles = set(dict(apps.get_model("identidad", "Usuario")._meta.get_field("rol").choices))
    assert set(rbac.PERMISOS) == roles | {V}


def test_un_permiso_fuera_de_la_matriz_no_se_puede_declarar():
    from django.core.exceptions import ImproperlyConfigured

    with pytest.raises(ImproperlyConfigured):
        RequierePermiso("reservas.inventado")
    with pytest.raises(ImproperlyConfigured):
        RequierePermiso()


# ---------------------------------------------------------------- GET /identidad/permisos

ESPERADOS = {
    V: {"busqueda.ver", "cuenta.registrar", "catalogo.ver"},
    H: {"busqueda.ver", "reservas.cotizar", "reservas.crear", "reservas.ver_propias", "reservas.cancelar_propia",
        "perfil.gestionar", "cuenta.desactivar", "notificaciones.ver", "catalogo.ver"},
    A: {"publicaciones.gestionar_propias", "calendario.gestionar", "reservas.ver_de_mis_alojamientos", "perfil.gestionar",
        "cuenta.desactivar", "notificaciones.ver", "catalogo.ver"},
    ADM: {"publicaciones.moderar", "reservas.resolver", "usuarios.ver", "usuarios.restringir", "tarifa.configurar",
          "auditoria.consultar", "tablero.ver", "reportes.descargar", "perfil.gestionar", "notificaciones.ver", "catalogo.ver"},
}


@pytest.mark.parametrize("rol", ROLES)
def test_permisos_del_usuario_actual(ctx, rol):
    usuario = None if rol == V else ctx["usuarios"][rol]
    r = _cliente(usuario).get("/api/v1/identidad/permisos")
    assert r.status_code == 200
    assert r.json()["rol"] == rol
    assert r.json()["permisos"] == sorted(ESPERADOS[rol])


# ---------------------------------------------------------------- GET /identidad/roles

def test_roles_devuelve_la_matriz_completa_al_administrador(ctx):
    r = _cliente(ctx["usuarios"][ADM]).get("/api/v1/identidad/roles")
    assert r.status_code == 200
    assert [x["rol"] for x in r.json()["roles"]] == [V, H, A, ADM]
    assert {x["rol"]: set(x["permisos"]) for x in r.json()["roles"]} == ESPERADOS


@pytest.mark.parametrize("rol,codigo", [(V, 401), (H, 403), (A, 403)])
def test_roles_no_la_ve_nadie_mas(ctx, rol, codigo):
    r = _cliente(None if rol == V else ctx["usuarios"][rol]).get("/api/v1/identidad/roles")
    assert r.status_code == codigo and "roles" not in r.json()


def test_politicas_trae_la_moderada_con_sus_tramos(ctx):
    politicas = _cliente().get("/api/v1/catalogo/politicas").json()
    moderada = next(p for p in politicas if p["nombre"] == "Moderada")
    assert moderada["id"] and moderada["tramos"] and all("porcentaje_devolucion" in t for t in moderada["tramos"])


# ---------------------------------------------------------------- ninguna vista usa TieneRol

VIEJOS = re.compile(r"\b(TieneRol|EsAdministrador|EsAnfitrion\w*|EsHuesped\w*|IsAuthenticated)\b")


def test_ninguna_vista_usa_tiene_rol_ni_sus_alias():
    for nombre in ("TieneRol", "EsAdministrador", "EsAnfitrion", "EsHuesped", "EsAnfitrionOAdministrador", "EsHuespedOAnfitrion"):
        assert not hasattr(permisos, nombre), nombre
    base = Path(settings.BASE_DIR) / "apps"
    usos = [f"{f.relative_to(base)}: {m.group(0)}" for f in base.rglob("*.py") if "tests" not in f.parts
            for m in VIEJOS.finditer(f.read_text(encoding="utf-8"))]
    assert usos == []


# ---------------------------------------------------------------- CA-05.2 desde el frontend

def test_ca_05_2_un_403_por_permiso_queda_en_la_auditoria(ctx):
    """El Huésped abre la revisión de publicaciones: la pantalla "No tienes permiso" llama a GET /admin/publicaciones,
    el backend responde 403 y registra el intento con exitoso=False, la ruta y el permiso que faltó."""
    huesped = ctx["usuarios"][H]
    r = _cliente(huesped).get("/api/v1/admin/publicaciones")
    assert r.status_code == 403
    evento = apps.get_model("auditoria", "EventoAuditoria").objects.filter(actor_id=huesped.id, accion="AccesoDenegado").latest("id")
    assert evento.exitoso is False
    assert evento.detalle["ruta"] == "/api/v1/admin/publicaciones"
    assert evento.detalle["permiso"] == "publicaciones.moderar"
    assert evento.detalle["rol"] == H


APP_TSX = Path(settings.BASE_DIR).parent / "frontend" / "src" / "App.tsx"
RUTA_FRONT = re.compile(r'\{ path: "([^"]+)", permiso: ("[^"]+"|\[[^\]]+\]), api: "([^"]+)"')


@pytest.mark.skipif(not APP_TSX.exists(), reason="el frontend no está en este checkout")
def test_cada_pantalla_protegida_registra_contra_una_ruta_con_su_mismo_permiso():
    """Cada ruta de App.tsx declara su ruta de la API; esa ruta debe exigir exactamente los mismos permisos que la
    pantalla. Si no, un usuario sin la pantalla podría recibir 200 y el intento no quedaría registrado (CA-05.2)."""
    from django.urls import resolve

    rutas = RUTA_FRONT.findall(APP_TSX.read_text(encoding="utf-8"))
    assert len(rutas) >= 20
    for pantalla, permiso, ruta_api in rutas:
        esperados = set(re.findall(r'"([^"]+)"', permiso))
        vista = resolve("/api/v1" + re.sub(r":\w+", "1", ruta_api)).func.view_class
        requeridos = next(p for p in vista.permission_classes if isinstance(p, RequierePermiso)).permisos
        assert set(requeridos) == esperados, (pantalla, ruta_api, requeridos)
