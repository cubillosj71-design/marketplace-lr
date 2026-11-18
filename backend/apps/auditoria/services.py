"""Interfaz pública de SRV-08 Auditoría (MOD-08, C4 nivel 3 vista b).

Es el único módulo que otros servicios pueden importar de esta app. Auditoría no depende de
ningún otro componente: cada módulo llama a `registrar()` dentro de la misma transacción del
cambio que audita. Así, si la transacción se revierte, el evento también; y si el evento no se
puede guardar, el cambio tampoco queda (RNF-E-CON-01).

Los inicios de sesión fallidos, los accesos negados y las fallas no controladas se registran
fuera de cualquier transaction.atomic ("transacción propia"), para que queden aunque la
petición termine en error.

Nadie fuera de apps.auditoria debe importar apps.auditoria.models (import-linter, ADR-001).
"""

from __future__ import annotations

from typing import Any

from .models import EventoAuditoria


def registrar(
    actor_id: int | None,
    accion: str,
    *,
    entidad: str | None = None,
    entidad_id: int | None = None,
    exitoso: bool = True,
    detalle: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    """Inserta un evento en evento_auditoria. Escribe directo, sin señales."""
    EventoAuditoria.objects.create(
        actor_id=actor_id, accion=accion[:50], entidad=entidad[:30] if entidad else None, entidad_id=entidad_id,
        exitoso=exitoso, detalle=detalle or None, ip=ip,
    )


def consultar(*, actor_id=None, accion=None, desde=None, hasta=None, exitoso=None):
    """Consulta para el administrador (RF-D-ADM-04.1, CA-23.1): filtra por usuario (actor), acción y periodo."""
    qs = EventoAuditoria.objects.all()
    if actor_id:
        qs = qs.filter(actor_id=actor_id)
    if accion:
        qs = qs.filter(accion=accion)
    if exitoso is not None:
        qs = qs.filter(exitoso=exitoso)
    if desde:
        qs = qs.filter(fecha__date__gte=desde)
    if hasta:
        qs = qs.filter(fecha__date__lte=hasta)
    return qs
