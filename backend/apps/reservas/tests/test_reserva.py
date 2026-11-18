"""HU-13 Reservar y pagar (RF-D-RES-02.2): CA-13.1, CA-13.3, CA-13.4, RNF-P-FIA-02, RNF-P-FIA-03 y los
triggers de reserva y pago (RNF-E-CON-01). CA-13.2 (concurrencia) está en test_concurrencia.py."""

import uuid
from decimal import Decimal

import pytest
from django.apps import apps
from django.db import DatabaseError, connection, transaction

from apps.auditoria import services as auditoria

pytestmark = pytest.mark.django_db
RESERVAR = "/api/v1/reservas"

Reserva = lambda: apps.get_model("reservas", "Reserva")  # noqa: E731
Pago = lambda: apps.get_model("pagos", "Pago")  # noqa: E731


@pytest.fixture
def cotizacion(publicar, entrar, dias):
    """Cotización de 3 noches de un alojamiento de $200.000 con limpieza de $50.000 (total $710.000)."""
    pid = publicar("Para reservar", precio=200000, limpieza=50000)
    h = entrar("huesped@correo.com")
    r = h.post("/api/v1/reservas/cotizaciones", {"publicacion": pid, "fecha_llegada": dias(30).isoformat(),
                                                 "fecha_salida": dias(33).isoformat(), "num_huespedes": 2}, format="json")
    assert r.status_code == 201, r.content
    h.cot = r.json()
    h.pid = pid
    return h


def _reservar(h, clave=None, medio="tarjeta", cot=None):
    return h.post(RESERVAR, {"cotizacion": cot or h.cot["id"], "clave_idempotencia": str(clave or uuid.uuid4()),
                             "medio_pago": medio}, format="json")


def test_ca_13_1_reserva_confirmada_y_noches_ocupadas(cotizacion, cliente, dias):
    r = _reservar(cotizacion)
    assert r.status_code == 201, r.content
    reserva = r.json()
    assert reserva["estado"] == "CONFIRMADA" and reserva["total"] == "710000.00"
    assert reserva["pagos"][0]["estado"] == "APROBADO" and reserva["pagos"][0]["tipo"] == "COBRO"
    r_db = Reserva().objects.get(pk=reserva["id"])
    assert r_db.politica_id is not None and r_db.cotizacion_id == cotizacion.cot["id"]
    assert Pago().objects.get().reserva_id == r_db.id
    noches = cliente.get(f"/api/v1/busqueda/publicaciones/{cotizacion.pid}", {"desde": dias(29), "hasta": dias(35)}).json()
    assert noches["disponibilidad"]["noches_no_disponibles"] == [dias(30).isoformat(), dias(31).isoformat(), dias(32).isoformat()]
    assert auditoria.consultar(accion="ReservaConfirmada").filter(entidad_id=reserva["id"]).exists()
    assert auditoria.consultar(accion="PagoAprobado").exists()


def test_reserva_confirmada_publica_el_evento_de_dominio(cotizacion, django_capture_on_commit_callbacks):
    from apps.comun.eventos import evento_dominio

    recibidos = []
    receptor = lambda sender, nombre, **kw: recibidos.append((nombre, kw["entidad_id"]))  # noqa: E731
    evento_dominio.connect(receptor, weak=False)
    try:
        with django_capture_on_commit_callbacks(execute=True):
            rid = _reservar(cotizacion).json()["id"]
    finally:
        evento_dominio.disconnect(receptor)
    assert ("ReservaConfirmada", rid) in recibidos


def test_ca_13_3_pago_rechazado_no_crea_la_reserva(cotizacion):
    r = _reservar(cotizacion, medio="rechazar")
    assert r.status_code == 402 and r.json()["estado_pago"] == "RECHAZADO" and "rechaz" in r.json()["detalle"]
    assert not Reserva().objects.filter(cotizacion_id=cotizacion.cot["id"]).exists()
    assert not Pago().objects.exists()
    intento = auditoria.consultar(accion="ReservaRechazada").get()
    assert intento.exitoso is False and intento.actor_id == cotizacion.usuario["id"]
    assert _reservar(cotizacion).status_code == 201  # con otro medio sí reserva


def test_ca_13_4_doble_clic_crea_una_sola_reserva(cotizacion):
    clave = uuid.uuid4()
    primera, segunda = _reservar(cotizacion, clave), _reservar(cotizacion, clave)
    assert (primera.status_code, segunda.status_code) == (201, 200)
    assert primera.json()["id"] == segunda.json()["id"]
    assert Reserva().objects.filter(cotizacion_id=cotizacion.cot["id"]).count() == 1


def test_rnf_p_fia_02_veinte_envios_de_la_misma_solicitud(cotizacion):
    clave = uuid.uuid4()
    respuestas = [_reservar(cotizacion, clave) for _ in range(20)]
    assert [r.status_code for r in respuestas].count(201) == 1
    assert {r.json()["id"] for r in respuestas} == {respuestas[0].json()["id"]}
    assert Reserva().objects.count() == 4  # 3 de la demo + 1
    assert Pago().objects.count() == 1  # se cobró una sola vez


def test_rnf_p_fia_03_falla_a_la_mitad_no_deja_registros(cotizacion, monkeypatch):
    """La pasarela aprueba, pero falla algo después de guardar el pago: no queda reserva ni pago ni auditoría."""
    from apps.reservas import services

    def fallar(*a, **kw):
        raise RuntimeError("Falla después del pago")

    monkeypatch.setattr(services, "publicar", fallar)
    with pytest.raises(RuntimeError):
        services.reservar(apps.get_model("identidad", "Usuario").objects.get(pk=cotizacion.usuario["id"]),
                          cotizacion.cot["id"], uuid.uuid4(), "tarjeta")
    assert not Reserva().objects.filter(cotizacion_id=cotizacion.cot["id"]).exists()
    assert not Pago().objects.exists()
    assert not auditoria.consultar(accion="ReservaConfirmada").exists()
    assert not auditoria.consultar(accion="PagoAprobado").exists()


