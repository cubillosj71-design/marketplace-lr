"""Permiso de DRF basado en la matriz de apps.comun.rbac (RF-D-USU-02.1, ADR-005).

Uso: permission_classes = [RequierePermiso("reservas.crear")]. Con varios permisos basta tener uno de ellos.

- El rol tiene el permiso: pasa. La regla de dueño (CA-05.3) la revisa el service.
- Sin sesión y el VISITANTE no tiene el permiso: 401.
- Con sesión y sin el permiso: 403, y el intento queda en la auditoría con exitoso=False, la ruta y el permiso
  que faltó (CA-05.2). Se registra con auditoria.services.registrar_evento() fuera de cualquier transaction.atomic
  ("transacción propia"), así queda guardado aunque la petición termine en 403.
"""

from django.core.exceptions import ImproperlyConfigured
from rest_framework.permissions import BasePermission

from . import rbac
from .eventos import obtener_ip


def _negar_acceso(request, detalle: dict) -> None:
    """Registra el intento de usar una función sin permiso (AccesoDenegado, CA-05.2).

    Se registra fuera de cualquier transacción para que quede aunque la petición termine en error.

    Args:
        request: la petición negada.
        detalle: datos del intento (permiso que faltó y rol de quien llamó).
    """
    from apps.auditoria import services as auditoria  # import tardío: comun se carga antes que las apps

    usuario = getattr(request, "user", None)
    auditoria.registrar_evento(
        getattr(usuario, "id", None),
        "AccesoDenegado",
        exitoso=False,
        detalle={"ruta": request.path, "metodo": request.method, **detalle},
        ip=obtener_ip(request),
    )


class RequierePermiso(BasePermission):
    """Se declara como instancia; DRF la "instancia" llamándola, y devuelve la misma (no guarda estado)."""

    message = "No tienes permiso para esta acción."

    def __init__(self, *permisos: str):
        desconocidos = set(permisos) - rbac.TODOS
        if not permisos or desconocidos:
            raise ImproperlyConfigured(f"Permiso que no está en la matriz de rbac: {sorted(desconocidos) or 'ninguno'}")
        self.permisos = permisos

    def __call__(self):
        """DRF instancia cada permission_class; este objeto ya es la instancia, así que se devuelve a sí mismo."""
        return self

    def __repr__(self):
        """Representación legible con los permisos que exige (se ve en errores y en las pruebas)."""
        return f"RequierePermiso({', '.join(map(repr, self.permisos))})"

    def has_permission(self, request, view) -> bool:
        """Decide si la petición pasa según el rol de quien llama y la matriz de apps.comun.rbac.

        Basta con tener uno de los permisos exigidos. Sin sesión, DRF responde 401; con sesión y sin el
        permiso, responde 403 y el intento queda en la auditoría.

        Args:
            request: la petición.
            view: la vista que se va a ejecutar.

        Returns:
            True si el rol tiene alguno de los permisos.
        """
        usuario = request.user
        if rbac.tiene_alguno(usuario, self.permisos):
            return True
        if usuario and usuario.is_authenticated:  # sin sesión: DRF responde 401 y no se registra
            _negar_acceso(request, {"permiso": " o ".join(self.permisos), "rol": usuario.rol})
        return False

