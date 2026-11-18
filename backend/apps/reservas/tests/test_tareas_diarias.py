"""Tareas programadas (C4 nivel 3, rutas /interno): POST /api/v1/interno/tareas/diarias con X-Token-Tareas y el
comando tareas_diarias. Completa reservas vencidas, cancela las EN_REVISION sin resolver y concilia pagos."""

import io
import uuid

import pytest
from django.apps import apps
from django.core.management import call_command

from apps.auditoria import services as auditoria

pytestmark = pytest.mark.django_db
RUTA = "/api/v1/interno/tareas/diarias"
TOKEN = "token-de-prueba-largo-y-aleatorio"


@pytest.fixture
def con_token(settings):
    settings.TOKEN_TAREAS = TOKEN


@pytest.mark.parametrize("encabezados", [{}, {"HTTP_X_TOKEN_TAREAS": "otro"}])
def test_sin_token_o_con_token_incorrecto_responde_403_y_queda_registrado(con_token, cliente, encabezados):
    r = cliente.post(RUTA, **encabezados)
    assert r.status_code == 403
    intento = auditoria.consultar(accion="AccesoDenegado").get()
    assert intento.exitoso is False and intento.detalle["ruta"] == RUTA


def test_sin_token_configurado_nadie_entra(settings, cliente):
    settings.TOKEN_TAREAS = ""
    assert cliente.post(RUTA, HTTP_X_TOKEN_TAREAS="").status_code == 403


def test_con_token_completa_y_cancela_en_orden(con_token, cliente, alojamiento_740, publicar, reservar, entrar, reloj):
    otra = publicar("Para bloquear")
    reloj("2026-11-01")
    vencida = reservar(alojamiento_740, "2026-11-05", "2026-11-07")
    en_revision = reservar(otra, "2026-11-20", "2026-11-23", desayuno=False)
    entrar("admin@inversioneslr.com").post(f"/api/v1/admin/publicaciones/{otra}/bloqueo", {"motivo": "Fraude"}, format="json")
    reloj("2026-11-20")
    r = cliente.post(RUTA, HTTP_X_TOKEN_TAREAS=TOKEN)
    assert r.status_code == 200
    assert r.json() == {"reservas_completadas": 1, "reservas_canceladas_sin_resolucion": 1, "pagos_conciliados": 0}
    Reserva = apps.get_model("reservas", "Reserva")
    assert Reserva.objects.get(pk=vencida["id"]).estado == "COMPLETADA"
    assert Reserva.objects.get(pk=en_revision["id"]).estado == "CANCELADA"
    assert auditoria.consultar(accion="TareasDiarias").get().detalle["origen"] == "interno"


def test_concilia_los_pagos_en_verificacion(con_token, cliente, alojamiento_740, reservar, reloj, monkeypatch):
    from apps.pagos.pasarela import AdaptadorSimulado, ResultadoPago

    reloj("2026-11-01")
    r = reservar(alojamiento_740, "2026-11-20", "2026-11-23")
    Pago = apps.get_model("pagos", "Pago")
    pendiente = Pago.objects.create(cotizacion_id=r["cotizacion"], tipo="COBRO", monto=1000, estado="EN_VERIFICACION",
                                    clave_idempotencia=uuid.uuid4())
    monkeypatch.setattr(AdaptadorSimulado, "consultar", lambda self, clave: ResultadoPago("APROBADO", "pi_confirmado"))
    assert cliente.post(RUTA, HTTP_X_TOKEN_TAREAS=TOKEN).json()["pagos_conciliados"] == 1
    pendiente.refresh_from_db()
    assert (pendiente.estado, pendiente.referencia_externa) == ("APROBADO", "pi_confirmado")


def test_el_comando_hace_lo_mismo(alojamiento_740, reservar, reloj):
    reloj("2026-11-01")
    r = reservar(alojamiento_740, "2026-11-05", "2026-11-07")
    reloj("2026-11-08")
    salida = io.StringIO()
    call_command("tareas_diarias", stdout=salida)
    assert "Reservas completadas: 1" in salida.getvalue()
    assert apps.get_model("reservas", "Reserva").objects.get(pk=r["id"]).estado == "COMPLETADA"
    assert auditoria.consultar(accion="TareasDiarias").get().detalle["origen"] == "comando"


def test_salud_sigue_publica(cliente):
    assert cliente.get("/api/v1/salud").json() == {"estado": "ok"}
