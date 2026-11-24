"""Reglas de fechas compartidas por el calendario, la búsqueda, la cotización y la reserva.

RF-D-ALO-02.2: no se aceptan fechas con salida posterior a hoy + 12 meses.
"""

from __future__ import annotations

import calendar
from datetime import date

from . import reloj
from .errores import ErrorNegocio

MESES_MAXIMOS = 12


def sumar_meses(d: date, meses: int) -> date:
    """Suma meses a una fecha sin pasarse del último día del mes de llegada.

    Ejemplo: 31 de enero + 1 mes = 28 (o 29) de febrero.

    Args:
        d: fecha de partida.
        meses: meses que se suman.

    Returns:
        La fecha resultante.
    """
    m = d.month - 1 + meses
    anio, mes = d.year + m // 12, m % 12 + 1
    return date(anio, mes, min(d.day, calendar.monthrange(anio, mes)[1]))


def calcular_fecha_maxima(hoy: date | None = None) -> date:
    """Última fecha de salida aceptada: hoy + 12 meses."""
    return sumar_meses(hoy or reloj.obtener_fecha_hoy(), MESES_MAXIMOS)


def validar_estancia(llegada: date, salida: date, *, permitir_pasado: bool = False,
                     campo_llegada: str = "fecha_llegada", campo_salida: str = "fecha_salida") -> int:
    """Valida el rango [llegada, salida) y devuelve el número de noches."""
    if salida <= llegada:  # CA-10.3
        raise ErrorNegocio("La fecha de salida debe ser posterior a la de llegada.", campo=campo_salida)
    if not permitir_pasado and llegada < reloj.obtener_fecha_hoy():
        raise ErrorNegocio("La fecha de llegada no puede ser anterior a hoy.", campo=campo_llegada)
    limite = calcular_fecha_maxima()
    if salida > limite:  # RF-D-ALO-02.2
        raise ErrorNegocio(f"Solo se aceptan fechas hasta el {limite:%d/%m/%Y} (12 meses desde hoy).", campo=campo_salida)
    return (salida - llegada).days
