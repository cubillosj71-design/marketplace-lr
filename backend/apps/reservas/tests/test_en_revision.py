"""HU-20 Reservas EN_REVISION (RF-D-ADM-01.2): CA-20.1 a CA-20.5, y que restringir una cuenta no cambia sus
reservas (RF-D-ADM-02.1)."""

from decimal import Decimal

import pytest
from django.apps import apps

from apps.reservas import services

pytestmark = pytest.mark.django_db

Reserva = lambda: apps.get_model("reservas", "Reserva")  # noqa: E731
Cancelacion = lambda: apps.get_model("reservas", "Cancelacion")  # noqa: E731


@pytest.fixture
def reserva_740(alojamiento_740, reservar, reloj):
    reloj("2026-11-01")
    return reservar(alojamiento_740, "2026-11-20", "2026-11-23")


def _bloquear(entrar, pid, motivo="Dirección falsa"):
    return entrar("admin@inversioneslr.com").post(f"/api/v1/admin/publicaciones/{pid}/bloqueo", {"motivo": motivo}, format="json")


def _resolver(entrar, rid, **datos):
    return entrar("admin@inversioneslr.com").post(f"/api/v1/admin/reservas/{rid}/resolver", datos, format="json")


def test_ca_20_1_bloquear_pasa_la_reserva_a_en_revision_en_la_misma_transaccion(reserva_740, entrar, cliente):
    # Sin ejecutar los callbacks de on_commit: si la reserva ya está EN_REVISION, se hizo dentro de la transacción
    assert _bloquear(entrar, reserva_740["publicacion"]).json()["estado"] == "BLOQUEADA"
    assert Reserva().objects.get(pk=reserva_740["id"]).estado == "EN_REVISION"
    assert reserva_740["publicacion"] not in [p["id"] for p in cliente.get("/api/v1/busqueda/publicaciones").json()]
    en_revision = entrar("admin@inversioneslr.com").get("/api/v1/admin/reservas", {"estado": "EN_REVISION"}).json()
    assert [r["id"] for r in en_revision] == [reserva_740["id"]]


def test_si_falla_pasar_a_revision_el_bloqueo_tambien_se_revierte(reserva_740, entrar, monkeypatch):
    def fallar(self):
        raise RuntimeError("falla en Reservas")

    monkeypatch.setattr(apps.get_model("reservas", "Reserva"), "pasar_a_revision", fallar)
    assert _bloquear(entrar, reserva_740["publicacion"]).status_code == 500
    assert apps.get_model("catalogo", "Publicacion").objects.get(pk=reserva_740["publicacion"]).estado == "ACTIVA"
    assert Reserva().objects.get(pk=reserva_740["id"]).estado == "CONFIRMADA"


def test_ca_20_2_mantener_vuelve_a_confirmada(reserva_740, entrar):
    _bloquear(entrar, reserva_740["publicacion"])
    r = _resolver(entrar, reserva_740["id"], mantener=True)
    assert r.status_code == 200 and r.json()["estado"] == "CONFIRMADA"
    assert not Cancelacion().objects.exists()


def test_ca_20_3_cancelar_devuelve_el_100_y_libera_las_noches(reserva_740, entrar, reloj):
    _bloquear(entrar, reserva_740["publicacion"])
    reloj("2026-11-18")
    assert _resolver(entrar, reserva_740["id"], mantener=False).status_code == 400  # motivo obligatorio
    r = _resolver(entrar, reserva_740["id"], mantener=False, motivo="El anfitrión no puede cumplir")
    assert r.json()["estado"] == "CANCELADA" and r.json()["cancelacion"]["valor_devolucion"] == "740000.00"
    admin = apps.get_model("identidad", "Usuario").objects.get(correo="admin@inversioneslr.com")
    assert Cancelacion().objects.get(reserva_id=reserva_740["id"]).cancelada_por_id == admin.id
    assert apps.get_model("pagos", "Pago").objects.get(reserva_id=reserva_740["id"], tipo="DEVOLUCION").monto == Decimal("740000")
    assert not apps.get_model("reservas", "NocheNoDisponible").objects.filter(publicacion_id=reserva_740["publicacion"]).exists()


def test_solo_se_resuelven_reservas_en_revision(reserva_740, entrar):
    assert _resolver(entrar, reserva_740["id"], mantener=True).status_code == 409
    assert entrar("huesped@correo.com").post(f"/api/v1/admin/reservas/{reserva_740['id']}/resolver",
                                             {"mantener": True}, format="json").status_code == 403


def test_ca_20_4_desbloquear_deja_pausada_y_el_anfitrion_reactiva(reserva_740, entrar):
    pid = reserva_740["publicacion"]
    _bloquear(entrar, pid)
    assert entrar("admin@inversioneslr.com").delete(f"/api/v1/admin/publicaciones/{pid}/bloqueo").json()["estado"] == "PAUSADA"
    assert entrar("anfitrion@correo.com").post(f"/api/v1/catalogo/publicaciones/{pid}/reactivar").json()["estado"] == "ACTIVA"


def test_ca_20_5_sin_resolucion_al_llegar_se_cancela_y_avisa(reserva_740, entrar, reloj, django_capture_on_commit_callbacks):
    _bloquear(entrar, reserva_740["publicacion"])
    reloj("2026-11-19")
    assert services.cancelar_en_revision_vencidas() == 0  # todavía no llega
    reloj("2026-11-20")
    with django_capture_on_commit_callbacks(execute=True):
        assert services.cancelar_en_revision_vencidas() == 1
    c = Cancelacion().objects.get(reserva_id=reserva_740["id"])
    assert (c.motivo, c.cancelada_por_id, c.valor_devolucion, c.porcentaje_devolucion) == (
        "Sin resolución antes de la llegada", None, Decimal("740000"), Decimal("100"))
    assert Reserva().objects.get(pk=reserva_740["id"]).estado == "CANCELADA"
    for correo in ("huesped@correo.com", "anfitrion@correo.com"):
        tipos = [n["tipo"] for n in entrar(correo).get("/api/v1/notificaciones").json()["notificaciones"] if not n["leida"]]
        assert "ReservaCancelada" in tipos


def test_restringir_no_cambia_las_reservas_del_anfitrion_ni_del_huesped(reserva_740, entrar):
    Usuario = apps.get_model("identidad", "Usuario")
    admin = entrar("admin@inversioneslr.com")
    antes = dict(Reserva().objects.values_list("id", "estado"))
    for correo in ("anfitrion@correo.com", "huesped@correo.com"):
        uid = Usuario.objects.get(correo=correo).id
        assert admin.post(f"/api/v1/admin/usuarios/{uid}/restriccion", {"motivo": "Prueba"}, format="json").status_code == 201
    assert dict(Reserva().objects.values_list("id", "estado")) == antes
    assert Reserva().objects.get(pk=reserva_740["id"]).estado == "CONFIRMADA"
