"""Eventos de dominio (ADR-007, C4 nivel 3).

Solo para los eventos de dominio del diagrama: PublicacionAprobada, PublicacionDevuelta,
PublicacionBloqueada, PublicacionDesbloqueada, PublicacionPausada, PublicacionReactivada, ReservaConfirmada,
ReservaCancelada, ReservaEnRevision y ReservaResuelta.

Cada evento se entrega por dos señales, como en el diagrama C4 nivel 3:
- `evento_dominio_en_transaccion`: síncrona, dentro de la MISMA transacción de quien publica. La usa Reservas
  para pasar a EN_REVISION las reservas de una publicación bloqueada (CA-20.1): si algo falla, se revierte todo.
- `evento_dominio`: DESPUÉS de confirmar la transacción (transaction.on_commit). La usa Notificaciones para crear
  los avisos. Se envía con send_robust: si un receptor falla, la operación ya confirmada no se rompe.

La auditoría NO usa estos eventos: cada módulo llama a auditoria.services.registrar_evento() en la misma transacción
del cambio (C4 nivel 3, vista b).
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.dispatch import Signal

log = logging.getLogger("marketplace")

# Argumentos de ambas señales: nombre (str), usuario_id (int | None, quien lo provocó), entidad (str | None),
# entidad_id (int | None), detalle (dict)
evento_dominio_en_transaccion = Signal()
evento_dominio = Signal()

EVENTOS_DE_DOMINIO = frozenset({
    "PublicacionAprobada", "PublicacionDevuelta", "PublicacionBloqueada", "PublicacionDesbloqueada",
    "PublicacionPausada", "PublicacionReactivada",
    "ReservaConfirmada", "ReservaCancelada", "ReservaEnRevision", "ReservaResuelta",
})


def _ejecutar_despues_de_confirmar(nombre: str, datos: dict) -> None:
    for receptor, resultado in evento_dominio.send_robust(sender=nombre, **datos):
        if isinstance(resultado, Exception):
            log.error("Falló un receptor de %s: %r", nombre, resultado, extra={"evento": nombre})


def publicar_evento(
    nombre: str,
    *,
    usuario_id: int | None = None,
    entidad: str | None = None,
    entidad_id: int | None = None,
    detalle: dict[str, Any] | None = None,
) -> None:
    if nombre not in EVENTOS_DE_DOMINIO:
        raise ValueError(f"{nombre} no es un evento de dominio del diagrama; para auditar usa auditoria.services.registrar_evento().")
    datos = dict(nombre=nombre, usuario_id=usuario_id, entidad=entidad, entidad_id=entidad_id, detalle=detalle or {})
    evento_dominio_en_transaccion.send(sender=nombre, **datos)  # misma transacción: si falla, se revierte
    transaction.on_commit(lambda: _ejecutar_despues_de_confirmar(nombre, datos))


def obtener_ip(request) -> str | None:
    """IP del cliente; en Render llega en X-Forwarded-For.

    El proxy de Render AGREGA la IP real al final de la lista. Se toma la última y no la
    primera, porque la primera la puede escribir el propio cliente para fingir otra IP.
    """
    if request is None:
        return None
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR")
    return reenviada.split(",")[-1].strip() if reenviada else request.META.get("REMOTE_ADDR")
