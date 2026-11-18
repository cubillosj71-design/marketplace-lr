"""HU-14 y HU-26 (consultar reservas, RF-D-RES-02.3) y HU-15 (cancelar, RF-D-RES-03.1).

Las fechas se fijan con el reloj inyectable para reproducir los ejemplos del SRS: una reserva de $740.000 con
llegada el 20 de noviembre."""

from decimal import Decimal

import pytest
from django.apps import apps
from django.db import DatabaseError, connection, transaction

from apps.auditoria import services as auditoria

pytestmark = pytest.mark.django_db
NUEVO = {"nombre_completo": "Ana Torres", "correo": "ana@correo.com", "telefono": "300 000 0000",
         "password": "Segura2026", "rol": "HUESPED", "acepta_datos": True}

Reserva = lambda: apps.get_model("reservas", "Reserva")  # noqa: E731
Pago = lambda: apps.get_model("pagos", "Pago")  # noqa: E731
Cancelacion = lambda: apps.get_model("reservas", "Cancelacion")  # noqa: E731


@pytest.fixture
def reserva_740(alojamiento_740, reservar, reloj):
    """Reserva CONFIRMADA de $740.000 del 20 al 23 de noviembre de 2026, hecha el 1 de noviembre."""
    reloj("2026-11-01")
    r = reservar(alojamiento_740, "2026-11-20", "2026-11-23")
    assert r["total"] == "740000.00"
    return r


def _cancelar(entrar, rid, motivo="Cambio de planes", correo="huesped@correo.com", clave="Clave1234"):
    return entrar(correo, clave).post(f"/api/v1/reservas/{rid}/cancelar", {"motivo": motivo}, format="json")


def _noches(pid):
    return list(apps.get_model("reservas", "NocheNoDisponible").objects.filter(publicacion_id=pid).values_list("fecha", flat=True))


# ---------------- HU-15 Cancelar
def test_ca_15_1_cancelar_5_dias_antes_devuelve_el_50(reserva_740, entrar, reloj):
    reloj("2026-11-15")
    r = _cancelar(entrar, reserva_740["id"])
    assert r.status_code == 200, r.content
    c = r.json()["cancelacion"]
    assert r.json()["estado"] == "CANCELADA"
    assert (c["dias_anticipacion"], c["porcentaje_devolucion"], c["valor_devolucion"]) == (5, "50.00", "370000.00")
    devolucion = Pago().objects.get(reserva_id=reserva_740["id"], tipo="DEVOLUCION")
    assert devolucion.monto == Decimal("370000") and devolucion.estado == "APROBADO"
    assert _noches(reserva_740["publicacion"]) == []  # las noches quedan disponibles


def test_ca_15_2_diez_dias_antes_devuelve_el_100(reserva_740, entrar, reloj):
    reloj("2026-11-10")
    c = _cancelar(entrar, reserva_740["id"]).json()["cancelacion"]
    assert (c["dias_anticipacion"], c["porcentaje_devolucion"], c["valor_devolucion"]) == (10, "100.00", "740000.00")


def test_ca_15_4_el_dia_anterior_devuelve_0_sin_pago(reserva_740, entrar, reloj):
    reloj("2026-11-19T23:30")  # hora de Colombia: sigue siendo el 19
    r = _cancelar(entrar, reserva_740["id"])
    assert r.json()["estado"] == "CANCELADA" and r.json()["cancelacion"]["valor_devolucion"] == "0.00"
    assert not Pago().objects.filter(reserva_id=reserva_740["id"], tipo="DEVOLUCION").exists()  # monto > 0
    assert _noches(reserva_740["publicacion"]) == []


@pytest.mark.parametrize("dia", ["2026-11-20T00:05", "2026-11-21"])
def test_ca_15_5_desde_el_dia_de_llegada_no_se_cancela(reserva_740, entrar, reloj, dia):
    reloj(dia)
    r = _cancelar(entrar, reserva_740["id"])
    assert r.status_code == 409 and "llegada" in r.json()["detalle"]
    assert Reserva().objects.get(pk=reserva_740["id"]).estado == "CONFIRMADA"
    assert not Cancelacion().objects.exists()


