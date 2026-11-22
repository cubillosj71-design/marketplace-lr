"""MOD-09 Reportes (RF-D-ADM-05.1, 05.2 y su nota; ADR-009): HU-24 tablero, HU-25 reportes y HU-22 tarifa.

Las reservas pertenecen al periodo por su fecha de CREACIÓN. Para fijarla, las pruebas mueven el reloj de la
aplicación y reservan por los services reales (octubre de 2027, un mes sin datos de demostración)."""

import io
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.apps import apps
from django.core.management import call_command
from openpyxl import load_workbook

from apps.auditoria import services as auditoria
from apps.reportes import archivos
from apps.reservas import services as reservas

pytestmark = pytest.mark.django_db
OCTUBRE = {"desde": "2027-10-01", "hasta": "2027-10-31"}
TABLERO = "/api/v1/admin/tablero"


@pytest.fixture
def admin(demo, entrar):
    return entrar("admin@inversioneslr.com")


@pytest.fixture
def reservar_en(reloj):
    """reservar_en(pid, creada, llegada, noches=1) crea una reserva CONFIRMADA con fecha de creación fija."""
    huesped = apps.get_model("identidad", "Usuario").objects.get(correo="huesped@correo.com")

    def _reservar(pid, creada, llegada, noches=1, adicionales=()):
        reloj(creada)
        d = date.fromisoformat(llegada)
        cot = reservas.cotizar_estancia(huesped, pid, d, d + timedelta(days=noches), 2, adicionales)
        r, _ = reservas.reservar_alojamiento(huesped, cot.id, uuid.uuid4(), "simulado")
        return r["id"]

    _reservar.huesped = huesped
    return _reservar


def _cancelar(reloj, huesped, rid, dia, motivo="Cambio de planes"):
    reloj(dia)
    return reservas.cancelar_reserva(huesped, rid, motivo)


def _tablero(admin, periodo=OCTUBRE):
    r = admin.get(TABLERO, periodo)
    assert r.status_code == 200, r.content
    return r.json()


# ---------------- HU-24 Tablero (RF-D-ADM-05.1)
def test_ca_24_1_cantidades_por_estado_de_las_reservas_creadas_en_octubre(admin, publicar, reservar_en, reloj):
    pid = publicar("Para el tablero", precio=100000, limpieza=0)
    completadas = [reservar_en(pid, "2027-10-01", f"2027-10-{2 + 2 * i:02d}") for i in range(5)]
    canceladas = [reservar_en(pid, "2027-10-05", f"2027-11-{20 + 2 * i:02d}") for i in range(3)]
    confirmadas = [reservar_en(pid, "2027-10-10", f"2027-12-{1 + 2 * i:02d}") for i in range(12)]
    for rid in canceladas:
        _cancelar(reloj, reservar_en.huesped, rid, "2027-10-20")
    reloj("2027-11-01")
    reservas.completar_reservas_vencidas()  # (cancelar ya completa las vencidas; aquí no queda ninguna)
    assert apps.get_model("reservas", "Reserva").objects.filter(pk__in=completadas, estado="COMPLETADA").count() == 5
    t = _tablero(admin)
    assert t["reservas_por_estado"] == {"CONFIRMADA": 12, "EN_REVISION": 0, "COMPLETADA": 5, "CANCELADA": 3}
    assert t["reservas_total"] == 20 and len(completadas) + len(confirmadas) == 17


def test_ca_24_2_completadas_por_2_millones_con_180_mil_de_servicio(admin, publicar, reservar_en, reloj):
    # 1 noche de $900.000 + limpieza $10.000 + servicio 10 % ($90.000) = $1.000.000 por reserva
    pid = publicar("Lujo", precio=900000, limpieza=10000)
    reservar_en(pid, "2027-10-02", "2027-10-05")
    reservar_en(pid, "2027-10-03", "2027-10-08")
    reloj("2027-11-01")
    reservas.completar_reservas_vencidas()
    t = _tablero(admin)
    assert t["reservas_por_estado"]["COMPLETADA"] == 2
    assert t["ingresos"] == {"bruto": "2000000.00", "plataforma": "180000.00"}


def test_ca_24_3_la_ciudad_con_mas_reservas_aparece_primera(admin, publicar, reservar_en):
    cartagena = publicar("En Cartagena", ciudad="Cartagena")
    medellin = publicar("En Medellín", ciudad="Medellín")
    for i in range(3):
        reservar_en(cartagena, "2027-10-05", f"2027-11-{2 + 2 * i:02d}")
    reservar_en(medellin, "2027-10-06", "2027-11-02")
    top = _tablero(admin)["top_ciudades"]
    assert [(c["ciudad"], c["reservas"]) for c in top] == [("Cartagena", 3), ("Medellín", 1)]


