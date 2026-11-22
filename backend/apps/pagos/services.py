"""Interfaz pública de SRV-05 Pagos (MOD-05).

Es el único módulo que otros servicios pueden importar de esta app. Nadie fuera de apps.pagos debe
importar apps.pagos.models (import-linter, ADR-001). Pagos no depende de Reservas: recibe la cotización
como objeto (con id y total) y el id de la reserva.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from django.db import transaction

from apps.auditoria import services as auditoria
from apps.comun.errores import auditar_falla

from .models import EstadoPago, Pago, TipoPago
from .pasarela import AdaptadorSimulado, PasarelaPagos, obtener_pasarela


class ServicioPagos:
    def __init__(self, pasarela: PasarelaPagos | None = None):
        self.pasarela = pasarela or obtener_pasarela()

    def cobrar_cotizacion(self, cotizacion, clave: UUID, medio: str, *, reserva_id: int | None = None,
               actor_id: int | None = None, ip: str | None = None) -> Pago:
        """Cobra el total de la cotización y guarda el pago con su estado.

        Debe llamarse dentro de la transacción de la reserva: el pago y su evento de auditoría se
        guardan en esa misma transacción, así si la reserva se revierte no queda un pago a medias
        (RNF-P-FIA-03). La pasarela recibe la clave como llave de idempotencia (RNF-P-FIA-02).
        """
        resultado = self.pasarela.cobrar(cotizacion.total, clave, medio)
        pago = Pago.objects.create(
            cotizacion_id=cotizacion.id, reserva_id=reserva_id, tipo=TipoPago.COBRO, monto=cotizacion.total,
            estado=resultado.estado, referencia_externa=resultado.referencia, clave_idempotencia=clave,
        )
        pago.motivo = resultado.motivo  # no se guarda: es el mensaje para el huésped
        aprobado = resultado.estado == EstadoPago.APROBADO
        auditoria.registrar(
            actor_id, "PagoAprobado" if aprobado else "PagoNoAprobado", entidad="Pago", entidad_id=pago.id,
            exitoso=aprobado, ip=ip,
            detalle={"estado": pago.estado, "monto": str(pago.monto), "cotizacion": cotizacion.id, "reserva": reserva_id,
                     "referencia": pago.referencia_externa, **({"motivo": resultado.motivo} if resultado.motivo else {})},
        )
        return pago

    def devolver_pago(self, *, cotizacion_id: int, reserva_id: int, monto: Decimal, actor_id: int | None = None,
                 ip: str | None = None) -> Pago | None:
        """Devolución de una cancelación (RF-D-RES-03.1): pide a la pasarela devolver(referencia, monto) sobre el
        cobro aprobado de la cotización y guarda el pago DEVOLUCION con el estado que responda.

        Debe llamarse dentro de la transacción de la cancelación. Si el valor es 0 no se crea pago
        (pago.monto > 0). La devolución va por la misma pasarela que hizo el cobro: un cobro simulado (SIM-...)
        se devuelve con el simulado aunque ahora haya llave de Stripe."""
        if monto <= 0:
            return None
        cobro = (Pago.objects.filter(cotizacion_id=cotizacion_id, tipo=TipoPago.COBRO, estado=EstadoPago.APROBADO)
                 .order_by("-fecha").first())
        referencia = cobro.referencia_externa if cobro else None
        pasarela = self.pasarela if referencia and not referencia.startswith("SIM-") else AdaptadorSimulado()
        resultado = pasarela.devolver(referencia or "", monto)
        pago = Pago.objects.create(
            cotizacion_id=cotizacion_id, reserva_id=reserva_id, tipo=TipoPago.DEVOLUCION, monto=monto,
            estado=resultado.estado, referencia_externa=resultado.referencia, clave_idempotencia=uuid4(),
        )
        aprobada = resultado.estado == EstadoPago.APROBADO
        auditoria.registrar(actor_id, "DevolucionRegistrada", entidad="Pago", entidad_id=pago.id, ip=ip, exitoso=aprobada,
                            detalle={"reserva": reserva_id, "monto": str(monto), "estado": pago.estado,
                                     "referencia": pago.referencia_externa, "cobro": referencia,
                                     **({"motivo": resultado.motivo} if resultado.motivo else {})})
        return pago


def conciliar_pagos() -> int:
    """Tarea diaria: los pagos EN_VERIFICACION se consultan en la pasarela y se actualizan (estado y referencia,
    lo único que permite el trigger de pago). Devuelve cuántos pagos cambiaron."""
    pasarela = obtener_pasarela()
    cambiados = 0
    for pago in Pago.objects.filter(estado=EstadoPago.EN_VERIFICACION):
        try:
            resultado = pasarela.consultar(pago.clave_idempotencia)
        except Exception as e:  # noqa: BLE001  la pasarela no respondió por este pago: se reintenta mañana
            auditar_falla(e, entidad="Pago", entidad_id=pago.id, tarea="conciliar_pagos")
            continue
        if not resultado or resultado.estado == pago.estado:
            continue
        with transaction.atomic():
            anterior = pago.estado
            pago.estado, pago.referencia_externa = resultado.estado, resultado.referencia or pago.referencia_externa
            pago.save(update_fields=["estado", "referencia_externa"])
            auditoria.registrar(None, "PagoConciliado", entidad="Pago", entidad_id=pago.id,
                                detalle={"de": anterior, "a": pago.estado, "referencia": pago.referencia_externa})
        cambiados += 1
    return cambiados


def listar_pagos_de_reserva(reserva_id: int) -> list[dict]:
    return [{"id": p.id, "tipo": p.tipo, "monto": f"{p.monto:.2f}", "estado": p.estado,
             "referencia_externa": p.referencia_externa, "fecha": p.fecha}
            for p in Pago.objects.filter(reserva_id=reserva_id).order_by("fecha")]
