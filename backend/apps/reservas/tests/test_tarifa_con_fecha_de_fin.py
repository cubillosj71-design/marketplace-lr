"""RF-D-ADM-03.1 (cambio pedido por el profesor, 2026-11-23): la tarifa de servicio puede tener fecha de fin.

Una tarifa con fecha de fin rige hasta el final de ese día y, al terminar, vuelve a cobrarse la tarifa sin fecha de
fin, así que ningún día queda sin tarifa. Lo último que guarda el Administrador es lo que se cobra. Dos tarifas con
fecha de fin no se cruzan y no se programan hacia atrás. Las fechas son relativas a hoy (dias) para no depender del
año en que se corran.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.auditoria import services as auditoria
from apps.comun.errores import Conflicto, ErrorNegocio, NoEncontrado
from apps.reservas import services
from apps.reservas.models import Cotizacion, TarifaServicio

pytestmark = pytest.mark.django_db
RUTA = "/api/v1/admin/tarifa-servicio"


@pytest.fixture
def admin(django_user_model, demo):
    return django_user_model.objects.get(correo="admin@inversioneslr.com")


@pytest.fixture
def huesped(django_user_model, demo):
    return django_user_model.objects.get(correo="huesped@correo.com")


def _a_las(reloj, dia, hora="09:00"):
    reloj(f"{dia.isoformat()}T{hora}")


def _porcentaje_cotizado(huesped, alojamiento, dias) -> Decimal:
    cot = services.cotizar_estancia(huesped, alojamiento, dias(90), dias(93), 2)
    return Cotizacion.objects.select_related("tarifa_servicio_ref").get(pk=cot.pk).tarifa_servicio_ref.porcentaje


def test_la_programada_reemplaza_a_la_base_solo_en_sus_fechas(admin, huesped, reloj, dias, alojamiento_740):
    _a_las(reloj, dias(1))
    services.programar_tarifa(admin, Decimal("15"), dias(10), dias(12))
    _a_las(reloj, dias(9), "23:59")
    assert _porcentaje_cotizado(huesped, alojamiento_740, dias) == Decimal("10.00")  # la base
    for dia in (dias(10), dias(11), dias(12)):  # el día `hasta` se cuenta completo
        _a_las(reloj, dia, "23:30")
        assert _porcentaje_cotizado(huesped, alojamiento_740, dias) == Decimal("15.00")
    _a_las(reloj, dias(13), "00:01")
    assert _porcentaje_cotizado(huesped, alojamiento_740, dias) == Decimal("10.00")  # vuelve la base: nunca hay hueco


def test_si_empieza_hoy_rige_desde_este_momento(admin, reloj, dias):
    _a_las(reloj, dias(0), "15:00")
    t = services.programar_tarifa(admin, Decimal("12"), dias(0), dias(2))
    assert timezone.localtime(t["vigente_desde"]).hour == 15  # las cotizaciones de la mañana conservan su tarifa
    assert t["estado"] == "VIGENTE" and t["programada"] is True


@pytest.mark.parametrize("desde,hasta,porcentaje,campo", [
    (-1, 3, "12", "desde"),   # hacia atrás
    (5, 4, "12", "hasta"),    # fin antes del inicio
    (5, 8, "35", "porcentaje"),  # CA-22.2
])
def test_fechas_y_porcentaje_invalidos(admin, reloj, dias, desde, hasta, porcentaje, campo):
    _a_las(reloj, dias(0))
    with pytest.raises(ErrorNegocio) as e:
        services.programar_tarifa(admin, Decimal(porcentaje), dias(desde), dias(hasta))
    assert e.value.campo == campo


def test_dos_programadas_no_se_cruzan(admin, reloj, dias):
    _a_las(reloj, dias(0))
    services.programar_tarifa(admin, Decimal("15"), dias(10), dias(20))
    for desde, hasta in ((15, 25), (5, 10), (20, 22), (12, 14)):
        with pytest.raises(Conflicto) as e:
            services.programar_tarifa(admin, Decimal("12"), dias(desde), dias(hasta))
        assert "Ya hay una tarifa con fecha de fin" in e.value.detalle
    services.programar_tarifa(admin, Decimal("12"), dias(21), dias(25))  # empieza al día siguiente: no se cruza


def test_la_base_de_datos_tambien_impide_el_cruce(admin, dias):
    """Defensa: aunque el servicio fallara, la restricción EXCLUDE rechaza dos programadas cruzadas."""
    inicio = timezone.now() + timedelta(days=30)
    TarifaServicio.objects.create(administrador=admin, porcentaje=Decimal("5"), vigente_desde=inicio,
                                  vigente_hasta=inicio + timedelta(days=5), programada=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        TarifaServicio.objects.create(administrador=admin, porcentaje=Decimal("6"), vigente_desde=inicio + timedelta(days=2),
                                      vigente_hasta=inicio + timedelta(days=9), programada=True)


def test_una_programada_siempre_tiene_fin(admin):
    with pytest.raises(IntegrityError), transaction.atomic():
        TarifaServicio.objects.create(administrador=admin, porcentaje=Decimal("5"), vigente_desde=timezone.now(), programada=True)


def test_cancelar_solo_antes_de_empezar(admin, reloj, dias):
    _a_las(reloj, dias(0))
    futura = services.programar_tarifa(admin, Decimal("15"), dias(10), dias(12))
    services.cancelar_tarifa_programada(admin, futura["id"])
    assert not TarifaServicio.objects.filter(pk=futura["id"]).exists()
    assert auditoria.consultar_eventos(accion="TarifaProgramadaCancelada").get().entidad_id == futura["id"]

    en_curso = services.programar_tarifa(admin, Decimal("15"), dias(1), dias(5))
    _a_las(reloj, dias(2))
    with pytest.raises(Conflicto):
        services.cancelar_tarifa_programada(admin, en_curso["id"])
    base = TarifaServicio.objects.get(programada=False, vigente_hasta__isnull=True)
    with pytest.raises(NoEncontrado):  # la base no se cancela: se cambia
        services.cancelar_tarifa_programada(admin, base.id)


def test_lo_ultimo_que_se_guarda_es_lo_que_se_cobra(admin, huesped, reloj, dias, alojamiento_740):
    """Una tarifa con fecha de fin en curso termina cuando se guarda otra (con o sin fecha de fin)."""
    _a_las(reloj, dias(0), "09:00")
    primera = services.programar_tarifa(admin, Decimal("20"), dias(0), dias(5))
    _a_las(reloj, dias(1), "10:00")
    segunda = services.programar_tarifa(admin, Decimal("12"), dias(1), dias(3))  # reemplaza a la de 20 %
    assert TarifaServicio.objects.get(pk=primera["id"]).vigente_hasta == segunda["vigente_desde"]
    assert _porcentaje_cotizado(huesped, alojamiento_740, dias) == Decimal("12.00")
    _a_las(reloj, dias(2), "10:00")
    services.cambiar_tarifa(admin, Decimal("11"))  # sin fecha de fin: termina la de 12 % y se cobra desde ya
    assert _porcentaje_cotizado(huesped, alojamiento_740, dias) == Decimal("11.00")
    _a_las(reloj, dias(6), "10:00")
    assert _porcentaje_cotizado(huesped, alojamiento_740, dias) == Decimal("11.00")


def test_cambiar_la_base_no_toca_las_programadas(admin, reloj, dias):
    _a_las(reloj, dias(0))
    programada = services.programar_tarifa(admin, Decimal("15"), dias(10), dias(12))
    _a_las(reloj, dias(1))
    services.cambiar_tarifa(admin, Decimal("11"))
    assert TarifaServicio.objects.get(pk=programada["id"]).porcentaje == Decimal("15")
    assert services.consultar_porcentaje_base() == "11.00"


def test_estados_del_historial_por_la_api(admin, reloj, dias, entrar):
    _a_las(reloj, dias(0))
    c = entrar("admin@inversioneslr.com", "Clave1234")
    r = c.post(f"{RUTA}/programadas", {"porcentaje": "15.00", "desde": dias(0).isoformat(), "hasta": dias(3).isoformat()},
               format="json")
    assert r.status_code == 201, r.content
    c.post(f"{RUTA}/programadas", {"porcentaje": "12.00", "desde": dias(10).isoformat(), "hasta": dias(12).isoformat()},
           format="json")
    datos = c.get(RUTA).json()
    assert datos["porcentaje"] == "15.00" and datos["base"] == "10.00"
    estados = {(t["porcentaje"], t["programada"]): t["estado"] for t in datos["historial"]}
    assert estados == {("15.00", True): "VIGENTE", ("12.00", True): "PROGRAMADA", ("10.00", False): "EN_ESPERA"}
    _a_las(reloj, dias(5))
    estados = {t["porcentaje"]: t["estado"] for t in c.get(RUTA).json()["historial"]}
    assert estados == {"15.00": "TERMINADA", "12.00": "PROGRAMADA", "10.00": "VIGENTE"}
    assert c.post(f"{RUTA}/programadas", {"porcentaje": "9.00", "desde": dias(11).isoformat(), "hasta": dias(20).isoformat()},
                  format="json").status_code == 409
