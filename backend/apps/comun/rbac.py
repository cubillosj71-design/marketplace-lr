"""Matriz de permisos por rol (RF-D-USU-02.1, HU-05, ADR-005).

Cada cuenta tiene un único rol (usuario.rol) y quien no ha iniciado sesión es VISITANTE. Un permiso dice QUÉ puede
hacer un rol, con el formato "modulo.accion"; SOBRE QUÉ recurso (la regla de dueño, CA-05.3) lo revisa cada service.
Las vistas lo exigen con apps.comun.permisos.RequierePermiso.

No usa tablas: la matriz vive en el código y el esquema de la base no cambia.
"""

VISITANTE = "VISITANTE"

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
    }),
}

TODOS: frozenset[str] = frozenset().union(*PERMISOS.values())


def obtener_rol(usuario) -> str:
    """El rol de la cuenta, o VISITANTE si no hay sesión."""
    if usuario is None or not getattr(usuario, "is_authenticated", False):
        return VISITANTE
    return usuario.rol


def obtener_permisos(usuario) -> frozenset[str]:
    """Permisos del rol del usuario según la matriz PERMISOS (RF-D-USU-02.1).

    Args:
        usuario: el usuario de la petición; sin sesión se toman los del VISITANTE.

    Returns:
        El conjunto de permisos del rol (vacío si el rol no está en la matriz).
    """
    return PERMISOS.get(obtener_rol(usuario), frozenset())


def tiene_alguno(usuario, permisos) -> bool:
    """Indica si el usuario tiene al menos uno de los permisos dados.

    Args:
        usuario: el usuario de la petición.
        permisos: permisos aceptados (basta uno).

    Returns:
        True si su rol tiene alguno.
    """
    return not obtener_permisos(usuario).isdisjoint(permisos)
