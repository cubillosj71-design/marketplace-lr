"""MAL-34: Mis reservas con portada y ciudad, y el detalle de la reserva (CU-RES-03, RF-D-RES-03.1).

El listado trae la portada y la ciudad de cada alojamiento sin una consulta por reserva. El detalle muestra el
desglose y la política guardados al reservar, la devolución si el huésped cancela hoy y el pago simulado."""

from decimal import Decimal

import pytest
from django.apps import apps

pytestmark = pytest.mark.django_db

Publicacion = lambda: apps.get_model("catalogo", "Publicacion")  # noqa: E731
Imagen = lambda: apps.get_model("catalogo", "ImagenPublicacion")  # noqa: E731
Reserva = lambda: apps.get_model("reservas", "Reserva")  # noqa: E731


@pytest.fixture
def reserva_740(alojamiento_740, reservar, reloj):
    """Reserva CONFIRMADA de $740.000 del 20 al 23 de noviembre de 2026 (política Moderada), hecha el 1 de noviembre."""
    reloj("2026-11-01")
    r = reservar(alojamiento_740, "2026-11-20", "2026-11-23")
    assert r["total"] == "740000.00"
    return r


# ---------------- Listado: portada y ciudad sin N+1
def test_mis_reservas_trae_portada_y_ciudad_sin_n_mas_1(demo, entrar, django_assert_max_num_queries):
    h = entrar("huesped@correo.com")
    lista = h.get("/api/v1/reservas/mias").json()
    ids = {r["publicacion"] for r in lista}
    assert len(lista) >= 10 and len(ids) >= 5  # Carlos tiene reservas en varios alojamientos de la demo

    portadas = {i.publicacion_id: i.ruta for i in Imagen().objects.filter(publicacion_id__in=ids, orden=1)}
    ciudades = dict(Publicacion().objects.filter(pk__in=ids).values_list("id", "ciudad__nombre"))
    for r in lista:
        assert r["portada"] == portadas[r["publicacion"]]  # la imagen de orden 1
        assert r["ciudad"] == ciudades[r["publicacion"]]

    # Las consultas no crecen con el número de reservas: sesión, tareas de vencimiento, reservas, títulos,
    # portadas con ciudad y nombres. Con una consulta por reserva serían más de 20.
    with django_assert_max_num_queries(12):
        assert len(h.get("/api/v1/reservas/mias").json()) == len(lista)


def test_obtener_portadas_y_ciudades_hace_una_sola_consulta(demo, django_assert_num_queries):
    from apps.catalogo import services as catalogo

    ids = list(Publicacion().objects.values_list("id", flat=True))
    with django_assert_num_queries(1):
        datos = catalogo.obtener_portadas_y_ciudades(ids)
    assert set(datos) == set(ids)
    assert all(d["portada"].startswith("/alojamientos/") for d in datos.values())


def test_publicacion_sin_imagen_no_trae_portada(reserva_740, entrar):
    Imagen().objects.filter(publicacion_id=reserva_740["publicacion"]).delete()
    r = next(x for x in entrar("huesped@correo.com").get("/api/v1/reservas/mias").json() if x["id"] == reserva_740["id"])
    assert r["portada"] is None and r["ciudad"] == "Cartagena"


