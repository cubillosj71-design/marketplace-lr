"""MAL-34: Reservas de mis alojamientos con portada y ciudad, y el detalle de la reserva para el anfitrión
(CU-RES-03, RF-D-RES-03.1, HU-26).

El anfitrión ve solo las reservas de sus publicaciones, con el nombre del huésped pero sin sus datos de contacto, y
sin la devolución de "si cancelas hoy": cancelar es solo del huésped (CA-15.5)."""

import json

import pytest
from django.apps import apps

pytestmark = pytest.mark.django_db

Publicacion = lambda: apps.get_model("catalogo", "Publicacion")  # noqa: E731
Imagen = lambda: apps.get_model("catalogo", "ImagenPublicacion")  # noqa: E731
Usuario = lambda: apps.get_model("identidad", "Usuario")  # noqa: E731


@pytest.fixture
def reserva_740(alojamiento_740, reservar, reloj):
    """Reserva CONFIRMADA de $740.000 en una publicación de Laura (anfitrion@correo.com), hecha por Carlos."""
    reloj("2026-11-01")
    return reservar(alojamiento_740, "2026-11-20", "2026-11-23")


def test_listado_del_anfitrion_trae_portada_y_ciudad_sin_n_mas_1(demo, entrar, django_assert_max_num_queries):
    a = entrar("anfitrion@correo.com")
    lista = a.get("/api/v1/reservas/de-mis-alojamientos").json()
    propias = set(Publicacion().objects.filter(anfitrion__correo="anfitrion@correo.com").values_list("id", flat=True))
    ids = {r["publicacion"] for r in lista}
    assert len(lista) >= 8 and len(ids) >= 3 and ids <= propias  # solo sus publicaciones
    assert any(r["estado"] == "CANCELADA" for r in lista)  # incluidas las canceladas (CA-26.2)

    portadas = {i.publicacion_id: i.ruta for i in Imagen().objects.filter(publicacion_id__in=ids, orden=1)}
    ciudades = dict(Publicacion().objects.filter(pk__in=ids).values_list("id", "ciudad__nombre"))
    for r in lista:
        assert (r["portada"], r["ciudad"]) == (portadas[r["publicacion"]], ciudades[r["publicacion"]])
        assert r["huesped_nombre"]

    # Las consultas no crecen con el número de reservas (una por reserva serían más de 20)
    with django_assert_max_num_queries(12):
        assert len(a.get("/api/v1/reservas/de-mis-alojamientos").json()) == len(lista)


def test_detalle_del_anfitrion_sin_contacto_del_huesped_ni_devolucion(reserva_740, entrar):
    r = entrar("anfitrion@correo.com").get(f"/api/v1/reservas/{reserva_740['id']}")
    assert r.status_code == 200, r.content
    d = r.json()
    assert d["huesped_nombre"] == "Carlos Ruiz"
    assert d["desglose"]["total"] == "740000.00" and d["politica_cancelacion"]["nombre"] == "Moderada"
    assert d["devolucion_hoy"] is None  # el anfitrión no cancela
    huesped = Usuario().objects.get(correo="huesped@correo.com")
    texto = json.dumps(d, default=str)
    for dato in (huesped.correo, huesped.telefono, huesped.telefono.replace(" ", "")):
        assert dato not in texto
    assert not {"correo", "telefono", "huesped_correo", "huesped_telefono"} & set(d)


def test_el_anfitrion_ve_quien_cancelo(reserva_740, entrar, reloj):
    reloj("2026-11-15")
    assert entrar("huesped@correo.com").post(f"/api/v1/reservas/{reserva_740['id']}/cancelar", {"motivo": "Cambio de planes"},
                                             format="json").status_code == 200
    d = entrar("anfitrion@correo.com").get(f"/api/v1/reservas/{reserva_740['id']}").json()
    c = d["cancelacion"]
    assert (c["cancelada_por_rol"], c["motivo"], c["valor_devolucion"]) == ("HUESPED", "Cambio de planes", "370000.00")
    lista = entrar("anfitrion@correo.com").get("/api/v1/reservas/de-mis-alojamientos").json()
    assert next(x for x in lista if x["id"] == reserva_740["id"])["cancelacion"]["cancelada_por_rol"] == "HUESPED"


def test_cancelaciones_de_la_demo_por_huesped_y_automatica(demo, entrar):
    roles = set()
    admin = entrar("admin@inversioneslr.com")
    for r in admin.get("/api/v1/admin/reservas").json():
        if r["cancelacion"]:
            roles.add(r["cancelacion"]["cancelada_por_rol"])
            assert (r["cancelacion"]["cancelada_por_rol"] == "AUTOMATICA") == r["cancelacion"]["automatica"]
    assert "HUESPED" in roles and roles <= {"HUESPED", "ADMINISTRADOR", "AUTOMATICA"}


def test_otro_anfitrion_no_ve_el_detalle_y_queda_en_la_auditoria(reserva_740, entrar, eventos):
    otro = entrar("sofia@correo.com")
    r = otro.get(f"/api/v1/reservas/{reserva_740['id']}")
    assert r.status_code == 403 and "desglose" not in r.json()
    assert "AccesoDenegado" in eventos(actor_id=otro.usuario["id"])
    assert reserva_740["id"] not in {x["id"] for x in otro.get("/api/v1/reservas/de-mis-alojamientos").json()}


def test_el_selector_por_alojamiento_solo_ofrece_publicaciones_propias(demo, entrar):
    """El selector "Alojamiento" de la pantalla se llena con GET /catalogo/mis-publicaciones."""
    a = entrar("anfitrion@correo.com")
    r = a.get("/api/v1/catalogo/mis-publicaciones", {"page_size": 100})
    assert r.status_code == 200
    datos = r.json()
    filas = datos["results"] if isinstance(datos, dict) else datos
    ids = {p["id"] for p in filas}
    propias = set(Publicacion().objects.filter(anfitrion__correo="anfitrion@correo.com").values_list("id", flat=True))
    assert ids == propias and len(ids) >= 3
    # Toda reserva de su listado es de una publicación del selector
    assert {x["publicacion"] for x in a.get("/api/v1/reservas/de-mis-alojamientos").json()} <= ids
