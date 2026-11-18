"""SRV-02 Catálogo: HU-06 a HU-09, RF-D-ADM-01.1 y 01.2."""

from datetime import date

import pytest
from django.apps import apps
from django.db import IntegrityError, transaction

pytestmark = pytest.mark.django_db
BASE = "/api/v1/catalogo"


def _id(titulo):
    return apps.get_model("catalogo", "Publicacion").objects.get(titulo=titulo).id


@pytest.fixture
def completa(cliente):
    cat = {k: cliente.get(f"{BASE}/{k}").json() for k in ("ciudades", "tipos-alojamiento", "servicios")}
    politica = apps.get_model("catalogo", "PoliticaCancelacion").objects.get(nombre="Moderada").id
    return {
        "titulo": "Apartamento Prueba", "descripcion": "Completo.", "ciudad": cat["ciudades"][0]["id"],
        "tipo_alojamiento": cat["tipos-alojamiento"][0]["id"], "politica": politica, "ubicacion_textual": "Centro",
        "capacidad": 3, "precio_noche": "200000", "tarifa_limpieza": "50000", "servicios": [cat["servicios"][0]["id"]],
        "servicios_adicionales": [{"nombre": "Desayuno", "precio": "30000"}], "reglas": ["No fumar", "", "Sin fiestas"],
        "imagenes": ["https://placehold.co/600x400"],
    }


def test_catalogos_son_publicos(cliente):
    assert len(cliente.get(f"{BASE}/ciudades").json()) == 9
    assert {t["nombre"] for t in cliente.get(f"{BASE}/tipos-alojamiento").json()} == {"Apartamento", "Casa", "Habitación", "Cabaña"}


# ---------------- HU-06 Crear · HU-07 Enviar a revisión
def test_crear_borrador_y_enviar_a_revision(demo, entrar, completa):
    c = entrar("pedro@correo.com")
    r = c.post(f"{BASE}/publicaciones", {"titulo": "Solo título"}, format="json")
    assert r.status_code == 201 and r.json()["estado"] == "BORRADOR" and r.json()["faltantes"]
    pid = r.json()["id"]
    r = c.post(f"{BASE}/publicaciones/{pid}/enviar-revision")
    assert r.status_code == 400 and "precio por noche" in r.json()["faltantes"]  # CA-07.2
    r = c.patch(f"{BASE}/publicaciones/{pid}", completa, format="json")
    assert [x["descripcion"] for x in r.json()["reglas"]] == ["No fumar", "Sin fiestas"]  # ReglaAlojamiento con orden
    assert c.post(f"{BASE}/publicaciones/{pid}/enviar-revision").json()["estado"] == "PENDIENTE_REVISION"  # CA-07.1


def test_ca_06_2_capacidad_y_precio_mayores_que_cero(demo, entrar, completa):
    c = entrar("pedro@correo.com")
    assert c.post(f"{BASE}/publicaciones", {**completa, "capacidad": 0}, format="json").json()["campo"] == "capacidad"
    assert c.post(f"{BASE}/publicaciones", {**completa, "precio_noche": "0"}, format="json").json()["campo"] == "precio_noche"


def test_descuento_completo_o_vacio(demo, entrar, completa):
    c = entrar("pedro@correo.com")
    assert c.post(f"{BASE}/publicaciones", {**completa, "descuento_porcentaje": "10"}, format="json").status_code == 400


def test_la_base_exige_publicacion_completa_fuera_de_borrador(demo):
    p = apps.get_model("catalogo", "Publicacion").objects.get(titulo="Casa familiar en Villa de Leyva")
    p.estado, p.descripcion = "ACTIVA", ""
    with pytest.raises(IntegrityError), transaction.atomic():
        p.save()


# ---------------- HU-05 Permisos
def test_ca_05_1_el_huesped_no_crea_publicaciones(demo, entrar, completa):
    assert entrar("huesped@correo.com").post(f"{BASE}/publicaciones", completa, format="json").status_code == 403


def test_ca_05_3_solo_el_dueno_o_el_admin_modifican(demo, entrar):
    pid = _id("Cabaña del Lago")
    assert entrar("pedro@correo.com").patch(f"{BASE}/publicaciones/{pid}", {"titulo": "Mía"}, format="json").status_code == 403
    assert entrar("admin@inversioneslr.com").patch(f"{BASE}/publicaciones/{pid}", {"titulo": "Cabaña del Lago editada"}, format="json").status_code == 200


def test_editar_activa_no_vuelve_a_revision(demo, entrar):
    pid = _id("Cabaña del Lago")
    r = entrar("sofia@correo.com").patch(f"{BASE}/publicaciones/{pid}", {"precio_noche": "300000"}, format="json")
    assert r.json()["estado"] == "ACTIVA"


def test_mis_publicaciones_solo_las_propias(demo, entrar):
    titulos = {p["titulo"] for p in entrar("sofia@correo.com").get(f"{BASE}/mis-publicaciones").json()["results"]}
    assert titulos == {"Cabaña del Lago", "Casa campestre La Ceja", "Habitación Laureles"}


