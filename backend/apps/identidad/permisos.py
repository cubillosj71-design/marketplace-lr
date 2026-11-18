"""Permisos por rol para las vistas de todos los servicios (RF-D-USU-02.1, HU-05, ADR-005).

Cada servicio los usa en sus vistas en lugar de revisar el rol a mano:

    from apps.identidad.permisos import Rol, EsDuenoOAdministrador, solo_roles

    class PublicacionDetalle(APIView):
        permission_classes = [solo_roles(Rol.ANFITRION, Rol.ADMINISTRADOR), EsDuenoOAdministrador]
        campo_dueno = "anfitrion_id"   # atributo del objeto con el id del dueño

Para dos o más roles usen solo_roles(...) y no "EsAnfitrion | EsAdministrador":
con el operador |, DRF evalúa primero EsAnfitrion, que registraría un acceso
denegado falso cada vez que entra un Administrador.

Por qué así:
- Sin sesión, DRF responde 401 y el front-end manda a iniciar sesión (CA-05.1).
- Con sesión pero sin el rol, responde 403 y el intento queda en el registro de
  acciones (CA-05.2, RF-D-ADM-04.1).
- La regla vive en un solo lugar: si cambia, no hay que buscarla en nueve apps
  (RNF-O-DES-01).
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from apps.auditoria import services as auditoria
from apps.auditoria.services import Accion

from .models import RolUsuario

# Los otros servicios no pueden importar apps.identidad.models (ADR-001), así
# que el enum de roles se expone desde aquí.
Rol = RolUsuario


def _registrar_acceso_denegado(request, view, motivo: str) -> None:
    auditoria.registrar(
        Accion.ACCESO_DENEGADO,
        exitoso=False,
        actor_id=request.user.pk,
        detalle={"motivo": motivo, "metodo": request.method, "ruta": request.path, "vista": type(view).__name__},
        ip=auditoria.ip_de_la_peticion(request),
    )


class TieneRol(BasePermission):
    """Base: deja pasar solo a usuarios autenticados cuyo rol esté en ``roles``."""

    roles: tuple[str, ...] = ()
    message = "Tu rol no tiene permiso para usar esta función."

    def has_permission(self, request, view) -> bool:
        usuario = request.user
        if not (usuario and usuario.is_authenticated):
            # False sin registrar: DRF lo convierte en 401 porque la
            # autenticación por JWT define el encabezado WWW-Authenticate.
            return False
        if usuario.rol in self.roles:
            return True
        _registrar_acceso_denegado(request, view, f"rol {usuario.rol} sin permiso")
        return False


class EsHuesped(TieneRol):
    roles = (RolUsuario.HUESPED,)


class EsAnfitrion(TieneRol):
    roles = (RolUsuario.ANFITRION,)


class EsAdministrador(TieneRol):
    roles = (RolUsuario.ADMINISTRADOR,)


class EsHuespedOAnfitrion(TieneRol):
    roles = (RolUsuario.HUESPED, RolUsuario.ANFITRION)


def solo_roles(*roles: str) -> type[TieneRol]:
    """Crea un permiso que deja pasar a cualquiera de los roles indicados."""
    return type(f"SoloRoles_{'_'.join(roles)}", (TieneRol,), {"roles": tuple(roles)})


class EsDuenoOAdministrador(BasePermission):
    """Permiso sobre un objeto concreto: solo su dueño o un Administrador (CA-05.3, RF-D-ALO-02.1).

    La vista indica en ``campo_dueno`` qué atributo del objeto guarda el id del
    dueño (por ejemplo ``anfitrion_id``). DRF lo evalúa en get_object().
    """

    message = "Solo el dueño de este recurso o un Administrador pueden modificarlo."

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.rol == RolUsuario.ADMINISTRADOR:
            return True
        campo = getattr(view, "campo_dueno", None)
        if campo is None:
            raise AttributeError(f"{type(view).__name__} debe definir campo_dueno para usar EsDuenoOAdministrador")
        if getattr(obj, campo, None) == request.user.pk:
            return True
        _registrar_acceso_denegado(request, view, "no es el dueño del recurso")
        return False