def test_ca_15_3_el_registro_muestra_quien_cuando_motivo_y_valor(reserva_740, entrar, reloj):
    reloj("2026-11-15")
    _cancelar(entrar, reserva_740["id"], motivo="Me enfermé")
    huesped = apps.get_model("identidad", "Usuario").objects.get(correo="huesped@correo.com")
    filas = entrar("admin@inversioneslr.com").get("/api/v1/admin/auditoria", {"accion": "ReservaCancelada"}).json()["results"]
    fila = next(f for f in filas if f["entidad_id"] == reserva_740["id"])
    assert fila["actor_id"] == huesped.id and fila["fecha"]
    assert fila["detalle"]["motivo"] == "Me enfermé" and fila["detalle"]["valor_devolucion"] == "370000.00"


def test_el_porcentaje_sale_de_la_politica_guardada_en_la_reserva(reserva_740, entrar, reloj):
    Politica = apps.get_model("catalogo", "PoliticaCancelacion")
    estricta = Politica.objects.create(nombre="Estricta")
    apps.get_model("catalogo", "TramoPolitica").objects.create(politica=estricta, dias_minimos=0, porcentaje_devolucion=0)
    apps.get_model("catalogo", "Publicacion").objects.filter(pk=reserva_740["publicacion"]).update(politica=estricta)
    reloj("2026-11-10")
    assert _cancelar(entrar, reserva_740["id"]).json()["cancelacion"]["porcentaje_devolucion"] == "100.00"  # Moderada


def test_simular_muestra_la_devolucion_antes_de_confirmar(reserva_740, entrar, reloj):
    reloj("2026-11-15")
    s = entrar("huesped@correo.com").get(f"/api/v1/reservas/{reserva_740['id']}/cancelar").json()
    assert s == {"reserva": reserva_740["id"], "cancelable": True, "dias_anticipacion": 5,
                 "porcentaje_devolucion": "50.00", "valor_devolucion": "370000.00"}
    assert Reserva().objects.get(pk=reserva_740["id"]).estado == "CONFIRMADA"


def test_motivo_obligatorio_y_solo_el_huesped_dueno(reserva_740, entrar, cliente, reloj):
    reloj("2026-11-15")
    r = _cancelar(entrar, reserva_740["id"], motivo="  ")
    assert r.status_code == 400 and r.json()["campo"] == "motivo"
    cliente.post("/api/v1/identidad/registro", NUEVO, format="json")
    assert _cancelar(entrar, reserva_740["id"], correo="ana@correo.com", clave="Segura2026").status_code == 403
    assert auditoria.consultar(accion="AccesoDenegado", exitoso=False).filter(entidad="Reserva").exists()


def test_cancelar_dos_veces_responde_409(reserva_740, entrar, reloj):
    reloj("2026-11-15")
    assert _cancelar(entrar, reserva_740["id"]).status_code == 200
    assert _cancelar(entrar, reserva_740["id"]).status_code == 409


@pytest.mark.parametrize("sql", ["UPDATE cancelacion SET motivo = 'x'", "DELETE FROM cancelacion", "TRUNCATE cancelacion"])
def test_cancelacion_es_de_solo_insercion(reserva_740, entrar, reloj, sql):
    reloj("2026-11-15")
    _cancelar(entrar, reserva_740["id"])
    with connection.cursor() as c:
        c.execute("SET CONSTRAINTS ALL IMMEDIATE")
    with pytest.raises(DatabaseError, match="solo inserción"), transaction.atomic(), connection.cursor() as c:
        c.execute(sql)


# ---------------- HU-14 Mis reservas
def test_ca_14_1_ve_confirmada_y_cancelada_con_su_estado(alojamiento_740, reservar, entrar, cliente, reloj):
    cliente.post("/api/v1/identidad/registro", NUEVO, format="json")
    reloj("2026-11-01")
    a = reservar(alojamiento_740, "2026-11-20", "2026-11-23", correo="ana@correo.com", clave="Segura2026")
    b = reservar(alojamiento_740, "2026-12-01", "2026-12-03", correo="ana@correo.com", clave="Segura2026")
    entrar("ana@correo.com", "Segura2026").post(f"/api/v1/reservas/{b['id']}/cancelar", {"motivo": "Ya no viajo"}, format="json")
    lista = entrar("ana@correo.com", "Segura2026").get("/api/v1/reservas/mias").json()
    estados = {r["id"]: r["estado"] for r in lista}
    assert estados == {a["id"]: "CONFIRMADA", b["id"]: "CANCELADA"}
    cancelada = next(r for r in lista if r["id"] == b["id"])
    assert cancelada["alojamiento"] == "Ejemplo 740" and cancelada["cancelacion"]["motivo"] == "Ya no viajo"
    assert cancelada["cancelacion"]["fecha"] and cancelada["cancelacion"]["valor_devolucion"]
    confirmada = next(r for r in lista if r["id"] == a["id"])
    assert (confirmada["num_huespedes"], confirmada["total"], confirmada["cancelable"]) == (2, "740000.00", True)


