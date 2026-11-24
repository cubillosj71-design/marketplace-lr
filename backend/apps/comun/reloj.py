"""Reloj de la aplicación (hora de Colombia, TIME_ZONE = America/Bogota).

Las reglas que dependen de la fecha (cancelación por días de anticipación, COMPLETADA, reservas EN_REVISION
vencidas, límite de 12 meses) leen la hora aquí y no directamente de timezone.now(). Así las pruebas pueden
fijar el día con `fijar_fecha_hora()` y reproducir los ejemplos del SRS (CA-15.1: cancelar el 15 de noviembre).
"""

from __future__ import annotations

from datetime import date, datetime

from django.utils import timezone

_fijo: datetime | None = None


def obtener_fecha_hora() -> datetime:
    return _fijo if _fijo is not None else timezone.now()


def obtener_fecha_hoy() -> date:
    """Fecha calendario en Colombia."""
    return timezone.localdate(obtener_fecha_hora())


def fijar_fecha_hora(momento: datetime | None) -> None:
    """Solo para pruebas: fija la hora actual (None vuelve al reloj real)."""
    global _fijo
    _fijo = momento
