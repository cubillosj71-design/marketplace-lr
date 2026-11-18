"""Permisos de DRF por rol (ADR-005). Cada acceso negado queda en la auditoría (CA-05.2).

El registro se hace con auditoria.services.registrar() fuera de cualquier transaction.atomic
("transacción propia"): queda guardado aunque la petición termine en 403.
"""

from rest_framework.permissions import BasePermission

from .eventos import ip_de


def _negar(request, view, motivo: str) -> bool:
    from apps.auditoria import services as auditoria  # import tardío: comun se carga antes que las apps

    usuario = getattr(request, "user", None)
    auditoria.registrar(
        getattr(usuario, "id", None),
        "AccesoDenegado",
        exitoso=False,
        detalle={"ruta": request.path, "metodo": request.method, "motivo": motivo},
        ip=ip_de(request),
    )
    return False


class TieneRol(BasePermission):
    """Uso: permission_classes = [TieneRol.de("ANFITRION", "ADMINISTRADOR")]."""

    roles: tuple[str, ...] = ()
    message = "No tienes permiso para esta acción."

    @classmethod
    def de(cls, *roles: str):
        return type(f"TieneRol_{'_'.join(roles)}", (cls,), {"roles": roles})

    def has_permission(self, request, view) -> bool:
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if u.rol in self.roles:
            return True
        return _negar(request, view, f"Rol {u.rol} sin acceso; se requiere {', '.join(self.roles)}")


EsAdministrador = TieneRol.de("ADMINISTRADOR")
EsAnfitrion = TieneRol.de("ANFITRION")
EsAnfitrionOAdministrador = TieneRol.de("ANFITRION", "ADMINISTRADOR")
EsHuespedOAnfitrion = TieneRol.de("HUESPED", "ANFITRION")


def negar_objeto(request, detalle: str) -> None:
    """Registra un intento sobre un recurso ajeno (CA-05.2) desde una vista."""
    _negar(request, None, detalle)