def test_ca_24_4_cancelada_con_devolucion_parcial_suma_lo_retenido(admin, alojamiento_740, reservar_en, reloj):
    desayuno = apps.get_model("catalogo", "ServicioAdicional").objects.get(publicacion_id=alojamiento_740).id
    rid = reservar_en(alojamiento_740, "2027-10-01", "2027-10-20", noches=3, adicionales=[desayuno])
    r = apps.get_model("reservas", "Reserva").objects.select_related("cotizacion").get(pk=rid)
    assert (r.total, r.cotizacion.tarifa_servicio) == (Decimal("740000"), Decimal("60000"))
    _cancelar(reloj, reservar_en.huesped, rid, "2027-10-15")  # 5 días: devolución de $370.000
    t = _tablero(admin)
    assert t["reservas_por_estado"]["CANCELADA"] == 1
    assert t["ingresos"] == {"bruto": "370000.00", "plataforma": "30000.00"}


def test_la_reserva_cuenta_en_el_mes_en_que_se_creo_no_en_el_de_llegada(admin, publicar, reservar_en):
    pid = publicar("Lejana")
    reservar_en(pid, "2027-10-10", "2027-12-20")
    assert _tablero(admin)["reservas_total"] == 1
    assert _tablero(admin, {"desde": "2027-12-01", "hasta": "2027-12-31"})["reservas_total"] == 0


def test_en_revision_suma_al_bruto_y_a_la_plataforma(admin, publicar, reservar_en, entrar, reloj):
    pid = publicar("Para bloquear", precio=100000, limpieza=0)
    reservar_en(pid, "2027-10-01", "2027-12-01")
    reloj("2027-10-02")
    entrar("admin@inversioneslr.com").post(f"/api/v1/admin/publicaciones/{pid}/bloqueo", {"motivo": "Revisar"}, format="json")
    t = _tablero(admin)
    assert t["reservas_por_estado"]["EN_REVISION"] == 1
    assert t["ingresos"] == {"bruto": "110000.00", "plataforma": "10000.00"}


def test_tablero_usuarios_por_rol_y_publicaciones_activas(admin):
    t = _tablero(admin, {"desde": "2026-01-01", "hasta": "2026-12-31"})
    assert t["usuarios_por_rol"] == {"HUESPED": 1, "ANFITRION": 4, "ADMINISTRADOR": 1}
    assert t["publicaciones_activas"] == 5


@pytest.mark.parametrize("periodo,mensaje", [
    ({"desde": "2026-01-01", "hasta": "2027-01-01"}, "12 meses"),
    ({"desde": "2026-10-31", "hasta": "2026-10-01"}, "posterior"),
])
def test_periodo_invalido_responde_400(admin, periodo, mensaje):
    r = admin.get(TABLERO, periodo)
    assert r.status_code == 400 and mensaje in r.json()["detalle"]
    assert admin.get("/api/v1/admin/reportes/reservas", {**periodo, "formato": "pdf"}).status_code == 400


def test_solo_el_administrador(demo, entrar):
    for correo in ("huesped@correo.com", "anfitrion@correo.com"):
        c = entrar(correo)
        assert c.get(TABLERO).status_code == 403
        assert c.get("/api/v1/admin/reportes/usuarios").status_code == 403


# ---------------- HU-25 Reportes (RF-D-ADM-05.2)
def _excel(admin, tipo, periodo=OCTUBRE):
    r = admin.get(f"/api/v1/admin/reportes/{tipo}", {**periodo, "formato": "xlsx"})
    assert r.status_code == 200, r.content
    return load_workbook(io.BytesIO(r.content))


