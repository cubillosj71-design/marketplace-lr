"""Errores de negocio, respuestas uniformes y logs en JSON (RNF-O-OPE-01).

Las reglas de negocio lanzan ErrorNegocio con un código HTTP; la API responde
{"detalle": "...", "campo": "..."}. Las fallas no previstas van al log y a la auditoría como
ErrorOperacion con exitoso=False, fuera de cualquier transacción ("transacción propia").
"""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .eventos import ip_de

log = logging.getLogger("marketplace")


class ErrorNegocio(Exception):
    def __init__(self, detalle: str, codigo: int = status.HTTP_400_BAD_REQUEST, campo: str | None = None, extra: dict | None = None):
        super().__init__(detalle)
        self.detalle, self.codigo, self.campo, self.extra = detalle, codigo, campo, extra or {}


class NoEncontrado(ErrorNegocio):
    def __init__(self, detalle: str = "No existe."):
        super().__init__(detalle, status.HTTP_404_NOT_FOUND)


class SinPermiso(ErrorNegocio):
    def __init__(self, detalle: str = "No tienes permiso para esta acción."):
        super().__init__(detalle, status.HTTP_403_FORBIDDEN)


class Conflicto(ErrorNegocio):
    def __init__(self, detalle: str, extra: dict | None = None):
        super().__init__(detalle, status.HTTP_409_CONFLICT, extra=extra)


def manejar_excepcion(exc, contexto):
    if isinstance(exc, ErrorNegocio):
        cuerpo = {"detalle": exc.detalle, **({"campo": exc.campo} if exc.campo else {}), **exc.extra}
        return Response(cuerpo, status=exc.codigo)
    respuesta = exception_handler(exc, contexto)
    if respuesta is None:
        vista = contexto.get("view")
        log.exception("Falla no controlada", extra={"vista": type(vista).__name__ if vista else None})
        _auditar_falla(exc, contexto)
        return Response({"detalle": "Ocurrió un error inesperado. Intenta de nuevo."}, status=500)
    return respuesta


def _auditar_falla(exc, contexto) -> None:
    """RNF-O-OPE-01: la falla queda en la auditoría. Si ni eso se puede guardar (por ejemplo, la base
    no responde), queda solo en el log y la respuesta sigue siendo el 500 controlado."""
    from apps.auditoria import services as auditoria  # import tardío: comun se carga antes que las apps

    request = contexto.get("request")
    usuario = getattr(request, "user", None)
    try:
        auditoria.registrar(
            getattr(usuario, "id", None), "ErrorOperacion", exitoso=False, ip=ip_de(request),
            detalle={"error": type(exc).__name__, "mensaje": str(exc)[:300], "ruta": getattr(request, "path", None)},
        )
    except Exception:  # noqa: BLE001
        log.exception("No se pudo registrar la falla en la auditoría")