def test_ca_14_2_confirmada_con_salida_ayer_aparece_completada(alojamiento_740, reservar, entrar, reloj):
    reloj("2026-11-01")
    r = reservar(alojamiento_740, "2026-11-05", "2026-11-07")
    reloj("2026-11-08")  # la salida fue ayer
    lista = entrar("huesped@correo.com").get("/api/v1/reservas/mias").json()
    assert next(x for x in lista if x["id"] == r["id"])["estado"] == "COMPLETADA"
    assert Reserva().objects.get(pk=r["id"]).estado == "COMPLETADA"


def test_el_dia_de_salida_todavia_no_es_completada(alojamiento_740, reservar, entrar, reloj):
    reloj("2026-11-01")
    r = reservar(alojamiento_740, "2026-11-05", "2026-11-07")
    reloj("2026-11-07")
    assert entrar("huesped@correo.com").get(f"/api/v1/reservas/{r['id']}").json()["estado"] == "CONFIRMADA"


def test_ca_14_3_solo_ve_las_suyas(alojamiento_740, reservar, entrar, cliente, reloj):
    cliente.post("/api/v1/identidad/registro", NUEVO, format="json")
    reloj("2026-11-01")
    propia = reservar(alojamiento_740, "2026-11-20", "2026-11-23", correo="ana@correo.com", clave="Segura2026")
    reservar(alojamiento_740, "2026-12-01", "2026-12-03")  # de otro huésped
    lista = entrar("ana@correo.com", "Segura2026").get("/api/v1/reservas/mias").json()
    assert [r["id"] for r in lista] == [propia["id"]]


# ---------------- HU-26 Reservas de mis alojamientos
def test_ca_26_1_el_anfitrion_ve_solo_las_de_sus_alojamientos(alojamiento_740, publicar, reservar, entrar, reloj):
    otra = publicar("Segunda de Laura")
    de_sofia = publicar("De Sofía", anfitrion="sofia@correo.com")
    reloj("2026-11-01")
    r1 = reservar(alojamiento_740, "2026-11-20", "2026-11-23")
    r2 = reservar(otra, "2026-11-20", "2026-11-23", desayuno=False)
    ajena = reservar(de_sofia, "2026-11-20", "2026-11-23", desayuno=False)
    laura = entrar("anfitrion@correo.com")
    ids = {r["id"] for r in laura.get("/api/v1/reservas/de-mis-alojamientos").json()}
    assert {r1["id"], r2["id"]} <= ids and ajena["id"] not in ids
    assert all(r["anfitrion"] == laura.usuario["id"] for r in laura.get("/api/v1/reservas/de-mis-alojamientos").json())


def test_ca_26_2_ve_la_cancelada(reserva_740, entrar, reloj):
    reloj("2026-11-15")
    _cancelar(entrar, reserva_740["id"])
    lista = entrar("anfitrion@correo.com").get("/api/v1/reservas/de-mis-alojamientos").json()
    assert next(r for r in lista if r["id"] == reserva_740["id"])["estado"] == "CANCELADA"


def test_detalle_solo_para_huesped_anfitrion_y_administrador(reserva_740, entrar):
    url = f"/api/v1/reservas/{reserva_740['id']}"
    for correo in ("huesped@correo.com", "anfitrion@correo.com", "admin@inversioneslr.com"):
        assert entrar(correo).get(url).status_code == 200
    assert entrar("sofia@correo.com").get(url).status_code == 403


def test_el_huesped_no_lista_las_de_anfitrion_ni_al_reves(demo, entrar):
    assert entrar("huesped@correo.com").get("/api/v1/reservas/de-mis-alojamientos").status_code == 403
    assert entrar("anfitrion@correo.com").get("/api/v1/reservas/mias").status_code == 403
