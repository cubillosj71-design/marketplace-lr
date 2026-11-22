"""SRV-01 Identidad: sesión con cookie httpOnly (C4 nivel 2), enlace en pantalla (AMB-08),
límite de intentos y los criterios de aceptación que faltaban (CA-01.1, CA-02.1, CA-03.1,
CA-04.1, CA-04.3)."""

import pytest
from django.test import override_settings

from apps.identidad import services

pytestmark = pytest.mark.django_db
TOKEN = "/api/v1/identidad/token"
RENOVAR = "/api/v1/identidad/token/renovar"
SALIR = "/api/v1/identidad/salir"
PERFIL = "/api/v1/identidad/perfil"
RECUPERACION = "/api/v1/identidad/recuperacion"
NUEVO = {"nombre_completo": "Marta Ríos", "correo": "marta@correo.com", "telefono": "300 111 2233",
         "password": "Segura2026", "rol": "HUESPED", "acepta_datos": True}


# ---------------- HU-01
def test_ca_01_1_registro_valido_deja_la_cuenta_activa_y_lista_para_entrar(cliente, entrar):
    r = cliente.post("/api/v1/identidad/registro", NUEVO, format="json")
    assert r.status_code == 201 and r.json()["rol"] == "HUESPED"
    assert r.json()["activa"] is True and r.json()["restringida"] is False
    assert entrar("marta@correo.com", "Segura2026").usuario["correo"] == "marta@correo.com"


# ---------------- HU-02 y ADR-005
def test_ca_02_1_el_refresh_va_en_cookie_httponly_y_no_en_el_cuerpo(demo, cliente):
    r = cliente.post(TOKEN, {"correo": "huesped@correo.com", "password": "Clave1234"}, format="json")
    assert r.status_code == 200 and "access" in r.json() and "refresh" not in r.json()
    cookie = r.cookies["renovacion"]
    assert cookie["httponly"] and cookie["samesite"] == "Strict" and cookie["path"] == "/api/v1/identidad/"


def test_renovar_con_la_cookie_recupera_la_sesion(demo, entrar):
    c = entrar("huesped@correo.com")
    c.credentials()  # como al recargar la página: sin access en memoria
    r = c.post(RENOVAR)
    assert r.status_code == 200 and r.json()["usuario"]["correo"] == "huesped@correo.com"


def test_un_refresh_ya_rotado_no_sirve_otra_vez(demo, entrar):
    c = entrar("huesped@correo.com")
    viejo = c.refresh
    assert c.post(RENOVAR).status_code == 200
    c.cookies["renovacion"] = viejo
    assert c.post(RENOVAR).status_code == 401


def test_sin_cookie_no_hay_renovacion(cliente):
    assert cliente.post(RENOVAR).status_code == 401


def test_salir_con_la_cookie_cierra_la_sesion_aunque_el_access_haya_vencido(demo, entrar):
    c = entrar("huesped@correo.com")
    viejo = c.refresh
    c.credentials()
    assert c.post(SALIR).status_code == 204
    c.cookies["renovacion"] = viejo
    assert c.post(RENOVAR).status_code == 401


def test_una_cuenta_restringida_no_renueva_su_sesion(demo, entrar):
    sofia = entrar("sofia@correo.com")
    admin = entrar("admin@inversioneslr.com")
    admin.post(f"/api/v1/admin/usuarios/{sofia.usuario['id']}/restriccion", {"motivo": "Prueba"}, format="json")
    assert sofia.post(RENOVAR).status_code == 401


def test_mas_de_10_intentos_por_minuto_desde_la_misma_ip_se_frenan(demo, cliente):
    for _ in range(10):
        cliente.post(TOKEN, {"correo": "huesped@correo.com", "password": "adivinando"}, format="json")
    assert cliente.post(TOKEN, {"correo": "huesped@correo.com", "password": "Clave1234"}, format="json").status_code == 429


# ---------------- HU-03
@override_settings(DEBUG=False)
def test_ca_03_1_el_enlace_se_muestra_en_pantalla_tambien_en_produccion(demo, cliente):
    r = cliente.post(RECUPERACION, {"correo": "huesped@correo.com"}, format="json")
    assert r.status_code == 202 and "/#/restablecer/" in r.json()["enlace"]


def test_pedir_un_enlace_nuevo_anula_el_anterior(demo):
    primero = services.solicitar_recuperacion("huesped@correo.com")
    segundo = services.solicitar_recuperacion("huesped@correo.com")
    assert services.consultar_estado_enlace(primero) == "vencido"
    assert services.consultar_estado_enlace(segundo) == "valido"


def test_abrir_y_usar_el_enlace_no_choca_con_el_limite_de_solicitudes(demo, cliente):
    token = services.solicitar_recuperacion("huesped@correo.com")
    for _ in range(6):
        assert cliente.get(f"{RECUPERACION}/{token}").json()["estado"] == "valido"
    assert cliente.post(f"{RECUPERACION}/{token}", {"password": "NuevaClave2026"}, format="json").status_code == 200


# ---------------- HU-04
def test_ca_04_1_cambiar_telefono_y_ciudad_muestra_los_datos_nuevos(demo, entrar):
    c = entrar("huesped@correo.com")
    assert c.patch(PERFIL, {"telefono": "301 999 8877", "ciudad": "Cartagena"}, format="json").status_code == 200
    perfil = c.get(PERFIL).json()
    assert perfil["telefono"] == "301 999 8877" and perfil["ciudad"] == "Cartagena"
    # "Sin ciudad": la ciudad es opcional
    c.patch(PERFIL, {"ciudad": None}, format="json")
    assert c.get(PERFIL).json()["ciudad"] is None


def test_el_perfil_devuelve_los_campos_del_modelo_relacional(demo, entrar):
    perfil = entrar("huesped@correo.com").get(PERFIL).json()
    assert set(perfil) == {"id", "correo", "nombre_completo", "telefono", "ciudad", "rol", "activa", "restringida",
                           "autorizacion_datos", "fecha_registro"}


def test_ca_04_3_un_anfitrion_desactivado_sale_de_las_cuentas_visibles(demo, entrar):
    c = entrar("pedro@correo.com")
    pedro = c.usuario["id"]
    assert services.listar_cuentas_activas([pedro]) == {pedro}
    assert c.post("/api/v1/identidad/perfil/desactivar").status_code == 200
    assert services.listar_cuentas_activas([pedro]) == set()  # Búsqueda oculta sus publicaciones


def test_ip_toma_el_valor_que_agrega_el_proxy():
    from apps.comun.eventos import ip_de

    peticion = type("P", (), {"META": {"HTTP_X_FORWARDED_FOR": "1.1.1.1, 200.1.2.3", "REMOTE_ADDR": "10.0.0.2"}})()
    assert ip_de(peticion) == "200.1.2.3"
