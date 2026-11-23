"""MAL-36: pantalla "Reservas en revisión" del Administrador (RF-D-ADM-01.2, HU-20).

Pendientes (EN_REVISION) con portada, ciudad, anfitrión, motivo y fecha del bloqueo y días para la llegada, sin una
consulta por reserva. Resueltas con el resultado: mantenida, cancelada por el administrador o cancelada
automáticamente. Todo sale de datos que ya existen: historial de revisiones, cancelacion y registro de acciones."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.reservas import services

pytestmark = pytest.mark.django_db
ADMIN = "admin@inversioneslr.com"
PENDIENTES, RESUELTAS = "/api/v1/admin/reservas?estado=EN_REVISION", "/api/v1/admin/reservas/resueltas"


def _bloquear(entrar, pid, motivo="Información engañosa"):
    r = entrar(ADMIN).post(f"/api/v1/admin/publicaciones/{pid}/bloqueo", {"motivo": motivo}, format="json")
    assert r.status_code == 200, r.content


def _resolver(entrar, rid, **datos):
    r = entrar(ADMIN).post(f"/api/v1/admin/reservas/{rid}/resolver", datos, format="json")
    assert r.status_code == 200, r.content
    return r.json()


@pytest.fixture
def tres_en_revision(publicar, reservar, entrar, reloj):
    """Tres publicaciones bloqueadas, cada una con una reserva que pasó a EN_REVISION (llegadas 20, 25 y 30 de nov)."""
    reloj("2026-11-01")
    reservas = []
    for n, (ciudad, llegada, salida) in enumerate([("Cartagena", "2026-11-30", "2026-12-02"), ("Salento", "2026-11-20", "2026-11-23"),
                                                    ("Barichara", "2026-11-25", "2026-11-27")]):
        pid = publicar(f"Revisión {n}", ciudad=ciudad, adicionales=[("Desayuno", 30000)])
        reservas.append(reservar(pid, llegada, salida))
        _bloquear(entrar, pid, f"Motivo {n}")
    return reservas


# ---------------- Pendientes
def test_pendientes_traen_portada_ciudad_y_bloqueo_sin_n_mas_1(publicar, reservar, entrar, reloj):
    reloj("2026-11-01")
    admin = entrar(ADMIN)

    def crear(n, ciudad, llegada):
        pid = publicar(f"Bloqueada {n}", ciudad=ciudad)
        reservar(pid, llegada, "2026-12-15", desayuno=False)
        _bloquear(entrar, pid, f"Fotos que no son del alojamiento ({n})")

    def consultas():
        with CaptureQueriesContext(connection) as c:
            datos = admin.get(PENDIENTES).json()
        return len(c.captured_queries), datos

    crear(0, "Popayán", "2026-12-10")
    una, _ = consultas()
    for n, (ciudad, llegada) in enumerate([("Jardín", "2026-12-04"), ("San Gil", "2026-12-06"), ("Pereira", "2026-12-08")], start=1):
        crear(n, ciudad, llegada)
    cuatro, datos = consultas()
    assert cuatro == una  # las consultas no crecen con el número de reservas
    datos = [d for d in datos if d["alojamiento"].startswith("Bloqueada")]  # sin la de la demo (Loft Chapinero)

    assert [d["ciudad"] for d in datos] == ["Jardín", "San Gil", "Pereira", "Popayán"]  # primero la llegada más cercana
    for d in datos:
        assert d["estado"] == "EN_REVISION" and d["portada"].startswith("https://placehold.co/")
        assert d["bloqueo"]["motivo"].startswith("Fotos que no son del alojamiento") and d["bloqueo"]["fecha"]  # hora real del bloqueo (auto_now_add)
        assert (d["huesped_nombre"], d["anfitrion_nombre"]) == ("Carlos Ruiz", "Laura Gómez")
    assert [d["dias_para_llegada"] for d in datos] == [33, 35, 37, 39]


def test_pendientes_de_la_demo_traen_el_motivo_del_bloqueo(demo, entrar):
    d = entrar(ADMIN).get(PENDIENTES).json()
    assert [x["alojamiento"] for x in d] == ["Loft Chapinero"]
    assert d[0]["bloqueo"]["motivo"] == "La dirección publicada no coincide con la del alojamiento."
    assert d[0]["ciudad"] == "Bogotá" and d[0]["portada"] == "/alojamientos/chapinero-sala.jpg"


# ---------------- Resueltas
def test_resueltas_distinguen_mantenida_cancelada_por_el_administrador_y_automatica(tres_en_revision, entrar, reloj):
    cartagena, salento, barichara = tres_en_revision
    reloj("2026-11-10")
    _resolver(entrar, cartagena["id"], mantener=True)
    _resolver(entrar, barichara["id"], mantener=False, motivo="Publicación engañosa")
    reloj("2026-11-20")  # llega el día de llegada de Salento sin resolverla: se cancela sola
    assert services.cancelar_en_revision_vencidas() == 1

    pendientes = {d["id"] for d in entrar(ADMIN).get(PENDIENTES).json()}
    assert not pendientes & {cartagena["id"], salento["id"], barichara["id"]}
    datos = entrar(ADMIN).get(RESUELTAS).json()
    por_ciudad = {d["ciudad"]: d for d in datos}
    assert set(por_ciudad) == {"Cartagena", "Salento", "Barichara"}

    m = por_ciudad["Cartagena"]["resolucion"]
    assert (m["resultado"], m["por"]) == ("MANTENIDA", "Admin LR") and m["fecha"]  # hora del registro de acciones
    assert por_ciudad["Cartagena"]["estado"] == "CONFIRMADA"

    a = por_ciudad["Barichara"]["resolucion"]
    assert (a["resultado"], a["por"], a["motivo"]) == ("CANCELADA_ADMINISTRADOR", "Admin LR", "Publicación engañosa")
    assert a["valor_devolucion"] == por_ciudad["Barichara"]["total"]  # 100 %

    s = por_ciudad["Salento"]["resolucion"]
    assert (s["resultado"], s["por"], s["motivo"]) == ("CANCELADA_AUTOMATICA", None, "Sin resolución antes de la llegada")
    assert s["valor_devolucion"] == por_ciudad["Salento"]["total"]

    assert [d["ciudad"] for d in datos] == ["Salento", "Barichara", "Cartagena"]  # la resolución más reciente primero
    assert all(d["bloqueo"]["motivo"].startswith("Motivo") for d in datos)


def test_una_reserva_que_nunca_estuvo_en_revision_no_sale_en_resueltas(demo, entrar):
    ids = {d["id"] for d in entrar(ADMIN).get(RESUELTAS).json()}
    assert ids == set()  # en la demo la única que pasó a EN_REVISION sigue pendiente


def test_mantenida_y_luego_cancelada_por_el_huesped_sigue_como_mantenida(tres_en_revision, entrar, reloj):
    cartagena = tres_en_revision[0]
    reloj("2026-11-10")
    _resolver(entrar, cartagena["id"], mantener=True)
    r = entrar("huesped@correo.com").post(f"/api/v1/reservas/{cartagena['id']}/cancelar", {"motivo": "Ya no viajo"}, format="json")
    assert r.status_code == 200
    d = next(x for x in entrar(ADMIN).get(RESUELTAS).json() if x["id"] == cartagena["id"])
    assert d["resolucion"]["resultado"] == "MANTENIDA" and d["estado"] == "CANCELADA"


# ---------------- Detalle
def test_detalle_del_administrador_trae_bloqueo_desglose_y_resultado(tres_en_revision, entrar, reloj):
    barichara = tres_en_revision[2]
    admin = entrar(ADMIN)
    d = admin.get(f"/api/v1/admin/reservas/{barichara['id']}").json()
    assert d["bloqueo"]["motivo"] == "Motivo 2" and d["resolucion"] is None and d["dias_para_llegada"] == 24
    assert d["desglose"]["total"] == barichara["total"] and d["politica_cancelacion"]["nombre"] == "Moderada"
    assert (d["huesped_nombre"], d["anfitrion_nombre"]) == ("Carlos Ruiz", "Laura Gómez")
    assert d["devolucion_hoy"] is None  # cancelar como huésped no es del administrador
    reloj("2026-11-10")
    _resolver(entrar, barichara["id"], mantener=False, motivo="Publicación engañosa")
    assert admin.get(f"/api/v1/admin/reservas/{barichara['id']}").json()["resolucion"]["resultado"] == "CANCELADA_ADMINISTRADOR"


# ---------------- Permisos
@pytest.mark.parametrize("correo", ["huesped@correo.com", "anfitrion@correo.com"])
def test_huesped_y_anfitrion_no_ven_esta_informacion_y_queda_registrado(tres_en_revision, entrar, eventos, correo):
    c = entrar(correo)
    rid = tres_en_revision[0]["id"]
    for ruta in (PENDIENTES, RESUELTAS, f"/api/v1/admin/reservas/{rid}"):
        r = c.get(ruta)
        assert r.status_code == 403, ruta
        assert "bloqueo" not in r.content.decode()
    assert eventos(actor_id=c.usuario["id"]).count("AccesoDenegado") == 3
