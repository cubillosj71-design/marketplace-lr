"""MOD-05 Pagos: elección del adaptador y traducción de los estados de Stripe, sin red ni llaves reales."""

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.pagos.pasarela import AdaptadorSimulado, AdaptadorStripe, obtener_pasarela


def test_sin_llave_se_usa_el_simulado(settings):
    settings.STRIPE_SECRET_KEY = ""
    assert isinstance(obtener_pasarela(), AdaptadorSimulado)


def test_con_llave_se_usa_stripe(settings):
    settings.STRIPE_SECRET_KEY = "llave-falsa-solo-para-pruebas"
    assert isinstance(obtener_pasarela(), AdaptadorStripe)


def test_el_simulado_aprueba_salvo_rechazar():
    clave = uuid.uuid4()
    assert AdaptadorSimulado().cobrar(Decimal("710000"), clave, "tarjeta").estado == "APROBADO"
    rechazo = AdaptadorSimulado().cobrar(Decimal("710000"), clave, "rechazar")
    assert rechazo.estado == "RECHAZADO" and rechazo.motivo


class IntentsFalsos:
    def __init__(self, estado="succeeded", error=None):
        self.estado, self.error, self.llamadas = estado, error, []

    def create(self, params, options):
        self.llamadas.append((params, options))
        if self.error:
            raise self.error
        return SimpleNamespace(id="pi_prueba", status=self.estado, last_payment_error=None)


def _stripe(intents):
    a = AdaptadorStripe("llave-falsa-solo-para-pruebas")
    a._intents = intents
    return a


def test_stripe_crea_y_confirma_el_payment_intent_con_la_clave_de_idempotencia():
    intents = IntentsFalsos()
    clave = uuid.uuid4()
    r = _stripe(intents).cobrar(Decimal("740000.00"), clave, "pm_card_visa")
    params, options = intents.llamadas[0]
    assert r.estado == "APROBADO" and r.referencia == "pi_prueba"
    assert params["amount"] == 74000000 and params["currency"] == "cop" and params["confirm"] is True
    assert params["payment_method"] == "pm_card_visa" and options == {"idempotency_key": str(clave)}


@pytest.mark.parametrize("estado,esperado", [("processing", "EN_VERIFICACION"), ("requires_action", "EN_VERIFICACION"),
                                            ("requires_payment_method", "RECHAZADO"), ("canceled", "RECHAZADO")])
def test_estados_de_stripe(estado, esperado):
    assert _stripe(IntentsFalsos(estado)).cobrar(Decimal("1000"), uuid.uuid4(), "pm_x").estado == esperado


def test_tarjeta_rechazada_por_stripe():
    import stripe

    error = stripe.CardError("Your card was declined.", None, "card_declined")
    r = _stripe(IntentsFalsos(error=error)).cobrar(Decimal("1000"), uuid.uuid4(), "pm_card_chargeDeclined")
    assert r.estado == "RECHAZADO" and r.motivo


# ---------------- devolver(referencia, monto) del diagrama (RF-D-RES-03.1)
class ReembolsosFalsos:
    def __init__(self, estado="succeeded", error=None):
        self.estado, self.error, self.llamadas = estado, error, []

    def create(self, params, options):
        self.llamadas.append((params, options))
        if self.error:
            raise self.error
        return SimpleNamespace(id="re_prueba", status=self.estado)


def _stripe_reembolsos(reembolsos):
    a = AdaptadorStripe("llave-falsa-solo-para-pruebas")
    a._reembolsos = reembolsos
    return a


def test_el_simulado_aprueba_la_devolucion():
    r = AdaptadorSimulado().devolver("SIM-1a2b3c4d", Decimal("370000"))
    assert r.estado == "APROBADO" and r.referencia == "SIM-DEV-1a2b3c4d"


def test_stripe_devuelve_sobre_el_payment_intent_con_clave_de_idempotencia():
    reembolsos = ReembolsosFalsos()
    r = _stripe_reembolsos(reembolsos).devolver("pi_prueba", Decimal("370000.00"))
    params, options = reembolsos.llamadas[0]
    assert r.estado == "APROBADO" and r.referencia == "re_prueba"
    assert params == {"payment_intent": "pi_prueba", "amount": 37000000}
    assert options == {"idempotency_key": "devolucion-pi_prueba"}  # un reintento no devuelve dos veces


@pytest.mark.parametrize("estado,esperado", [("pending", "EN_VERIFICACION"), ("failed", "RECHAZADO"), ("canceled", "RECHAZADO")])
def test_estados_de_la_devolucion_en_stripe(estado, esperado):
    assert _stripe_reembolsos(ReembolsosFalsos(estado)).devolver("pi_x", Decimal("1000")).estado == esperado


def test_stripe_rechaza_la_devolucion():
    import stripe

    r = _stripe_reembolsos(ReembolsosFalsos(error=stripe.InvalidRequestError("No such payment_intent", "payment_intent"))).devolver(
        "pi_inexistente", Decimal("1000"))
    assert r.estado == "RECHAZADO" and r.motivo
