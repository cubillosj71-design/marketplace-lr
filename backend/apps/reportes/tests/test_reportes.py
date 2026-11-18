"""SRV-09 Reportes (ADR-009): tablero y archivos con las mismas cifras; HU-22 tarifa; HU-23 auditoría."""

import io

import pytest
from django.db import connection
from openpyxl import load_workbook

pytestmark = pytest.mark.django_db
PERIODO = {"desde": "2026-01-01", "hasta": "2026-12-31"}


def test_tablero(demo, entrar):
    t = entrar("admin@inversioneslr.com").get("/api/v1/admin/tablero", PERIODO).json()
    assert t["usuarios_por_rol"] == {"HUESPED": 1, "ANFITRION": 4, "ADMINISTRADOR": 1}
    assert t["publicaciones_activas"] == 5
    assert t["reservas_por_estado"]["CONFIRMADA"] == 3
    assert t["ingresos"] == {"bruto": "2470000.00", "plataforma": "210000.00"}
    assert t["top_ciudades"][0]["ciudad"] == "Bogotá"


def test_solo_el_administrador(demo, entrar):
    for correo in ("huesped@correo.com", "anfitrion@correo.com"):
        c = entrar(correo)
        assert c.get("/api/v1/admin/tablero").status_code == 403
        assert c.get("/api/v1/admin/reportes/usuarios").status_code == 403


def test_ca_25_3_usuarios_en_pdf(demo, entrar):
    r = entrar("admin@inversioneslr.com").get("/api/v1/admin/reportes/usuarios", {**PERIODO, "formato": "pdf"})
    assert r.status_code == 200 and r.content[:5] == b"%PDF-"
    assert 'filename="reporte-usuarios_2026-01-01_2026-12-31.pdf"' in r["Content-Disposition"]


def test_ca_25_1_publicaciones_en_excel_cuadra_con_el_tablero(demo, entrar):
    admin = entrar("admin@inversioneslr.com")
    r = admin.get("/api/v1/admin/reportes/publicaciones", {**PERIODO, "formato": "xlsx"})
    libro = load_workbook(io.BytesIO(r.content))
    filas = list(libro["Detalle"].iter_rows(min_row=2, values_only=True))
    assert len(filas) == 9  # sin el borrador
    activas_excel = sum(1 for f in filas if f[6] == "Activa")
    assert activas_excel == admin.get("/api/v1/admin/tablero", PERIODO).json()["publicaciones_activas"]
    assert libro["Detalle"]["F2"].number_format == '"$"#,##0'  # pesos como número


@pytest.mark.parametrize("tipo", ["reservas", "ingresos", "demanda"])
@pytest.mark.parametrize("formato", ["pdf", "xlsx"])
def test_los_cinco_reportes(demo, entrar, tipo, formato):
    r = entrar("admin@inversioneslr.com").get(f"/api/v1/admin/reportes/{tipo}", {**PERIODO, "formato": formato})
    assert r.status_code == 200 and r.content[:2] in (b"%P", b"PK")


def test_ingresos_de_la_plataforma(demo, entrar):
    r = entrar("admin@inversioneslr.com").get("/api/v1/admin/reportes/ingresos", {**PERIODO, "formato": "xlsx"})
    resumen = {k: v for k, v in load_workbook(io.BytesIO(r.content))["Resumen"].iter_rows(min_row=6, values_only=True)}
    assert resumen["Ingreso de la plataforma, tarifa de servicio (COP)"] == "$210.000"


def test_periodo_maximo_12_meses(demo, entrar):
    r = entrar("admin@inversioneslr.com").get("/api/v1/admin/reportes/usuarios", {"desde": "2025-01-01", "hasta": "2026-12-31"})
    assert r.status_code == 400 and "12 meses" in r.json()["detalle"]


def test_tipo_invalido(demo, entrar):
    assert entrar("admin@inversioneslr.com").get("/api/v1/admin/reportes/otro").status_code == 404


@pytest.mark.django_db(transaction=True)
def test_ca_25_2_cada_descarga_queda_en_la_auditoria(demo, entrar):
    admin = entrar("admin@inversioneslr.com")
    admin.get("/api/v1/admin/reportes/usuarios", {**PERIODO, "formato": "pdf"})
    r = admin.get("/api/v1/admin/auditoria", {"accion": "ReporteDescargado"}).json()["results"]
    assert r[0]["usuario_id"] == admin.usuario["id"] and r[0]["detalle"]["tipo"] == "usuarios" and r[0]["fecha"]


# ---------------- HU-22 Tarifa de servicio
def test_ca_22_1_tarifa_nueva_no_cambia_reservas_confirmadas(demo, entrar):
    admin = entrar("admin@inversioneslr.com")
    assert admin.put("/api/v1/admin/tarifa-servicio", {"porcentaje": "35"}, format="json").status_code == 400
    assert admin.put("/api/v1/admin/tarifa-servicio", {"porcentaje": "12"}, format="json").status_code == 200
    t = admin.get("/api/v1/admin/tarifa-servicio").json()
    assert t["porcentaje"] == "12.00" and len(t["historial"]) == 2
    assert admin.get("/api/v1/admin/tablero", PERIODO).json()["ingresos"]["plataforma"] == "210000.00"


# ---------------- HU-23 Auditoría de solo inserción
@pytest.mark.django_db(transaction=True)
def test_la_auditoria_no_se_modifica_ni_se_borra(demo, entrar):
    from django.db import DatabaseError

    entrar("admin@inversioneslr.com")
    for sql in ("UPDATE evento_auditoria SET accion = 'x'", "DELETE FROM evento_auditoria"):
        with pytest.raises(DatabaseError, match="solo inserción"), connection.cursor() as c:
            c.execute(sql)
