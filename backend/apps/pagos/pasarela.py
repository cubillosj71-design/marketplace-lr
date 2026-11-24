"""Pasarela de pagos de MOD-05: interfaz PasarelaPagos y sus dos adaptadores (ADR-006).

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
    """Interfaz de la pasarela de pagos (patrón Adaptador, ADR-006, MOD-05).

    ServicioPagos solo conoce esta interfaz; obtener_pasarela() elige el adaptador según la configuración.
    Para cambiar de proveedor basta con escribir otro adaptador.
    """
    @abstractmethod
    def cobrar_pago(self, monto: Decimal, clave: UUID, medio: str) -> ResultadoPago:
        """Cobra el total de una reserva.

        Args:
            monto: valor en pesos colombianos.
            clave: llave de idempotencia; un reintento con la misma clave no vuelve a cobrar.
            medio: medio de pago (en Stripe, el payment_method pm_... que tokeniza el frontend).

        Returns:
            El estado del cobro (APROBADO, RECHAZADO o EN_VERIFICACION), su referencia y, si no se
            aprobó, el motivo para mostrar al huésped.
        """

    @abstractmethod
    def devolver_pago(self, referencia: str, monto: Decimal) -> ResultadoPago:
        """Devuelve parte o todo un cobro aprobado (cancelación, RF-D-RES-03.1).

        Args:
            referencia: referencia del cobro en la pasarela (pi_... o SIM-...).
            monto: valor a devolver en pesos colombianos.

        Returns:
            El estado de la devolución y su referencia.
        """

    @abstractmethod
    def consultar_pago(self, clave: UUID) -> ResultadoPago | None:
        """Consulta el estado actual de un cobro (conciliación diaria de pagos EN_VERIFICACION).

        Args:
            clave: llave de idempotencia con la que se cobró.

        Returns:
            El estado en la pasarela, o None si la pasarela no lo conoce.
        """


class AdaptadorSimulado(PasarelaPagos):
    """Pasarela simulada para desarrollo, pruebas y la demo (sin llave de Stripe).

    Aprueba todos los cobros salvo que el medio de pago sea "rechazar" (para probar CA-13.3). Las
    referencias empiezan por SIM- (cobros) y SIM-DEV- (devoluciones).
    """
    MEDIO_RECHAZO = "rechazar"

    def cobrar_pago(self, monto: Decimal, clave: UUID, medio: str) -> ResultadoPago:
        """Aprueba el cobro, o lo rechaza si el medio es "rechazar". Ver PasarelaPagos.cobrar_pago."""
        if (medio or "").strip().lower() == self.MEDIO_RECHAZO:
            return ResultadoPago(EstadoPago.RECHAZADO, f"SIM-{str(clave)[:8]}", "La entidad rechazó el pago (pago simulado).")
        return ResultadoPago(EstadoPago.APROBADO, f"SIM-{str(clave)[:8]}")

    def devolver_pago(self, referencia: str, monto: Decimal) -> ResultadoPago:
        """Aprueba la devolución con una referencia SIM-DEV-. Ver PasarelaPagos.devolver_pago."""
        return ResultadoPago(EstadoPago.APROBADO, f"SIM-DEV-{(referencia or '').removeprefix('SIM-')[:8]}")

    def consultar_pago(self, clave: UUID) -> ResultadoPago | None:
        """El simulado no guarda pagos fuera de la tabla pago: siempre devuelve None (nada que conciliar)."""
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
    """Pasarela real de Stripe en modo prueba (ADR-006): PaymentIntent para cobrar y Refund para devolver.

    Args:
        llave: llave secreta de Stripe (sk_test_...). Solo llega por variables de entorno.
    """
    def __init__(self, llave: str):
        import stripe

        self._stripe = stripe
        cliente = stripe.StripeClient(llave)
        self._intents = getattr(cliente, "v1", cliente).payment_intents
        self._reembolsos = getattr(cliente, "v1", cliente).refunds

    def _convertir_resultado(self, intent) -> ResultadoPago:
        """Traduce un PaymentIntent de Stripe al ResultadoPago de la aplicación.

        succeeded es APROBADO; processing, requires_action y requires_capture son EN_VERIFICACION; el
        resto es RECHAZADO, con el mensaje de error de Stripe como motivo.
        """
        estado = _ESTADOS_STRIPE.get(intent.status, EstadoPago.RECHAZADO)
        error = getattr(intent, "last_payment_error", None)
        motivo = None if estado == EstadoPago.APROBADO else (getattr(error, "message", None) or f"Pago {intent.status}.")
        return ResultadoPago(estado, intent.id, motivo)

    def cobrar_pago(self, monto: Decimal, clave: UUID, medio: str) -> ResultadoPago:
        """Crea y confirma un PaymentIntent en pesos colombianos con la llave de idempotencia `clave`.

        Un reintento con la misma clave no vuelve a cobrar. Una tarjeta rechazada (CardError) devuelve
        RECHAZADO con el mensaje de Stripe. Ver PasarelaPagos.cobrar_pago.
        """
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
        return self._convertir_resultado(intent)

    def devolver_pago(self, referencia: str, monto: Decimal) -> ResultadoPago:
        """Crea un reembolso sobre el PaymentIntent del cobro, con la llave de idempotencia devolucion-<referencia>.

        Una reserva se cancela una sola vez, así que un cobro tiene a lo sumo una devolución. Si Stripe
        rechaza la solicitud, devuelve RECHAZADO con el motivo. Ver PasarelaPagos.devolver_pago.
        """
        try:
            reembolso = self._reembolsos.create(
                params={"payment_intent": referencia, "amount": int((monto * 100).to_integral_value())},
                options={"idempotency_key": f"devolucion-{referencia}"},
            )
        except self._stripe.StripeError as e:
            return ResultadoPago(EstadoPago.RECHAZADO, None, getattr(e, "user_message", None) or "Stripe no aceptó la devolución.")
        estado = _ESTADOS_REEMBOLSO.get(reembolso.status, EstadoPago.RECHAZADO)
        return ResultadoPago(estado, reembolso.id, None if estado == EstadoPago.APROBADO else f"Devolución {reembolso.status}.")

    def consultar_pago(self, clave: UUID) -> ResultadoPago | None:
        """Busca en Stripe el PaymentIntent con esa clave de idempotencia (metadata) y devuelve su estado actual."""
        encontrados = self._intents.search(params={"query": f"metadata['clave_idempotencia']:'{clave}'"})
        return self._convertir_resultado(encontrados.data[0]) if encontrados.data else None


def obtener_pasarela() -> PasarelaPagos:
    """Elige la pasarela según la configuración (ADR-006).

    Returns:
        AdaptadorStripe si existe STRIPE_SECRET_KEY; si no, AdaptadorSimulado.
    """
    llave = getattr(settings, "STRIPE_SECRET_KEY", "")
    return AdaptadorStripe(llave) if llave else AdaptadorSimulado()
