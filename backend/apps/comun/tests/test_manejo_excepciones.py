"""Manejo de excepciones: un dato malformado que manda el cliente nunca produce un 500, y una falla en una tarea
en lote no detiene las demás (queda en el log y en la auditoría como ErrorOperacion, RNF-O-OPE-01)."""

import uuid

import pytest
from django.apps import apps

from apps.auditoria import services as auditoria

pytestmark = pytest.mark.django_db
CUERPOS_MALOS = [[], "texto", {"correo": 123, "password": ["x"], "refresh": None, "motivo": {"a": 1}}]


@pytest.fixture(autouse=True)
def sin_limite_de_intentos(monkeypatch):
    """El límite de intentos (429) taparía la respuesta que se quiere revisar."""
    from rest_framework.views import APIView

    monkeypatch.setattr(APIView, "get_throttles", lambda self: [])


@pytest.mark.parametrize("cuerpo", CUERPOS_MALOS, ids=["lista", "texto", "tipos-equivocados"])
@pytest.mark.parametrize("ruta,esperado", [
    ("/api/v1/identidad/token", 401),
    ("/api/v1/identidad/token/renovar", 401),
    ("/api/v1/identidad/salir", 204),
    ("/api/v1/identidad/recuperacion", 202),
    ("/api/v1/identidad/recuperacion/token-que-no-existe", 404),
])
def test_cuerpo_malformado_no_produce_500(demo, cliente, ruta, esperado, cuerpo):
    r = cliente.post(ruta, cuerpo, format="json")
    assert r.status_code == esperado, r.content
    assert r.status_code == 204 or "detalle" in r.json()


@pytest.mark.parametrize("cuerpo", CUERPOS_MALOS, ids=["lista", "texto", "tipos-equivocados"])
def test_bloquear_con_cuerpo_malformado_pide_el_motivo(demo, entrar, cuerpo):
    pid = apps.get_model("catalogo", "Publicacion").objects.filter(estado="ACTIVA").values_list("id", flat=True).first()
    r = entrar("admin@inversioneslr.com", "Clave1234").post(f"/api/v1/admin/publicaciones/{pid}/bloqueo", cuerpo, format="json")
    assert r.status_code == 400 and r.json()["campo"] == "motivo"


def test_refresh_nulo_no_crea_un_token_vacio(demo, cliente):
    """RefreshToken(None) de SimpleJWT crea un token nuevo sin usuario; antes terminaba en KeyError (500)."""
    from apps.identidad import services

    with pytest.raises(services.ErrorNegocio):
        services.renovar_sesion(None)
    services.cerrar_sesion(None)  # no hay nada que cerrar: no falla


def test_un_error_de_la_api_responde_500_controlado_sin_detalles_internos(demo, cliente, monkeypatch):
    from apps.catalogo import services

    monkeypatch.setattr(services, "listar_catalogos", lambda: 1 / 0)
    r = cliente.get("/api/v1/catalogo/ciudades")
    assert r.status_code == 500 and r.json() == {"detalle": "Ocurrió un error inesperado. Intenta de nuevo."}
    falla = auditoria.consultar_eventos(accion="ErrorOperacion").get()
    assert falla.exitoso is False and falla.detalle["error"] == "ZeroDivisionError"


# ---------------- tareas en lote
def test_si_una_tarea_diaria_falla_las_demas_corren(alojamiento_740, reservar, reloj, monkeypatch):
    from apps.comun.tareas import ejecutar_tareas_diarias
    from apps.pagos import services as pagos

    reloj("2026-11-01")
    r = reservar(alojamiento_740, "2026-11-05", "2026-11-07")
    reloj("2026-11-08")

    def caida():
        raise ConnectionError("Stripe no respondió")

    monkeypatch.setattr(pagos, "conciliar_pagos", caida)
    resultado = ejecutar_tareas_diarias("prueba")
    assert resultado["reservas_completadas"] == 1 and resultado["pagos_conciliados"] is None
    assert resultado["errores"] == {"pagos_conciliados": "ConnectionError"}
    assert apps.get_model("reservas", "Reserva").objects.get(pk=r["id"]).estado == "COMPLETADA"
    assert auditoria.consultar_eventos(accion="TareasDiarias").get().exitoso is False
    assert auditoria.consultar_eventos(accion="ErrorOperacion").get().detalle["tarea"] == "pagos_conciliados"


def test_una_reserva_que_falla_no_detiene_las_demas(alojamiento_740, publicar, reservar, reloj, monkeypatch):
    from apps.reservas import services
    from apps.reservas.models import Reserva

    otra = publicar("Otra")
    reloj("2026-11-01")
    a = reservar(alojamiento_740, "2026-11-05", "2026-11-07")
    b = reservar(otra, "2026-11-05", "2026-11-07", desayuno=False)
    original = Reserva.completar_reserva

    def completar(self):
        if self.id == a["id"]:
            raise RuntimeError("falla en esta reserva")
        original(self)

    monkeypatch.setattr(Reserva, "completar_reserva", completar)
    reloj("2026-11-08")
    assert services.completar_reservas_vencidas() == 1
    assert Reserva.objects.get(pk=a["id"]).estado == "CONFIRMADA"  # se revirtió sola; se reintenta en la próxima
    assert Reserva.objects.get(pk=b["id"]).estado == "COMPLETADA"
    assert auditoria.consultar_eventos(accion="ErrorOperacion").get().entidad_id == a["id"]


def test_un_pago_que_no_se_puede_consultar_no_detiene_la_conciliacion(alojamiento_740, reservar, reloj, monkeypatch):
    from apps.pagos import services
    from apps.pagos.pasarela import AdaptadorSimulado, ResultadoPago

    reloj("2026-11-01")
    r = reservar(alojamiento_740, "2026-11-20", "2026-11-23")
    Pago = apps.get_model("pagos", "Pago")
    malo, bueno = (Pago.objects.create(cotizacion_id=r["cotizacion"], tipo="COBRO", monto=1000, estado="EN_VERIFICACION",
                                       clave_idempotencia=uuid.uuid4()) for _ in range(2))

    def consultar(self, clave):
        if clave == malo.clave_idempotencia:
            raise ConnectionError("timeout")
        return ResultadoPago("APROBADO", "pi_ok")

    monkeypatch.setattr(AdaptadorSimulado, "consultar", consultar)
    assert services.conciliar_pagos() == 1
    malo.refresh_from_db(); bueno.refresh_from_db()
    assert (malo.estado, bueno.estado) == ("EN_VERIFICACION", "APROBADO")
