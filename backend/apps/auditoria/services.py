"""Interfaz pública de SRV-08 Auditoría.

Es el único módulo que otros servicios pueden importar de esta app.
Nadie fuera de apps.auditoria debe importar apps.auditoria.models (regla verificada
con import-linter en el pipeline, ADR-001).
"""

import logging

from .models import EventoAuditoria

log = logging.getLogger("marketplace")


def registrar_evento(sender, nombre, usuario_id=None, entidad=None, entidad_id=None, resultado="EXITO", detalle=None, ip=None, **_):
    """Suscriptor de evento_dominio. Si falla, deja la falla en el log y no interrumpe la operación."""
    try:
        EventoAuditoria.objects.create(
            usuario_id=usuario_id, accion=nombre[:50], entidad=entidad, entidad_id=entidad_id,
            resultado=resultado, detalle=detalle or None, ip=ip,
        )
    except Exception:  # noqa: BLE001
        log.exception("No se pudo registrar el evento de auditoría", extra={"evento": nombre})


def consultar(*, usuario_id=None, accion=None, desde=None, hasta=None, resultado=None):
    qs = EventoAuditoria.objects.all()
    if usuario_id:
        qs = qs.filter(usuario_id=usuario_id)
    if accion:
        qs = qs.filter(accion=accion)
    if resultado:
        qs = qs.filter(resultado=resultado)
    if desde:
        qs = qs.filter(fecha__date__gte=desde)
    if hasta:
        qs = qs.filter(fecha__date__lte=hasta)
    return qs
