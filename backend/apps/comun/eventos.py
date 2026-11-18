"""Eventos de dominio (ADR-007).

Los servicios publican hechos con `publicar`; los suscriptores (Auditoría, Notificaciones, Reservas)
se conectan a la señal `evento_dominio` sin que quien publica los conozca. El envío se hace con
transaction.on_commit, así un evento solo sale si la transacción se guardó. Fuera de una
transacción (por ejemplo, un acceso denegado) sale de inmediato.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.dispatch import Signal

# Argumentos: nombre (str), usuario_id (int | None), entidad (str | None), entidad_id (int | None),
# resultado ("EXITO" | "FALLO"), detalle (dict), ip (str | None)
evento_dominio = Signal()


def publicar(
    nombre: str,
    *,
    usuario_id: int | None = None,
    entidad: str | None = None,
    entidad_id: int | None = None,
    resultado: str = "EXITO",
    detalle: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    datos = dict(
        nombre=nombre, usuario_id=usuario_id, entidad=entidad, entidad_id=entidad_id,
        resultado=resultado, detalle=detalle or {}, ip=ip,
    )
    transaction.on_commit(lambda: evento_dominio.send(sender=nombre, **datos))


def ip_de(request) -> str | None:
    """IP del cliente; en Render llega en X-Forwarded-For.

    El proxy de Render AGREGA la IP real al final de la lista. Se toma la última y no la
    primera, porque la primera la puede escribir el propio cliente para fingir otra IP.
    """
    if request is None:
        return None
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR")
    return reenviada.split(",")[-1].strip() if reenviada else request.META.get("REMOTE_ADDR")
