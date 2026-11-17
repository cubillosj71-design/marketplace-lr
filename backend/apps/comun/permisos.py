"""Permisos de DRF por rol (ADR-005). Cada acceso negado publica AccesoDenegado para la auditoría."""

from rest_framework.permissions import BasePermission

from .eventos import ip_de, publicar


def _negar(request, view, motivo: str) -> bool:
    usuario = getattr(request, "user", None)
    publicar(
        "AccesoDenegado",
        usuario_id=getattr(usuario, "id", None),
        resultado="FALLO",
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
