"""Matriz de permisos por rol (RF-D-USU-02.1, HU-05, ADR-005 y ADR-010).

Cada cuenta tiene un único rol (usuario.rol) y quien no ha iniciado sesión es VISITANTE. Un permiso dice QUÉ puede
hacer un rol, con el formato "modulo.accion"; SOBRE QUÉ recurso (la regla de dueño, CA-05.3) lo revisa cada service.
Las vistas lo exigen con apps.comun.permisos.RequierePermiso.

RBAC dinámico (ADR-010): los roles son fijos, pero los permisos de cada rol viven en las tablas permiso y rol_permiso
de Identidad y el Administrador los cambia desde "Roles y permisos". Aquí quedan las reglas que no se editan:

- PERMISOS: la matriz inicial del SRS. Se carga en la base solo si rol_permiso está vacía (identidad.services).
- ASIGNABLES: qué permisos se le pueden dar a cada rol. Un permiso que el service ata al rol (moderar revisa que
  sea ADMINISTRADOR; gestionar publicaciones, que sea el anfitrión dueño) no se le puede dar a otro rol, porque
  pasaría el control de la vista y el service lo trataría como su rol real.
- FIJOS: lo que no se le puede quitar a un rol. catalogo.ver (sin él no cargan ni las ciudades del registro) y
  roles.gestionar del Administrador (si se lo quitara, nadie podría volver a editar la matriz).
"""

from typing import Callable

from django.core.exceptions import ImproperlyConfigured

VISITANTE = "VISITANTE"
ROLES = (VISITANTE, "HUESPED", "ANFITRION", "ADMINISTRADOR")

# Descripción de cada permiso, para la pantalla "Roles y permisos" (tabla permiso).
PERMISOS_INFO: dict[str, str] = {
    "busqueda.ver": "Buscar alojamientos y ver su detalle",
    "cuenta.registrar": "Registrarse",
    "catalogo.ver": "Consultar ciudades, tipos, servicios y políticas",
    "reservas.cotizar": "Cotizar una estancia",
    "reservas.crear": "Reservar y pagar",
    "reservas.ver_propias": "Consultar sus reservas",
    "reservas.cancelar_propia": "Cancelar sus reservas",
    "perfil.gestionar": "Actualizar su perfil y su contraseña",
    "cuenta.desactivar": "Desactivar su cuenta",
    "notificaciones.ver": "Ver sus notificaciones",
    "publicaciones.gestionar_propias": "Crear, editar, enviar a revisión, pausar y reactivar sus publicaciones",
    "calendario.gestionar": "Administrar el calendario de sus alojamientos",
    "reservas.ver_de_mis_alojamientos": "Consultar las reservas de sus alojamientos",
    "publicaciones.moderar": "Aprobar, devolver, bloquear y modificar cualquier publicación",
    "reservas.resolver": "Resolver reservas EN_REVISION",
    "usuarios.ver": "Consultar las cuentas de usuario",
    "usuarios.restringir": "Restringir cuentas y quitar la restricción",
    "tarifa.configurar": "Configurar la tarifa de servicio",
    "auditoria.consultar": "Consultar el registro de acciones",
    "tablero.ver": "Ver el tablero",
    "reportes.descargar": "Descargar reportes (PDF o Excel)",
    "roles.gestionar": "Cambiar los permisos de cada rol",
}

# Matriz inicial (SRS, RF-D-USU-02.1).
PERMISOS: dict[str, frozenset[str]] = {
    # Sin sesión: buscar, ver el detalle y registrarse (RF-D-USU-02.1)
    VISITANTE: frozenset({
        "busqueda.ver",
        "cuenta.registrar",
        "catalogo.ver",
    }),
    "HUESPED": frozenset({
        "busqueda.ver",
        "reservas.cotizar",
        "reservas.crear",
        "reservas.ver_propias",
        "reservas.cancelar_propia",
        "perfil.gestionar",
        "cuenta.desactivar",
        "notificaciones.ver",
        "catalogo.ver",
    }),
    "ANFITRION": frozenset({
        "publicaciones.gestionar_propias",
        "calendario.gestionar",
        "reservas.ver_de_mis_alojamientos",
        "perfil.gestionar",
        "cuenta.desactivar",
        "notificaciones.ver",
        "catalogo.ver",
    }),
    "ADMINISTRADOR": frozenset({
        "publicaciones.moderar",
        "reservas.resolver",
        "usuarios.ver",
        "usuarios.restringir",
        "tarifa.configurar",
        "auditoria.consultar",
        "tablero.ver",
        "reportes.descargar",
        "perfil.gestionar",
        "notificaciones.ver",
        "catalogo.ver",
        "roles.gestionar",
    }),
}

# Consultas de administración que solo dependen del permiso (sus services no revisan el rol).
CONSULTAS_ADMIN = frozenset({"usuarios.ver", "tablero.ver", "reportes.descargar", "auditoria.consultar"})

ASIGNABLES: dict[str, frozenset[str]] = {
    # El Visitante no tiene sesión: solo puede tener permisos públicos.
    VISITANTE: PERMISOS[VISITANTE],
    "HUESPED": PERMISOS["HUESPED"] | CONSULTAS_ADMIN,
    "ANFITRION": PERMISOS["ANFITRION"] | CONSULTAS_ADMIN | {"busqueda.ver"},
    "ADMINISTRADOR": PERMISOS["ADMINISTRADOR"] | {"busqueda.ver"},
}

FIJOS: dict[str, frozenset[str]] = {
    VISITANTE: frozenset({"catalogo.ver"}),
    "HUESPED": frozenset({"catalogo.ver"}),
    "ANFITRION": frozenset({"catalogo.ver"}),
    "ADMINISTRADOR": frozenset({"catalogo.ver", "roles.gestionar"}),
}

TODOS: frozenset[str] = frozenset(PERMISOS_INFO)


def rol_de(usuario) -> str:
    """El rol de la cuenta, o VISITANTE si no hay sesión."""
    if usuario is None or not getattr(usuario, "is_authenticated", False):
        return VISITANTE
    return usuario.rol


# De dónde salen los permisos vigentes de un rol. Identidad registra aquí su consulta a rol_permiso al iniciar
# (IdentidadConfig.ready). Es inversión de dependencia: comun no importa ninguna app, así cada app que usa
# RequierePermiso no queda atada a Identidad (contratos de import-linter, ADR-001).
_fuente: Callable[[str], frozenset[str]] | None = None


def registrar_fuente(consulta: Callable[[str], frozenset[str]]) -> None:
    global _fuente
    _fuente = consulta


def permisos_de(usuario) -> frozenset[str]:
    """Los permisos vigentes del rol, leídos de rol_permiso en cada llamada (ADR-010).

    No se guardan en caché: Gunicorn corre varios procesos y una caché en memoria dejaría a algunos con la matriz
    vieja después de un cambio. Es una consulta por la llave única (rol, permiso)."""
    if _fuente is None:
        raise ImproperlyConfigured("Identidad no registró la fuente de la matriz de permisos (rbac.registrar_fuente).")
    return _fuente(rol_de(usuario))


def tiene_alguno(usuario, permisos) -> bool:
    return not permisos_de(usuario).isdisjoint(permisos)
