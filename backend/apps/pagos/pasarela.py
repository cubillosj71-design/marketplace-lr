"""Pasarela de pagos de MOD-05 (diagrama de clases): interfaz PasarelaPagos y sus dos adaptadores (ADR-006).

- AdaptadorStripe: Stripe en modo prueba con PaymentIntent. El frontend tokeniza la tarjeta con Stripe
  Elements y manda el payment_method (pm_...); aquí se crea y se confirma el PaymentIntent con
  idempotency_key = clave, así un reintento con la misma clave nunca cobra dos veces.
- AdaptadorSimulado: aprueba siempre, salvo que el medio sea "rechazar" (para probar CA-13.3).

devolver(referencia, monto) reembolsa parte o todo un cobro (RF-D-RES-03.1). La referencia es la del cobro
(pi_... en Stripe). Se usa la llave de idempotencia "devolucion-<referencia>": una reserva se cancela una sola
vez, así que un cobro tiene a lo sumo una devolución y un reintento nunca devuelve dos veces.

Se elige por variable de entorno: si existe STRIPE_SECRET_KEY se usa Stripe; si no, el simulado.
La llave solo llega por variables de entorno (.env, Render): nunca va en el código ni en el repositorio.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from django.conf import settings

from .models import EstadoPago


@dataclass(frozen=True)
class ResultadoPago:
    """EstadoPago que devuelve la pasarela, con la referencia externa y, si no se aprobó, el motivo."""

    estado: str
    referencia: str | None = None
    motivo: str | None = None


class PasarelaPagos(ABC):
    @abstractmethod
    def cobrar(self, monto: Decimal, clave: UUID, medio: str) -> ResultadoPago: ...

    @abstractmethod
    def devolver(self, referencia: str, monto: Decimal) -> ResultadoPago: ...

    @abstractmethod
    def consultar(self, clave: UUID) -> ResultadoPago | None: ...


class AdaptadorSimulado(PasarelaPagos):
    MEDIO_RECHAZO = "rechazar"

    def cobrar(self, monto: Decimal, clave: UUID, medio: str) -> ResultadoPago:
        if (medio or "").strip().lower() == self.MEDIO_RECHAZO:
            return ResultadoPago(EstadoPago.RECHAZADO, f"SIM-{str(clave)[:8]}", "La entidad rechazó el pago (pago simulado).")
        return ResultadoPago(EstadoPago.APROBADO, f"SIM-{str(clave)[:8]}")

    def devolver(self, referencia: str, monto: Decimal) -> ResultadoPago:
        return ResultadoPago(EstadoPago.APROBADO, f"SIM-DEV-{(referencia or '').removeprefix('SIM-')[:8]}")

    def consultar(self, clave: UUID) -> ResultadoPago | None:
        return None  # el simulado no guarda estado fuera de la tabla pago


# Estados de un Refund -> EstadoPago
_ESTADOS_REEMBOLSO = {
    "succeeded": EstadoPago.APROBADO,
    "pending": EstadoPago.EN_VERIFICACION,
    "requires_action": EstadoPago.EN_VERIFICACION,
}

# Estados de un PaymentIntent -> EstadoPago
_ESTADOS_STRIPE = {
    "succeeded": EstadoPago.APROBADO,
    "processing": EstadoPago.EN_VERIFICACION,
    "requires_action": EstadoPago.EN_VERIFICACION,
    "requires_capture": EstadoPago.EN_VERIFICACION,
}


class AdaptadorStripe(PasarelaPagos):
    def __init__(self, llave: str):
        import stripe

        self._stripe = stripe
        cliente = stripe.StripeClient(llave)
        self._intents = getattr(cliente, "v1", cliente).payment_intents
        self._reembolsos = getattr(cliente, "v1", cliente).refunds

    def _resultado(self, intent) -> ResultadoPago:
        estado = _ESTADOS_STRIPE.get(intent.status, EstadoPago.RECHAZADO)
        error = getattr(intent, "last_payment_error", None)
        motivo = None if estado == EstadoPago.APROBADO else (getattr(error, "message", None) or f"Pago {intent.status}.")
        return ResultadoPago(estado, intent.id, motivo)

    def cobrar(self, monto: Decimal, clave: UUID, medio: str) -> ResultadoPago:
        try:
            intent = self._intents.create(
                params={
                    # COP es una moneda de dos decimales en Stripe: el monto va en centavos
                    "amount": int((monto * 100).to_integral_value()),
                    "currency": "cop",
                    "payment_method": medio,
                    "confirm": True,
                    "automatic_payment_methods": {"enabled": True, "allow_redirects": "never"},
                    "metadata": {"clave_idempotencia": str(clave)},
                },
                options={"idempotency_key": str(clave)},
            )
        except self._stripe.CardError as e:
            return ResultadoPago(EstadoPago.RECHAZADO, None, e.user_message or "La tarjeta fue rechazada.")
        return self._resultado(intent)

    def devolver(self, referencia: str, monto: Decimal) -> ResultadoPago:
        try:
            reembolso = self._reembolsos.create(
                params={"payment_intent": referencia, "amount": int((monto * 100).to_integral_value())},
                options={"idempotency_key": f"devolucion-{referencia}"},
            )
        except self._stripe.StripeError as e:
            return ResultadoPago(EstadoPago.RECHAZADO, None, getattr(e, "user_message", None) or "Stripe no aceptó la devolución.")
        estado = _ESTADOS_REEMBOLSO.get(reembolso.status, EstadoPago.RECHAZADO)
        return ResultadoPago(estado, reembolso.id, None if estado == EstadoPago.APROBADO else f"Devolución {reembolso.status}.")

    def consultar(self, clave: UUID) -> ResultadoPago | None:
        encontrados = self._intents.search(params={"query": f"metadata['clave_idempotencia']:'{clave}'"})
        return self._resultado(encontrados.data[0]) if encontrados.data else None


def obtener_pasarela() -> PasarelaPagos:
    llave = getattr(settings, "STRIPE_SECRET_KEY", "")
    return AdaptadorStripe(llave) if llave else AdaptadorSimulado()