def test_ca_25_1_excel_de_reservas_de_octubre_coincide_con_el_tablero(admin, publicar, alojamiento_740, reservar_en, reloj):
    pid = publicar("Mezcla", precio=200000, limpieza=20000)
    reservar_en(pid, "2027-10-01", "2027-10-03")
    reservar_en(pid, "2027-10-02", "2027-12-01", noches=2)
    rid = reservar_en(alojamiento_740, "2027-10-04", "2027-10-20", noches=3)
    _cancelar(reloj, reservar_en.huesped, rid, "2027-10-15")
    reservar_en(pid, "2027-11-02", "2027-12-10")  # de noviembre: no entra
    reloj("2027-11-05")
    reservas.completar_reservas_vencidas()
    t = _tablero(admin)
    libro = _excel(admin, "reservas")
    filas = list(libro["Detalle"].iter_rows(min_row=archivos.FILA_CABECERA + 1, values_only=True))
    cabecera = [c.value for c in libro["Detalle"][archivos.FILA_CABECERA]]
    col = {nombre: i for i, nombre in enumerate(cabecera)}
    assert len(filas) == t["reservas_total"] == 3
    assert Decimal(str(sum(f[col["Monto bruto"]] for f in filas))) == Decimal(t["ingresos"]["bruto"])
    assert Decimal(str(sum(f[col["Ingreso plataforma"]] for f in filas))) == Decimal(t["ingresos"]["plataforma"])
    estados = {e: sum(1 for f in filas if f[col["Estado"]] == e) for e in t["reservas_por_estado"]}
    assert estados == t["reservas_por_estado"]
    resumen = dict(libro["Resumen"].iter_rows(min_row=7, values_only=True))
    assert resumen["Reservas creadas en el periodo"] == t["reservas_total"]
    # La serie por día de las gráficas suma lo mismo que las cifras del tablero
    assert sum(d["reservas"] for d in t["serie_diaria"]) == t["reservas_total"]
    assert sum(Decimal(d["monto_bruto"]) for d in t["serie_diaria"]) == Decimal(t["ingresos"]["bruto"])
    assert sum(Decimal(d["ingreso_plataforma"]) for d in t["serie_diaria"]) == Decimal(t["ingresos"]["plataforma"])
    assert [d["fecha"] for d in t["serie_diaria"]] == sorted(d["fecha"] for d in t["serie_diaria"])


def test_ingresos_y_demanda_cuadran_con_el_tablero(admin, publicar, reservar_en):
    cartagena = publicar("Ingresos Cartagena", ciudad="Cartagena", precio=100000, limpieza=0)
    reservar_en(cartagena, "2027-10-01", "2027-10-10")
    reservar_en(cartagena, "2027-10-02", "2027-10-20")
    t = _tablero(admin)
    resumen = dict(_excel(admin, "ingresos")["Resumen"].iter_rows(min_row=7, values_only=True))
    assert resumen["Monto bruto (COP)"] == "$220.000" and t["ingresos"]["bruto"] == "220000.00"
    assert resumen["Ingreso de la plataforma, tarifa de servicio (COP)"] == "$20.000"
    demanda = list(_excel(admin, "demanda")["Detalle"].iter_rows(min_row=archivos.FILA_CABECERA + 1, values_only=True))
    cartagena_filas = [f for f in demanda if f[1] == "Cartagena"]  # una fila por día, ciudad y tipo
    assert sum(f[3] for f in cartagena_filas) == 2 and sum(f[4] for f in cartagena_filas) == 220000
    assert t["top_ciudades"][0] == {"ciudad": "Cartagena", "reservas": 2, "monto_bruto": "220000.00"}


def test_ca_25_2_la_descarga_queda_registrada_con_administrador_reporte_formato_y_periodo(admin):
    admin.get("/api/v1/admin/reportes/usuarios", {**OCTUBRE, "formato": "pdf"})
    evento = auditoria.consultar_eventos(accion="ReporteDescargado").get()
    assert evento.actor_id == admin.usuario["id"] and evento.fecha
    assert (evento.detalle["tipo"], evento.detalle["formato"], evento.detalle["desde"], evento.detalle["hasta"]) == (
        "usuarios", "pdf", "2027-10-01", "2027-10-31")
    fila = admin.get("/api/v1/admin/auditoria", {"tipo": "descarga_reporte"}).json()["results"][0]
    assert fila["actor_nombre"] == "Admin LR" and fila["fecha"]


def test_ca_25_2_si_no_se_puede_registrar_no_se_entrega_el_archivo(admin, monkeypatch):
    from apps.reportes import services

    def fallar(*a, **kw):
        raise RuntimeError("auditoría no disponible")

    monkeypatch.setattr(services.auditoria, "registrar", fallar)
    r = admin.get("/api/v1/admin/reportes/usuarios", {**OCTUBRE, "formato": "pdf"})
    assert r.status_code == 500 and not r.content.startswith(b"%PDF")


