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


def _formatear_pesos(valor) -> str:
    """Formatea un monto en pesos colombianos para un aviso: $370.000."""
    return "$" + f"{int(Decimal(valor)):,}".replace(",", ".")


def _formatear_fecha(iso: str) -> str:
    """Convierte una fecha ISO (AAAA-MM-DD) al formato DD/MM/AAAA de los avisos."""
    anio, mes, dia = iso[:10].split("-")
    return f"{dia}/{mes}/{anio}"


def _describir_reserva(d: dict, texto: str) -> str:
    """Arma el texto base de un aviso de reserva: «título» y fechas de llegada y salida.

    Args:
        d: detalle del evento (titulo, llegada, salida).
        texto: comienzo del mensaje (por ejemplo, "Reserva confirmada").
    """
    fechas = f" del {_formatear_fecha(d['llegada'])} al {_formatear_fecha(d['salida'])}" if d.get("llegada") and d.get("salida") else ""
    return f"{texto}: «{d.get('titulo') or 'alojamiento'}»{fechas}."


def _describir_cancelacion(d: dict) -> str:
    """Arma el aviso de una reserva cancelada, con el valor devuelto y el motivo si los hay."""
    texto = _describir_reserva(d, "Reserva cancelada")
    if d.get("valor_devolucion") is not None:
        texto += f" Devolución: {_formatear_pesos(d['valor_devolucion'])}."
    if d.get("motivo"):
        texto += f" Motivo: {d['motivo']}"
    return texto


def _describir_resolucion(d: dict) -> str:
    """Arma el aviso del resultado de una reserva en revisión: se mantiene o se cancela."""
    if d.get("mantener"):
        return _describir_reserva(d, "Tu reserva se mantiene CONFIRMADA")
    return _describir_reserva(d, "La revisión de tu reserva terminó con su cancelación")


# evento -> (destinatarios, mensaje). CA-16.3
AVISOS = {
    "ReservaConfirmada": (("huesped", "anfitrion"), lambda d: _describir_reserva(d, "Nueva reserva confirmada")),
    "ReservaCancelada": (("huesped", "anfitrion"), _describir_cancelacion),
    "ReservaEnRevision": (("huesped", "anfitrion"), lambda d: _describir_reserva(d, "Reserva EN_REVISION porque el alojamiento fue bloqueado")),
    "ReservaResuelta": (("huesped",), _describir_resolucion),
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
    """Usuarios que deben recibir el aviso de un evento.

    Args:
        nombre: nombre del evento de dominio.
        detalle: detalle del evento, con los ids de huésped, anfitrión, etc.

    Returns:
        Ids de los destinatarios sin repetir. Vacío si el evento no genera aviso o si solo avisa cuando
        lo provocó el Administrador y no fue así.
    """
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

def _serializar_notificacion(n: Notificacion) -> dict:
    """Convierte un aviso en el diccionario que devuelve la API de la bandeja."""
    return {"id": n.id, "tipo": n.tipo, "mensaje": n.mensaje, "entidad": n.entidad, "entidad_id": n.entidad_id,
            "leida": n.leida, "fecha": n.fecha}


def consultar_bandeja(usuario, limite: int = 100) -> dict:
    """Primero las no leídas y luego por fecha, con el conteo de no leídas."""
    qs = Notificacion.objects.filter(destinatario_id=usuario.id)
    return {"no_leidas": qs.filter(leida=False).count(),
            "notificaciones": [_serializar_notificacion(n) for n in qs.order_by("leida", "-fecha", "-id")[:limite]]}


def marcar_leida(usuario, notificacion_id: int) -> dict:
    """Marca como leído un aviso del usuario (CA-16.3).

    Args:
        usuario: quien llama; solo puede marcar sus propios avisos.
        notificacion_id: id del aviso.

    Returns:
        El aviso actualizado.

    Raises:
        NoEncontrado: si el aviso no existe o es de otro usuario.
    """
    n = Notificacion.objects.filter(pk=notificacion_id, destinatario_id=usuario.id).first()
    if not n:
        raise NoEncontrado("La notificación no existe.")
    n.marcar_leida()
    return _serializar_notificacion(n)


def marcar_todas_leidas(usuario) -> int:
    """Marca como leídos todos los avisos pendientes del usuario.

    Returns:
        Cuántos avisos cambiaron.
    """
    return Notificacion.objects.filter(destinatario_id=usuario.id, leida=False).update(leida=True)
