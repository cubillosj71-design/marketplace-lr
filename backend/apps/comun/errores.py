"""Errores de negocio, respuestas uniformes y logs en JSON (RNF-O-OPE-01).

Las reglas de negocio lanzan ErrorNegocio con un código HTTP; la API responde
{"detalle": "...", "campo": "..."}. Las fallas no previstas van al log y a la auditoría como
ErrorOperacion con exitoso=False, fuera de cualquier transacción ("transacción propia").
"""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .eventos import obtener_ip

log = logging.getLogger("marketplace")


class ErrorNegocio(Exception):
    """Regla de negocio que no se cumple: la API responde con el código y el mensaje para el usuario.

    Las lanzan los services; manejar_excepcion() la convierte en {"detalle", "campo"?, ...extra}.

    Attributes:
        detalle: mensaje en lenguaje claro para mostrar en pantalla.
        codigo: código HTTP de la respuesta (400 por defecto).
        campo: campo del formulario al que se refiere el error, si aplica.
        extra: datos adicionales que se agregan a la respuesta (por ejemplo, las reservas pendientes).
    """
    def __init__(self, detalle: str, codigo: int = status.HTTP_400_BAD_REQUEST, campo: str | None = None, extra: dict | None = None):
        super().__init__(detalle)
        self.detalle, self.codigo, self.campo, self.extra = detalle, codigo, campo, extra or {}


class NoEncontrado(ErrorNegocio):
    """El recurso pedido no existe: la API responde 404."""
    def __init__(self, detalle: str = "No existe."):
        super().__init__(detalle, status.HTTP_404_NOT_FOUND)


class SinPermiso(ErrorNegocio):
    """Quien llama no puede hacer la acción (por ejemplo, ver una reserva ajena): la API responde 403."""
    def __init__(self, detalle: str = "No tienes permiso para esta acción."):
        super().__init__(detalle, status.HTTP_403_FORBIDDEN)


class Conflicto(ErrorNegocio):
    """La acción choca con el estado actual de los datos: la API responde 409.

    Ejemplos: correo ya registrado, fechas ya ocupadas, publicación que cambió mientras tanto.
    """
    def __init__(self, detalle: str, extra: dict | None = None):
        super().__init__(detalle, status.HTTP_409_CONFLICT, extra=extra)


def manejar_excepcion(exc, contexto):
    """Manejador de excepciones de DRF (REST_FRAMEWORK["EXCEPTION_HANDLER"]).

    - ErrorNegocio: responde su código y {"detalle", "campo"?, ...extra}.
    - Errores que DRF ya sabe responder (validación, 401, 403, 404, 429): los deja como DRF los arma.
    - Cualquier otra excepción: la registra en el log y en la auditoría (ErrorOperacion) y responde
      500 con un mensaje genérico, sin detalles internos (RNF-O-OPE-01).

    Args:
        exc: la excepción que se lanzó en la vista.
        contexto: contexto de DRF con la vista y la petición.

    Returns:
        La respuesta HTTP que recibe el cliente.
    """
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
    """Registra en la auditoría una falla no prevista de la API, con el usuario, la IP y la ruta de la petición."""
    request = contexto.get("request")
    usuario = getattr(request, "user", None)
    auditar_falla(exc, actor_id=getattr(usuario, "id", None), ip=obtener_ip(request), ruta=getattr(request, "path", None))


def auditar_falla(exc: Exception, *, actor_id: int | None = None, ip: str | None = None, entidad: str | None = None,
                  entidad_id: int | None = None, **detalle) -> None:
    """RNF-O-OPE-01: la falla queda en la auditoría como ErrorOperacion, en su propia transacción. Si ni eso se
    puede guardar (por ejemplo, la base no responde), queda solo en el log y quien llama sigue su camino.
    La usan el manejador de la API (500 controlado) y las tareas en lote (una falla no detiene las demás)."""
    from django.db import transaction

    from apps.auditoria import services as auditoria  # import tardío: comun se carga antes que las apps

    try:
        with transaction.atomic():
            auditoria.registrar_evento(actor_id, "ErrorOperacion", exitoso=False, ip=ip, entidad=entidad, entidad_id=entidad_id,
                                detalle={"error": type(exc).__name__, "mensaje": str(exc)[:300], **detalle})
    except Exception:  # noqa: BLE001
        log.exception("No se pudo registrar la falla en la auditoría")
