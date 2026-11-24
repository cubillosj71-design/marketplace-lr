"""HU-09 Calendario (RF-D-ALO-02.2). PeriodoCalendario es de MOD-04 Reservas; la ruta se conserva
en /catalogo/publicaciones/{id}/calendario para el frontend."""

from datetime import timedelta

import pytest
from django.apps import apps
from django.utils import timezone

from apps.comun.fechas import calcular_fecha_maxima

pytestmark = pytest.mark.django_db


def _url(titulo="Apartamento con vista a Monserrate"):
    pid = apps.get_model("catalogo", "Publicacion").objects.get(titulo=titulo).id
    return f"/api/v1/catalogo/publicaciones/{pid}/calendario"


def test_ca_09_calendario_por_rangos(demo, entrar):
    c = entrar("anfitrion@correo.com")
    url = _url()
    r = c.post(url, {"fecha_inicio": "2026-12-15", "fecha_fin": "2026-12-18", "tipo": "NO_DISPONIBLE"}, format="json")
    assert r.status_code == 200  # CA-09.1: se une con el periodo del 12 al 15
    todos = c.get(url, {"desde": "2026-12-01", "hasta": "2027-01-01"}).json()
    assert todos["periodos"] == [{"fecha_inicio": "2026-12-12", "fecha_fin": "2026-12-18", "disponible": False, "tipo": "NO_DISPONIBLE"}]
    assert "2026-12-05" in todos["noches_reservadas"] and "2026-12-09" not in todos["noches_reservadas"]
    r = c.post(url, {"fecha_inicio": "2026-12-08", "fecha_fin": "2026-12-10", "tipo": "NO_DISPONIBLE"}, format="json")
    assert r.status_code == 409 and r.json()["fechas"] == ["2026-12-08"]  # CA-09.2
    c.post(url, {"fecha_inicio": "2026-12-14", "fecha_fin": "2026-12-16", "tipo": "DISPONIBLE"}, format="json")
    todos = c.get(url, {"desde": "2026-12-01", "hasta": "2027-01-01"}).json()["periodos"]
    assert [(p["fecha_inicio"], p["fecha_fin"]) for p in todos] == [("2026-12-12", "2026-12-14"), ("2026-12-16", "2026-12-18")]


def test_el_periodo_se_guarda_con_disponible_false(demo):
    Periodo = apps.get_model("reservas", "PeriodoCalendario")
    p = Periodo.objects.get()
    assert p.disponible is False and p.es_fecha_del_periodo(p.fecha_inicio) and not p.es_fecha_del_periodo(p.fecha_fin)


def test_calendario_solo_del_dueno(demo, entrar):
    assert entrar("admin@inversioneslr.com").get(_url()).status_code == 403
    assert entrar("sofia@correo.com").get(_url()).status_code == 403


def test_limite_de_12_meses_en_el_calendario(demo, entrar):
    c = entrar("anfitrion@correo.com")
    limite = calcular_fecha_maxima()
    r = c.post(_url(), {"fecha_inicio": (limite - timedelta(days=2)).isoformat(), "fecha_fin": (limite + timedelta(days=1)).isoformat(),
                        "tipo": "NO_DISPONIBLE"}, format="json")
    assert r.status_code == 400 and r.json()["campo"] == "fecha_fin"
    r = c.post(_url(), {"fecha_inicio": (limite - timedelta(days=2)).isoformat(), "fecha_fin": limite.isoformat(),
                        "tipo": "NO_DISPONIBLE"}, format="json")
    assert r.status_code == 200
    assert timezone.localdate() < limite
