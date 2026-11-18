"""Eventos de dominio (ADR-007).

Solo para los eventos de dominio del diagrama: PublicacionAprobada, PublicacionDevuelta,
PublicacionBloqueada, PublicacionDesbloqueada, PublicacionPausada y PublicacionReactivada (más
adelante ReservaConfirmada, ReservaCancelada, ReservaEnRevision y ReservaResuelta). Los reciben
Reservas y Notificaciones conectándose a la señal `evento_dominio`, sin que quien publica los conozca.

La auditoría NO usa estos eventos: cada módulo llama a auditoria.services.registrar() en la misma
transacción del cambio (C4 nivel 3, vista b).

El envío se hace con transaction.on_commit, así un evento solo sale si la transacción se guardó.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.dispatch import Signal

# Argumentos: nombre (str), usuario_id (int | None, quien lo provocó), entidad (str | None),
# entidad_id (int | None), detalle (dict)
evento_dominio = Signal()

EVENTOS_DE_DOMINIO = frozenset({
    "PublicacionAprobada", "PublicacionDevuelta", "PublicacionBloqueada", "PublicacionDesbloqueada",
    "PublicacionPausada", "PublicacionReactivada",
    "ReservaConfirmada", "ReservaCancelada", "ReservaEnRevision", "ReservaResuelta",
})


def publicar(
    nombre: str,
    *,
    usuario_id: int | None = None,
    entidad: str | None = None,
    entidad_id: int | None = None,
    detalle: dict[str, Any] | None = None,
) -> None:
    if nombre not in EVENTOS_DE_DOMINIO:
        raise ValueError(f"{nombre} no es un evento de dominio del diagrama; para auditar usa auditoria.services.registrar().")
    datos = dict(nombre=nombre, usuario_id=usuario_id, entidad=entidad, entidad_id=entidad_id, detalle=detalle or {})
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
