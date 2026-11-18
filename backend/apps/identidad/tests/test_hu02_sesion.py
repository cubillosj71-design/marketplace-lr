"""HU-02 Iniciar sesión (MAL-2) - RF-D-USU-01.2, CU-USU-02, ADR-005."""

import pytest

from apps.auditoria import services as auditoria
from apps.identidad import services

from .conftest import CLAVE

TOKEN = "/api/v1/identidad/token"
RENOVAR = "/api/v1/identidad/token/renovar"
SALIR = "/api/v1/identidad/salir"
PERFIL = "/api/v1/identidad/perfil"


@pytest.mark.django_db
def test_ca_02_1_credenciales_correctas_abren_sesion_con_las_funciones_del_rol(cliente, crear_usuario):
    crear_usuario()

    respuesta = cliente.post(TOKEN, {"correo": "ana@correo.com", "password": CLAVE}, format="json")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["usuario"]["rol"] == "HUESPED"
    assert "access" in cuerpo
    # El token de renovación NO va en el cuerpo: va en una cookie httpOnly.
    assert "refresh" not in cuerpo
    cookie = respuesta.cookies["renovacion"]
    assert cookie["httponly"]
    assert cookie["samesite"] == "Strict"
    assert cookie["path"] == "/api/v1/identidad/"

    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {cuerpo['access']}")
    assert cliente.get(PERFIL).status_code == 200


@pytest.mark.django_db
def test_ca_02_2_contrasena_incorrecta_rechaza_el_ingreso_y_registra_el_intento(cliente, crear_usuario):
    usuario = crear_usuario()

    respuesta = cliente.post(TOKEN, {"correo": "ana@correo.com", "password": "otra-clave"}, format="json")

    assert respuesta.status_code == 401
    assert respuesta.json()["codigo"] == "credenciales_invalidas"
    [evento] = auditoria.consultar(accion="INICIO_SESION")
    assert evento["exitoso"] is False
    assert evento["actor_id"] == usuario.pk  # así el administrador puede filtrar por usuario (CA-23.1)


@pytest.mark.django_db
def test_ca_02_2_correo_inexistente_da_el_mismo_mensaje_que_la_contrasena_incorrecta(cliente, crear_usuario):
    crear_usuario()
    malo_clave = cliente.post(TOKEN, {"correo": "ana@correo.com", "password": "otra-clave"}, format="json").json()
    malo_correo = cliente.post(TOKEN, {"correo": "nadie@correo.com", "password": "otra-clave"}, format="json").json()
    assert malo_clave == malo_correo
    assert len(auditoria.consultar(accion="INICIO_SESION", exitoso=False)) == 2


@pytest.mark.django_db
def test_ca_02_3_cuenta_restringida_con_datos_correctos_rechaza_e_informa(cliente, crear_usuario):
    crear_usuario(estado="RESTRINGIDA")

    respuesta = cliente.post(TOKEN, {"correo": "ana@correo.com", "password": CLAVE}, format="json")

    assert respuesta.status_code == 403
    assert respuesta.json()["codigo"] == "cuenta_restringida"
    assert "restringida" in respuesta.json()["mensaje"]


@pytest.mark.django_db
def test_flujo_4c_cuenta_desactivada_se_reactiva_al_iniciar_sesion(cliente, crear_usuario):
    usuario = crear_usuario(estado="DESACTIVADA")

    respuesta = cliente.post(TOKEN, {"correo": "ana@correo.com", "password": CLAVE}, format="json")

    assert respuesta.status_code == 200
    usuario.refresh_from_db()
    assert usuario.estado == "ACTIVA"
    assert auditoria.consultar(accion="REACTIVACION", actor_id=usuario.pk)


@pytest.mark.django_db
def test_el_ingreso_exitoso_queda_registrado(cliente, crear_usuario, iniciar_sesion):
    usuario = crear_usuario()
    iniciar_sesion()
    assert auditoria.consultar(accion="INICIO_SESION", exitoso=True, actor_id=usuario.pk)
    usuario.refresh_from_db()
    assert usuario.last_login is not None


@pytest.mark.django_db
def test_renovar_con_la_cookie_entrega_un_token_de_acceso_nuevo(cliente, crear_usuario, iniciar_sesion):
    crear_usuario()
    iniciar_sesion()

    respuesta = cliente.post(RENOVAR)

    assert respuesta.status_code == 200
    assert respuesta.json()["usuario"]["correo"] == "ana@correo.com"
    assert "access" in respuesta.json()


@pytest.mark.django_db
def test_un_token_de_renovacion_ya_usado_no_sirve_otra_vez(cliente, crear_usuario, iniciar_sesion):
    crear_usuario()
    viejo = iniciar_sesion().cookies["renovacion"].value
    assert cliente.post(RENOVAR).status_code == 200  # rota la cookie

    cliente.cookies["renovacion"] = viejo
    assert cliente.post(RENOVAR).status_code == 401


@pytest.mark.django_db
def test_sin_cookie_no_se_puede_renovar(cliente):
    assert cliente.post(RENOVAR).status_code == 401


@pytest.mark.django_db
def test_cerrar_sesion_invalida_la_renovacion(cliente, crear_usuario, iniciar_sesion):
    crear_usuario()
    cookie = iniciar_sesion().cookies["renovacion"].value

    assert cliente.post(SALIR).status_code == 204

    cliente.cookies["renovacion"] = cookie
    assert cliente.post(RENOVAR).status_code == 401
    assert auditoria.consultar(accion="CIERRE_SESION")


@pytest.mark.django_db
def test_adr_005_una_cuenta_restringida_pierde_el_acceso_de_inmediato(cliente, crear_usuario, iniciar_sesion):
    """Aunque su token de acceso no haya vencido, la petición siguiente se rechaza."""
    usuario = crear_usuario()
    administrador = crear_usuario(correo="admin@lr.com", rol="ADMINISTRADOR")
    iniciar_sesion()
    assert cliente.get(PERFIL).status_code == 200

    services.restringir(usuario.pk, administrador, "Incumplió las reglas")

    respuesta = cliente.get(PERFIL)
    assert respuesta.status_code == 401
    assert "restringida" in respuesta.json()["detail"]
    assert cliente.post(RENOVAR).status_code == 401


@pytest.mark.django_db
def test_mas_de_10_intentos_por_minuto_desde_la_misma_ip_se_frenan(cliente, crear_usuario):
    crear_usuario()
    for _ in range(10):
        cliente.post(TOKEN, {"correo": "ana@correo.com", "password": "adivinando"}, format="json")
    assert cliente.post(TOKEN, {"correo": "ana@correo.com", "password": CLAVE}, format="json").status_code == 429