# ---------------- HU-08 Pausar y reactivar
def test_ca_08_pausar_y_reactivar_sin_tocar_reservas(demo, entrar):
    from apps.reservas import services as reservas

    pid = _id("Apartamento con vista a Monserrate")
    c = entrar("anfitrion@correo.com")
    assert c.post(f"{BASE}/publicaciones/{pid}/pausar").json()["estado"] == "PAUSADA"
    assert len(reservas.confirmadas_pendientes(c.usuario["id"], True)) == 2  # CA-08.4
    assert c.post(f"{BASE}/publicaciones/{pid}/reactivar").json()["estado"] == "ACTIVA"
    assert c.post(f"{BASE}/publicaciones/{_id('Habitación cerca al centro')}/pausar").status_code == 409


# ---------------- HU-09 Calendario (PeriodoCalendario)
def test_ca_09_calendario_por_rangos(demo, entrar):
    pid = _id("Apartamento con vista a Monserrate")
    c = entrar("anfitrion@correo.com")
    url = f"{BASE}/publicaciones/{pid}/calendario"
    r = c.post(url, {"fecha_inicio": "2026-12-15", "fecha_fin": "2026-12-18", "tipo": "NO_DISPONIBLE"}, format="json")
    assert r.status_code == 200  # CA-09.1: se une con el periodo del 12 al 15
    todos = c.get(url, {"desde": "2026-12-01", "hasta": "2027-01-01"}).json()
    assert todos["periodos"] == [{"fecha_inicio": "2026-12-12", "fecha_fin": "2026-12-18", "tipo": "NO_DISPONIBLE"}]
    assert "2026-12-05" in todos["noches_reservadas"] and "2026-12-09" not in todos["noches_reservadas"]
    r = c.post(url, {"fecha_inicio": "2026-12-08", "fecha_fin": "2026-12-10", "tipo": "NO_DISPONIBLE"}, format="json")
    assert r.status_code == 409 and r.json()["fechas"] == ["2026-12-08"]  # CA-09.2
    c.post(url, {"fecha_inicio": "2026-12-14", "fecha_fin": "2026-12-16", "tipo": "DISPONIBLE"}, format="json")
    todos = c.get(url, {"desde": "2026-12-01", "hasta": "2027-01-01"}).json()["periodos"]
    assert [(p["fecha_inicio"], p["fecha_fin"]) for p in todos] == [("2026-12-12", "2026-12-14"), ("2026-12-16", "2026-12-18")]


def test_calendario_solo_del_dueno(demo, entrar):
    pid = _id("Apartamento con vista a Monserrate")
    assert entrar("admin@inversioneslr.com").get(f"{BASE}/publicaciones/{pid}/calendario").status_code == 403
    assert entrar("sofia@correo.com").get(f"{BASE}/publicaciones/{pid}/calendario").status_code == 403


# ---------------- RF-D-ADM-01 Moderación
def test_aprobar_y_devolver_quedan_en_el_historial(demo, entrar):
    admin = entrar("admin@inversioneslr.com")
    pid = _id("Estudio Usaquén")
    r = admin.post(f"/api/v1/admin/publicaciones/{pid}/revision", {"accion": "DEVOLVER"}, format="json")
    assert r.status_code == 400 and r.json()["campo"] == "observacion"
    r = admin.post(f"/api/v1/admin/publicaciones/{pid}/revision", {"accion": "DEVOLVER", "observacion": "Faltan fotos"}, format="json")
    assert r.json()["estado"] == "BORRADOR" and r.json()["revisiones"][0]["observacion"] == "Faltan fotos"
    pid = _id("Habitación cerca al centro")
    r = admin.post(f"/api/v1/admin/publicaciones/{pid}/revision", {"accion": "APROBAR"}, format="json")
    assert r.json()["estado"] == "ACTIVA" and r.json()["revisiones"][0]["accion"] == "APROBAR"


def test_admin_lista_sin_borradores(demo, entrar):
    estados = {p["estado"] for p in entrar("admin@inversioneslr.com").get("/api/v1/admin/publicaciones").json()["results"]}
    assert "BORRADOR" not in estados


@pytest.mark.django_db(transaction=True)
def test_bloquear_pasa_reservas_futuras_a_en_revision(demo, entrar, eventos):
    from apps.reservas import services as reservas

    admin = entrar("admin@inversioneslr.com")
    pid = _id("Apartamento con vista a Monserrate")
    assert admin.post(f"/api/v1/admin/publicaciones/{pid}/bloqueo", {"motivo": ""}, format="json").status_code == 400
    assert admin.post(f"/api/v1/admin/publicaciones/{pid}/bloqueo", {"motivo": "Fraude"}, format="json").json()["estado"] == "BLOQUEADA"
    estados = {r["estado"] for r in reservas.reservas_para_reporte(publicaciones_ids=[pid]) if r["fecha_llegada"] >= date.today()}
    assert estados == {"EN_REVISION"}
    assert "ReservaEnRevision" in eventos()
    assert admin.delete(f"/api/v1/admin/publicaciones/{pid}/bloqueo").json()["estado"] == "PAUSADA"


@pytest.mark.django_db(transaction=True)
def test_ca_05_2_intento_ajeno_queda_registrado(demo, entrar, eventos):
    entrar("pedro@correo.com").patch(f"{BASE}/publicaciones/{_id('Cabaña del Lago')}", {"titulo": "x"}, format="json")
    entrar("huesped@correo.com").get("/api/v1/admin/tablero")
    assert eventos(accion="AccesoDenegado", resultado="FALLO").count("AccesoDenegado") >= 2
