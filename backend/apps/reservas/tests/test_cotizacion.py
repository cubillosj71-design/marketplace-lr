"""HU-12 Cotizar (RF-D-RES-02.1): CA-12.1 a CA-12.3, CA-05.1 y el límite de 12 meses."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.apps import apps

from apps.comun.fechas import fecha_maxima

pytestmark = pytest.mark.django_db
COTIZAR = "/api/v1/reservas/cotizaciones"


@pytest.fixture
def alojamiento(publicar):
    """$200.000 por noche, limpieza $50.000, desayuno $30.000, 10 % de descuento desde 7 noches, capacidad 4.
    La tarifa de servicio vigente de la demo es del 10 %."""
    return publicar("Ejemplo del SRS", precio=200000, limpieza=50000, adicionales=[("Desayuno", 30000)], descuento=(10, 7), capacidad=4)


def _desayuno(pid):
    return apps.get_model("catalogo", "ServicioAdicional").objects.get(publicacion_id=pid, nombre="Desayuno").id


def _cotizar(c, pid, llegada, salida, huespedes=2, adicionales=()):
    return c.post(COTIZAR, {"publicacion": pid, "fecha_llegada": llegada.isoformat(), "fecha_salida": salida.isoformat(),
                            "num_huespedes": huespedes, "adicionales": list(adicionales)}, format="json")


def test_ca_12_1_desglose_de_3_noches_con_desayuno(alojamiento, entrar, dias):
    r = _cotizar(entrar("huesped@correo.com"), alojamiento, dias(30), dias(33), adicionales=[_desayuno(alojamiento)])
    assert r.status_code == 201, r.content
    c = r.json()
    assert (c["noches"], c["precio_base"], c["descuento"], c["tarifa_limpieza"]) == (3, "600000.00", "0.00", "50000.00")
    assert (c["porcentaje_servicio"], c["tarifa_servicio"]) == ("10.00", "60000.00")
    assert c["adicionales"] == [{"id": _desayuno(alojamiento), "nombre": "Desayuno", "precio_aplicado": "30000.00"}]
    assert c["total"] == "740000.00"


def test_ca_12_2_descuento_desde_7_noches_y_servicio_sobre_el_neto(alojamiento, entrar, dias):
    c = _cotizar(entrar("huesped@correo.com"), alojamiento, dias(30), dias(37)).json()
    assert (c["precio_base"], c["descuento"]) == ("1400000.00", "140000.00")
    assert Decimal(c["tarifa_servicio"]) == Decimal("1260000") * Decimal("0.10")  # sobre $1.260.000
    assert c["total"] == "1436000.00"  # 1.400.000 - 140.000 + 50.000 + 126.000


def test_cotizacion_guarda_la_tarifa_usada_y_vence_a_los_30_minutos(alojamiento, entrar, dias):
    c = _cotizar(entrar("huesped@correo.com"), alojamiento, dias(30), dias(33)).json()
    cot = apps.get_model("reservas", "Cotizacion").objects.get(pk=c["id"])
    assert cot.tarifa_servicio_ref.porcentaje == Decimal("10")
    assert timedelta(minutes=29) < cot.vence - cot.creada <= timedelta(minutes=30, seconds=1)


def test_ca_12_3_mas_huespedes_que_la_capacidad(alojamiento, entrar, dias):
    r = _cotizar(entrar("huesped@correo.com"), alojamiento, dias(30), dias(33), huespedes=5)
    assert r.status_code == 400 and r.json()["capacidad_maxima"] == 4 and "capacidad máxima" in r.json()["detalle"]


def test_ca_05_1_visitante_no_cotiza(alojamiento, cliente, dias):
    assert _cotizar(cliente, alojamiento, dias(30), dias(33)).status_code == 401


def test_solo_el_huesped_cotiza(alojamiento, entrar, dias):
    assert _cotizar(entrar("anfitrion@correo.com"), alojamiento, dias(30), dias(33)).status_code == 403


def test_no_cotiza_fechas_ocupadas_ni_publicacion_no_buscable(alojamiento, entrar, dias):
    h = entrar("huesped@correo.com")
    entrar("anfitrion@correo.com").post(f"/api/v1/catalogo/publicaciones/{alojamiento}/calendario",
                                        {"fecha_inicio": dias(31).isoformat(), "fecha_fin": dias(32).isoformat(), "tipo": "NO_DISPONIBLE"}, format="json")
    r = _cotizar(h, alojamiento, dias(30), dias(33))
    assert r.status_code == 409 and r.json()["fechas"] == [dias(31).isoformat()]
    pausada = apps.get_model("catalogo", "Publicacion").objects.get(titulo="Cabaña El Roble").id
    assert _cotizar(h, pausada, dias(30), dias(33)).status_code == 404


def test_adicional_de_otro_alojamiento_no_se_acepta(alojamiento, publicar, entrar, dias):
    otro = publicar("Otro", adicionales=[("Traslado", 70000)])
    ajeno = apps.get_model("catalogo", "ServicioAdicional").objects.get(publicacion_id=otro).id
    r = _cotizar(entrar("huesped@correo.com"), alojamiento, dias(30), dias(33), adicionales=[ajeno])
    assert r.status_code == 400 and r.json()["campo"] == "adicionales"


def test_limite_de_12_meses_y_fechas_pasadas(alojamiento, entrar, dias):
    h = entrar("huesped@correo.com")
    limite = fecha_maxima()
    r = _cotizar(h, alojamiento, limite - timedelta(days=2), limite + timedelta(days=1))
    assert r.status_code == 400 and r.json()["campo"] == "fecha_salida"
    assert _cotizar(h, alojamiento, limite - timedelta(days=2), limite).status_code == 201
    assert _cotizar(h, alojamiento, dias(-1), dias(2)).status_code == 400