# ---------------- Detalle: desglose y política guardados
def test_detalle_trae_el_desglose_guardado_aunque_cambie_el_precio(reserva_740, entrar):
    # El anfitrión sube el precio y la limpieza, y cambia el desayuno, después de la reserva
    Publicacion().objects.filter(pk=reserva_740["publicacion"]).update(precio_noche=Decimal("999000"), tarifa_limpieza=Decimal("1"))
    apps.get_model("catalogo", "ServicioAdicional").objects.filter(publicacion_id=reserva_740["publicacion"]).update(precio=Decimal("5"))

    r = entrar("huesped@correo.com").get(f"/api/v1/reservas/{reserva_740['id']}")
    assert r.status_code == 200, r.content
    d = r.json()
    assert d["desglose"] == {
        "noches": 3, "precio_noche": "200000.00", "precio_base": "600000.00", "descuento": "0.00",
        "tarifa_limpieza": "50000.00", "porcentaje_servicio": "10.00", "tarifa_servicio": "60000.00",
        "adicionales": [{"id": d["desglose"]["adicionales"][0]["id"], "nombre": "Desayuno", "precio_aplicado": "30000.00"}],
        "total_adicionales": "30000.00", "total": "740000.00",
    }
    assert (d["alojamiento"], d["ciudad"], d["num_huespedes"], d["noches"]) == ("Ejemplo 740", "Cartagena", 2, 3)
    assert d["portada"].startswith("https://placehold.co/")
    assert d["anfitrion_nombre"] == "Laura Gómez"
    assert d["politica_cancelacion"]["nombre"] == "Moderada"
    assert [(t["dias_minimos"], t["dias_maximos"], t["porcentaje_devolucion"]) for t in d["politica_cancelacion"]["tramos"]] == [
        (7, None, "100.00"), (2, 6, "50.00"), (0, 1, "0.00")]
    pago = d["pagos"][0]
    assert pago["tipo"] == "COBRO" and pago["estado"] == "APROBADO" and pago["referencia_externa"]


@pytest.mark.parametrize("dia, dias, porcentaje, valor", [
    ("2026-11-10", 10, "100.00", "740000.00"),   # 7 días o más: 100 %
    ("2026-11-15", 5, "50.00", "370000.00"),     # de 2 a 6 días: 50 %
    ("2026-11-19", 1, "0.00", "0.00"),           # menos de 2 días: 0 %, todavía se puede cancelar
])
def test_devolucion_si_cancela_hoy_en_los_tres_tramos(reserva_740, entrar, reloj, dia, dias, porcentaje, valor):
    reloj(dia)
    d = entrar("huesped@correo.com").get(f"/api/v1/reservas/{reserva_740['id']}").json()["devolucion_hoy"]
    assert d == {"cancelable": True, "dias_anticipacion": dias, "porcentaje_devolucion": porcentaje, "valor_devolucion": valor}
    # Es el mismo cálculo de la ventana de cancelar
    sim = entrar("huesped@correo.com").get(f"/api/v1/reservas/{reserva_740['id']}/cancelar").json()
    assert {k: sim[k] for k in d} == d


def test_el_dia_de_llegada_ya_no_se_puede_cancelar(reserva_740, entrar, reloj):
    reloj("2026-11-20")
    d = entrar("huesped@correo.com").get(f"/api/v1/reservas/{reserva_740['id']}").json()
    assert d["cancelable"] is False and d["devolucion_hoy"]["cancelable"] is False


def test_detalle_de_cancelada_trae_fecha_motivo_y_valor(reserva_740, entrar, reloj):
    reloj("2026-11-15")
    h = entrar("huesped@correo.com")
    assert h.post(f"/api/v1/reservas/{reserva_740['id']}/cancelar", {"motivo": "Cambio de planes"}, format="json").status_code == 200
    d = h.get(f"/api/v1/reservas/{reserva_740['id']}").json()
    assert d["estado"] == "CANCELADA" and d["devolucion_hoy"] is None
    assert (d["cancelacion"]["motivo"], d["cancelacion"]["valor_devolucion"]) == ("Cambio de planes", "370000.00")
    assert d["cancelacion"]["fecha"].startswith("2026-11-15")
    assert {p["tipo"] for p in d["pagos"]} == {"COBRO", "DEVOLUCION"}


# ---------------- Permisos
def test_otro_huesped_no_ve_el_detalle_y_queda_en_la_auditoria(reserva_740, entrar, eventos):
    otro = entrar("santiago@correo.com")
    r = otro.get(f"/api/v1/reservas/{reserva_740['id']}")
    assert r.status_code == 403
    assert "desglose" not in r.json()
    assert "AccesoDenegado" in eventos(actor_id=otro.usuario["id"])


def test_el_anfitrion_de_la_publicacion_si_ve_el_detalle(reserva_740, entrar):
    r = entrar("anfitrion@correo.com").get(f"/api/v1/reservas/{reserva_740['id']}")
    assert r.status_code == 200 and r.json()["desglose"]["total"] == "740000.00"
