"""Tareas programadas (C4 nivel 3: "Operación interna, rutas /interno").

Las corre una vez al día el workflow .github/workflows/tareas-diarias.yml (00:10 en Colombia) llamando a
POST /api/v1/interno/tareas/diarias, o una persona con `python manage.py tareas_diarias`.
"""

from __future__ import annotations

import hmac
import logging

from django.conf import settings

from apps.auditoria import services as auditoria
from apps.pagos import services as pagos
from apps.reservas import services as reservas

from .errores import auditar_falla

log = logging.getLogger("marketplace")


def ejecutar_tareas_diarias(origen: str, ip: str | None = None) -> dict:
    """En este orden: COMPLETADA (RF-D-RES-02.3), EN_REVISION vencidas (CA-20.5) y conciliación de pagos.

    Cada tarea va aislada: si una falla (por ejemplo, Stripe no responde en la conciliación), la falla queda en el
    log y en la auditoría y las demás se ejecutan igual. El resumen dice qué tarea falló (valor None y "errores")."""
    tareas = (
        ("reservas_completadas", reservas.completar_reservas_vencidas),
        ("reservas_canceladas_sin_resolucion", reservas.cancelar_en_revision_vencidas),
        ("pagos_conciliados", pagos.conciliar_pagos),
    )
    resultado: dict = {}
    errores: dict[str, str] = {}
    for nombre, tarea in tareas:
        try:
            resultado[nombre] = tarea()
        except Exception as e:  # noqa: BLE001  una tarea que falla no impide las demás
            log.exception("Falló una tarea diaria", extra={"tarea": nombre})
            auditar_falla(e, ip=ip, tarea=nombre, origen=origen)
            resultado[nombre], errores[nombre] = None, type(e).__name__
    if errores:
        resultado["errores"] = errores
    auditoria.registrar(None, "TareasDiarias", ip=ip, exitoso=not errores, detalle={"origen": origen, **resultado})
    return resultado


def token_valido(recibido: str | None) -> bool:
    """Compara el encabezado X-Token-Tareas con TOKEN_TAREAS. Sin TOKEN_TAREAS configurado, nada pasa."""
    esperado = getattr(settings, "TOKEN_TAREAS", "") or ""
    return bool(esperado) and bool(recibido) and hmac.compare_digest(recibido.encode(), esperado.encode())