@pytest.mark.parametrize("tipo,formato", [
    ("usuarios", "pdf"), ("publicaciones", "xlsx"), ("reservas", "pdf"), ("ingresos", "xlsx"), ("demanda", "pdf"),
])
def test_ca_25_3_cada_reporte_de_octubre_en_su_formato(admin, tipo, formato):
    """Con los datos de demostración de octubre de 2026 (usuarios, publicaciones y reservas creados ese mes)."""
    octubre_2026 = {"desde": "2026-10-01", "hasta": "2026-10-31"}
    r = admin.get(f"/api/v1/admin/reportes/{tipo}", {**octubre_2026, "formato": formato})
    assert r.status_code == 200
    assert r.content[:4] == (b"%PDF" if formato == "pdf" else b"PK\x03\x04")
    assert f'filename="reporte-{tipo}_2026-10-01_2026-10-31.{formato}"' in r["Content-Disposition"]
    registrados = auditoria.consultar_eventos(accion="ReporteDescargado").get().detalle["registros"]
    # Demanda: una fila por día, ciudad y tipo (RF-D-ADM-05.2, ordenada por fecha): las 4 reservas de octubre de la
    # demo se crearon en 4 días distintos
    esperados = {"usuarios": 1, "publicaciones": 3, "reservas": 4, "ingresos": 1, "demanda": 4}
    assert registrados == esperados[tipo]  # datos de octubre de ese reporte


def test_reporte_de_usuarios_filtra_por_estado_derivado_de_la_cuenta(admin):
    libro = _excel(admin, "usuarios", {"desde": "2026-01-01", "hasta": "2026-12-31", "estado": "RESTRINGIDA"})
    filas = list(libro["Detalle"].iter_rows(min_row=archivos.FILA_CABECERA + 1, values_only=True))
    assert [(f[2], f[4], f[6]) for f in filas] == [("restringido@correo.com", "Bogotá", "Restringida")]


def test_reporte_de_publicaciones_filtra_por_ciudad_y_estado(admin):
    libro = _excel(admin, "publicaciones", {"desde": "2026-01-01", "hasta": "2026-12-31", "ciudad": "bogotá", "estado": "ACTIVA"})
    titulos = {f[1] for f in libro["Detalle"].iter_rows(min_row=archivos.FILA_CABECERA + 1, values_only=True)}
    assert titulos == {"Apartamento con vista a Monserrate"}


def test_tipo_invalido(admin):
    assert admin.get("/api/v1/admin/reportes/otro").status_code == 404


def test_la_demo_trae_todos_los_estados_en_octubre_y_noviembre_de_2026(reloj, db, entrar):
    reloj("2026-11-18")  # demo determinista: "hoy" es el 18 de noviembre de 2026
    call_command("cargar_demo", verbosity=0)
    t = _tablero(entrar("admin@inversioneslr.com"), {"desde": "2026-10-01", "hasta": "2026-11-30"})
    assert t["reservas_por_estado"] == {"CONFIRMADA": 3, "EN_REVISION": 1, "COMPLETADA": 2, "CANCELADA": 1}
    cancelacion = apps.get_model("reservas", "Cancelacion").objects.get()
    assert 0 < cancelacion.porcentaje_devolucion < 100  # devolución parcial
    assert t["top_ciudades"][0]["ciudad"] == "Bogotá"


# ---------------- HU-22 Tarifa de servicio
def test_ca_22_1_el_12_solo_aplica_a_cotizaciones_nuevas(admin, publicar, reservar_en, entrar):
    pid = publicar("Tarifa", precio=100000, limpieza=0)
    rid = reservar_en(pid, "2027-10-01", "2027-11-01")
    antes = apps.get_model("reservas", "Reserva").objects.select_related("cotizacion").get(pk=rid)
    assert admin.put("/api/v1/admin/tarifa-servicio", {"porcentaje": "12"}, format="json").status_code == 200
    t = admin.get("/api/v1/admin/tarifa-servicio").json()
    assert t["porcentaje"] == "12.00" and len(t["historial"]) == 2
    nueva = entrar("huesped@correo.com").post("/api/v1/reservas/cotizaciones", {
        "publicacion": pid, "fecha_llegada": "2027-11-10", "fecha_salida": "2027-11-11", "num_huespedes": 2}, format="json").json()
    assert (nueva["porcentaje_servicio"], nueva["tarifa_servicio"]) == ("12.00", "12000.00")
    despues = apps.get_model("reservas", "Reserva").objects.select_related("cotizacion").get(pk=rid)
    assert (despues.total, despues.cotizacion.tarifa_servicio) == (antes.total, antes.cotizacion.tarifa_servicio) == (Decimal("110000"), Decimal("10000"))


def test_ca_22_2_el_35_no_se_acepta_e_indica_el_rango(admin):
    r = admin.put("/api/v1/admin/tarifa-servicio", {"porcentaje": "35"}, format="json")
    assert r.status_code == 400 and "0 % y 30 %" in r.json()["detalle"]
    assert admin.get("/api/v1/admin/tarifa-servicio").json()["porcentaje"] == "10.00"