def test_rnf_p_fia_03_falla_de_la_pasarela_no_deja_registros(cotizacion, monkeypatch):
    from apps.pagos.pasarela import AdaptadorSimulado

    def caida(self, monto, clave, medio):
        raise ConnectionError("La pasarela no respondió")

    monkeypatch.setattr(AdaptadorSimulado, "cobrar", caida)
    r = _reservar(cotizacion)
    assert r.status_code == 500
    assert not Reserva().objects.filter(cotizacion_id=cotizacion.cot["id"]).exists() and not Pago().objects.exists()
    assert auditoria.consultar(accion="ErrorOperacion", exitoso=False).exists()


def test_cotizacion_cambiada_responde_409_con_la_nueva(cotizacion, entrar):
    apps.get_model("catalogo", "Publicacion").objects.filter(pk=cotizacion.pid).update(precio_noche=Decimal("210000"))
    r = _reservar(cotizacion)
    assert r.status_code == 409 and "precio cambió" in r.json()["detalle"]
    nueva = r.json()["cotizacion"]
    assert nueva["id"] != cotizacion.cot["id"] and nueva["total"] == "743000.00"  # 630.000 + 50.000 + 63.000
    assert not Reserva().objects.filter(cotizacion_id=cotizacion.cot["id"]).exists()
    assert _reservar(cotizacion, cot=nueva["id"]).status_code == 201


def test_fechas_ocupadas_al_reservar_responde_409(cotizacion, entrar, dias):
    entrar("anfitrion@correo.com").post(f"/api/v1/catalogo/publicaciones/{cotizacion.pid}/calendario",
                                        {"fecha_inicio": dias(31).isoformat(), "fecha_fin": dias(32).isoformat(), "tipo": "NO_DISPONIBLE"}, format="json")
    r = _reservar(cotizacion)
    assert r.status_code == 409 and r.json()["detalle"] == "Las fechas ya no están disponibles."
    assert not Pago().objects.exists()


def test_la_misma_cotizacion_no_se_reserva_dos_veces_con_otra_clave(cotizacion):
    assert _reservar(cotizacion).status_code == 201
    assert _reservar(cotizacion).status_code == 409


def test_visitante_no_reserva(cotizacion, cliente):
    assert cliente.post(RESERVAR, {"cotizacion": cotizacion.cot["id"], "clave_idempotencia": str(uuid.uuid4()),
                                   "medio_pago": "tarjeta"}, format="json").status_code == 401


# ---------------- Triggers (RNF-E-CON-01)
def _sql_falla(sql, params=(), coincide="reserva: |pago: "):
    with connection.cursor() as c:
        c.execute("SET CONSTRAINTS ALL IMMEDIATE")  # resuelve las FK diferidas pendientes de la prueba
    with pytest.raises(DatabaseError, match=coincide), transaction.atomic(), connection.cursor() as c:
        c.execute(sql, params)


def _sql_ok(sql, params=()):
    with transaction.atomic(), connection.cursor() as c:
        c.execute(sql, params)


@pytest.mark.parametrize("origen,destino", [
    ("CANCELADA", "CONFIRMADA"), ("COMPLETADA", "CONFIRMADA"), ("COMPLETADA", "CANCELADA"),
    ("CANCELADA", "EN_REVISION"), ("EN_REVISION", "COMPLETADA"),
])
def test_transiciones_prohibidas_de_reserva(cotizacion, origen, destino):
    rid = _reservar(cotizacion).json()["id"]
    camino = {"CANCELADA": ["CANCELADA"], "COMPLETADA": ["COMPLETADA"], "EN_REVISION": ["EN_REVISION"]}[origen]
    for estado in camino:
        _sql_ok("UPDATE reserva SET estado = %s WHERE id = %s", [estado, rid])
    _sql_falla("UPDATE reserva SET estado = %s WHERE id = %s", [destino, rid])


@pytest.mark.parametrize("camino", [
    ["CANCELADA"], ["COMPLETADA"], ["EN_REVISION", "CONFIRMADA"], ["EN_REVISION", "CANCELADA"],
])
def test_transiciones_permitidas_de_reserva(cotizacion, camino):
    rid = _reservar(cotizacion).json()["id"]
    for estado in camino:
        _sql_ok("UPDATE reserva SET estado = %s WHERE id = %s", [estado, rid])
    assert Reserva().objects.get(pk=rid).estado == camino[-1]


@pytest.mark.parametrize("sql", [
    "UPDATE reserva SET total = total + 1",
    "UPDATE reserva SET fecha_salida = fecha_salida + 1",
    "DELETE FROM reserva",
    "TRUNCATE reserva CASCADE",
])
def test_reserva_no_se_modifica_ni_se_borra(cotizacion, sql):
    _reservar(cotizacion)
    _sql_falla(sql)


def test_pago_solo_cambia_estado_y_referencia(cotizacion):
    _reservar(cotizacion)
    _sql_ok("UPDATE pago SET estado = 'EN_VERIFICACION', referencia_externa = 'pi_123'")
    for sql in ("UPDATE pago SET monto = monto + 1", "UPDATE pago SET reserva_id = NULL", "DELETE FROM pago", "TRUNCATE pago CASCADE"):
        _sql_falla(sql)
