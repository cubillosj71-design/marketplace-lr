"""Interfaz pública de SRV-07 Notificaciones (MOD-07, HU-16, RF-D-RES-04.1).

Es el único módulo que otros servicios pueden importar de esta app; nadie fuera de apps.notificaciones importa
apps.notificaciones.models (import-linter, ADR-001). Notificaciones no importa modelos de otras apps: los
destinatarios y los textos llegan en el detalle de cada evento de dominio.

Recibe los eventos por `evento_dominio`, DESPUÉS de confirmar la transacción que los produjo (C4 nivel 3).
Si crear un aviso falla, lo registra en la auditoría en una transacción propia y no rompe la operación.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction

from apps.auditoria import services as auditoria
from apps.comun.errores import NoEncontrado

from .models import Notificacion

log = logging.getLogger("marketplace")


def _pesos(valor) -> str:
    return "$" + f"{int(Decimal(valor)):,}".replace(",", ".")


def _fecha(iso: str) -> str:
    anio, mes, dia = iso[:10].split("-")
    return f"{dia}/{mes}/{anio}"


def _reserva(d: dict, texto: str) -> str:
    fechas = f" del {_fecha(d['llegada'])} al {_fecha(d['salida'])}" if d.get("llegada") and d.get("salida") else ""
    return f"{texto}: «{d.get('titulo') or 'alojamiento'}»{fechas}."


def _cancelada(d: dict) -> str:
    texto = _reserva(d, "Reserva cancelada")
    if d.get("valor_devolucion") is not None:
        texto += f" Devolución: {_pesos(d['valor_devolucion'])}."
    if d.get("motivo"):
        texto += f" Motivo: {d['motivo']}"
    return texto


def _resuelta(d: dict) -> str:
    if d.get("mantener"):
        return _reserva(d, "Tu reserva se mantiene CONFIRMADA")
    return _reserva(d, "La revisión de tu reserva terminó con su cancelación")


# evento -> (destinatarios, mensaje). CA-16.3
AVISOS = {
    "ReservaConfirmada": (("huesped", "anfitrion"), lambda d: _reserva(d, "Nueva reserva confirmada")),
    "ReservaCancelada": (("huesped", "anfitrion"), _cancelada),
    "ReservaEnRevision": (("huesped", "anfitrion"), lambda d: _reserva(d, "Reserva EN_REVISION porque el alojamiento fue bloqueado")),
    "ReservaResuelta": (("huesped",), _resuelta),
    "PublicacionAprobada": (("anfitrion",), lambda d: f"Tu publicación «{d.get('titulo')}» fue aprobada y ya aparece en las búsquedas."),
    "PublicacionDevuelta": (("anfitrion",), lambda d: f"Tu publicación «{d.get('titulo')}» fue devuelta. Observación: {d.get('observacion', '')}"),
    "PublicacionBloqueada": (("anfitrion",), lambda d: f"Tu publicación «{d.get('titulo')}» fue bloqueada. Motivo: {d.get('observacion', '')}"),
    "PublicacionDesbloqueada": (("anfitrion",), lambda d: f"Tu publicación «{d.get('titulo')}» fue desbloqueada y quedó pausada. Puedes reactivarla."),
    "PublicacionPausada": (("anfitrion",), lambda d: f"El administrador pausó tu publicación «{d.get('titulo')}»."),
    "PublicacionReactivada": (("anfitrion",), lambda d: f"El administrador reactivó tu publicación «{d.get('titulo')}»."),
}
# Pausar y reactivar solo se avisan si lo hizo el Administrador (el anfitrión ya sabe lo que hizo él mismo)
SOLO_SI_ADMINISTRADOR = {"PublicacionPausada", "PublicacionReactivada"}


def obtener_destinatarios(nombre: str, detalle: dict) -> list[int]:
    if nombre not in AVISOS or (nombre in SOLO_SI_ADMINISTRADOR and not detalle.get("por_administrador")):
        return []
    ids = [detalle.get(clave) for clave in AVISOS[nombre][0]]
    return list(dict.fromkeys(i for i in ids if i))


def recibir_evento_dominio(sender, nombre, entidad=None, entidad_id=None, detalle=None, **_):
    """Receptor de evento_dominio (después de confirmar la transacción)."""
    detalle = detalle or {}
    try:
        para = obtener_destinatarios(nombre, detalle)
        if not para:
            return
        mensaje = AVISOS[nombre][1](detalle)[:300]
        with transaction.atomic():
            Notificacion.objects.bulk_create([
                Notificacion(destinatario_id=u, tipo=nombre[:40], mensaje=mensaje,
                             entidad=(entidad or "")[:30] or None, entidad_id=entidad_id)
                for u in para
            ])
    except Exception as e:  # noqa: BLE001  un aviso fallido no rompe la operación ya confirmada
        log.exception("No se pudo crear el aviso", extra={"evento": nombre})
        try:
            with transaction.atomic():  # transacción propia
                auditoria.registrar_evento(None, "NotificacionFallida", entidad=entidad, entidad_id=entidad_id, exitoso=False,
                                    detalle={"evento": nombre, "error": type(e).__name__, "mensaje": str(e)[:300]})
        except Exception:  # noqa: BLE001
            log.exception("Tampoco se pudo registrar la falla del aviso")


# ---------------------------------------------------------------- bandeja (CA-16.2)

def _dict(n: Notificacion) -> dict:
    return {"id": n.id, "tipo": n.tipo, "mensaje": n.mensaje, "entidad": n.entidad, "entidad_id": n.entidad_id,
            "leida": n.leida, "fecha": n.fecha}


def consultar_bandeja(usuario, limite: int = 100) -> dict:
    """Primero las no leídas y luego por fecha, con el conteo de no leídas."""
    qs = Notificacion.objects.filter(destinatario_id=usuario.id)
    return {"no_leidas": qs.filter(leida=False).count(),
            "notificaciones": [_dict(n) for n in qs.order_by("leida", "-fecha", "-id")[:limite]]}


def marcar_leida(usuario, notificacion_id: int) -> dict:
    n = Notificacion.objects.filter(pk=notificacion_id, destinatario_id=usuario.id).first()
    if not n:
        raise NoEncontrado("La notificación no existe.")
    n.marcar_leida()
    return _dict(n)


def marcar_todas_leidas(usuario) -> int:
    return Notificacion.objects.filter(destinatario_id=usuario.id, leida=False).update(leida=True)
