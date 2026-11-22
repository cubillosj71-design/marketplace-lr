"""RF-D-ADM-03.1, CA-22: la tarifa de servicio rige en un rango [vigente_desde, vigente_hasta).

Las fechas son relativas a hoy (dias), para que las pruebas no dependan del año en que se corran: la tarifa inicial de
la demo rige desde el 1 de enero del año en curso.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.auditoria import services as auditoria
from apps.reservas import services
from apps.reservas.models import Cotizacion, TarifaServicio

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin(django_user_model, demo):
    return django_user_model.objects.get(correo="admin@inversioneslr.com")


@pytest.fixture
def huesped(django_user_model, demo):
    return django_user_model.objects.get(correo="huesped@correo.com")


def _cambiar(reloj, admin, dia, porcentaje):
    reloj(f"{dia.isoformat()}T09:00")
    return services.cambiar_tarifa(admin, Decimal(porcentaje))


def test_un_cambio_de_tarifa_cierra_la_anterior_en_la_misma_transaccion(admin, reloj, dias):
    inicial = TarifaServicio.objects.get(vigente_hasta__isnull=True)
    nueva = _cambiar(reloj, admin, dias(1), "12")

    inicial.refresh_from_db()
    assert inicial.vigente_hasta == nueva["vigente_desde"]  # la anterior termina donde empieza la nueva
    assert nueva["vigente_hasta"] is None
    assert TarifaServicio.objects.filter(vigente_hasta__isnull=True).count() == 1
    evento = auditoria.consultar_eventos(accion="TarifaActualizada").get()
    assert evento.actor_id == admin.id and evento.detalle["tarifa_anterior"] == inicial.id
    assert evento.detalle["anterior"] == "10.00" and evento.detalle["nuevo"] == "12"


def test_la_consulta_por_rango_devuelve_las_tarifas_vigentes_en_el(admin, reloj, dias):
    _cambiar(reloj, admin, dias(1), "12")    # 10 % hasta el día 1; 12 % del día 1 al 10
    _cambiar(reloj, admin, dias(10), "15")   # 15 % desde el día 10

    def pct(desde, hasta):
        return [t["porcentaje"] for t in services.consultar_tarifas_vigentes(dias(desde), dias(hasta))]

    assert pct(3, 6) == ["12.00"]                     # dentro de la vigencia del 12 %
    assert pct(-5, 1) == ["10.00", "12.00"]           # el día 1 cambia a las 9:00: rigen las dos
    assert pct(10, 20) == ["12.00", "15.00"]          # el 12 % rige hasta las 9:00 del día 10
    assert pct(11, 40) == ["15.00"]                   # la vigente (sin fin) cubre cualquier fecha futura
    with pytest.raises(Exception, match="posterior"):
        services.consultar_tarifas_vigentes(dias(5), dias(4))


def test_el_historial_de_la_api_filtra_por_rango_y_trae_desde_y_hasta(admin, reloj, dias, entrar):
    _cambiar(reloj, admin, dias(1), "12")
    _cambiar(reloj, admin, dias(10), "15")
    reloj(f"{dias(10).isoformat()}T10:00")
    c = entrar("admin@inversioneslr.com")

    todo = c.get("/api/v1/admin/tarifa-servicio").json()["historial"]
    assert [t["porcentaje"] for t in todo] == ["15.00", "12.00", "10.00"]  # de la más reciente a la más antigua
    assert todo[0]["vigente_hasta"] is None and todo[1]["vigente_hasta"] == todo[0]["vigente_desde"]

    r = c.get("/api/v1/admin/tarifa-servicio", {"desde": dias(3).isoformat(), "hasta": dias(6).isoformat()})
    assert [t["porcentaje"] for t in r.json()["historial"]] == ["12.00"]
    assert c.get("/api/v1/admin/tarifa-servicio", {"desde": dias(6).isoformat(), "hasta": dias(3).isoformat()}).status_code == 400


def test_cada_cotizacion_usa_la_tarifa_vigente_en_su_fecha(admin, huesped, reloj, dias, alojamiento_740):
    llegada, salida = dias(60), dias(63)
    _cambiar(reloj, admin, dias(1), "12")
    reloj(f"{dias(5).isoformat()}T09:00")
    con_12 = services.cotizar_estancia(huesped, alojamiento_740, llegada, salida, 2)
    _cambiar(reloj, admin, dias(10), "15")
    reloj(f"{dias(12).isoformat()}T09:00")
    con_15 = services.cotizar_estancia(huesped, alojamiento_740, llegada, salida, 2)

    con_12 = Cotizacion.objects.select_related("tarifa_servicio_ref").get(pk=con_12.pk)
    con_15 = Cotizacion.objects.select_related("tarifa_servicio_ref").get(pk=con_15.pk)
    assert con_12.tarifa_servicio_ref.porcentaje == Decimal("12.00")
    assert con_15.tarifa_servicio_ref.porcentaje == Decimal("15.00")
    # 3 noches de $200.000: servicio del 12 % y del 15 % sobre $600.000 (CA-22.1: la primera no cambia)
    assert con_12.tarifa_servicio == Decimal("72000.00") and con_15.tarifa_servicio == Decimal("90000.00")
    # La tarifa usada es la que regía en la fecha de creación de la cotización
    for c in (con_12, con_15):
        t = c.tarifa_servicio_ref
        assert t.vigente_desde <= c.creada and (t.vigente_hasta is None or c.creada < t.vigente_hasta)


def test_el_check_rechaza_un_rango_invalido(admin):
    t = TarifaServicio.objects.get(vigente_hasta__isnull=True)
    with pytest.raises(IntegrityError, match="tarifa_hasta_mayor_que_desde"), transaction.atomic():
        TarifaServicio.objects.filter(pk=t.pk).update(vigente_hasta=t.vigente_desde - timedelta(days=1))
    with pytest.raises(IntegrityError, match="tarifa_hasta_mayor_que_desde"), transaction.atomic():
        TarifaServicio.objects.filter(pk=t.pk).update(vigente_hasta=t.vigente_desde)


def test_no_puede_haber_dos_tarifas_abiertas_a_la_vez(admin):
    t = TarifaServicio.objects.get(vigente_hasta__isnull=True)
    with pytest.raises(IntegrityError, match="tarifa_una_sola_vigente"), transaction.atomic():
        TarifaServicio.objects.create(administrador=admin, porcentaje=Decimal("12"), vigente_desde=t.vigente_desde + timedelta(days=1))
