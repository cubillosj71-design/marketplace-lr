"""HU-03 Recuperar la contraseña (MAL-3) - RF-D-USU-01.3, CU-USU-03, RNF-P-SEG-03."""

from datetime import timedelta

import pytest

from apps.identidad.models import TokenRecuperacion

from .conftest import CLAVE

SOLICITAR = "/api/v1/identidad/recuperacion"
NUEVA = "Nueva-clave-456"


def solicitar(cliente, correo="ana@correo.com"):
    respuesta = cliente.post(SOLICITAR, {"correo": correo}, format="json")
    assert respuesta.status_code == 200, respuesta.content
    enlace = respuesta.json()["enlace"]
    return enlace.rsplit("/", 1)[-1]


@pytest.mark.django_db
def test_ca_03_1_con_correo_registrado_se_muestra_un_enlace_en_pantalla(cliente, crear_usuario):
    crear_usuario()

    respuesta = cliente.post(SOLICITAR, {"correo": "ana@correo.com"}, format="json")

    assert respuesta.status_code == 200
    assert respuesta.json()["enlace"].startswith("/recuperar/")


@pytest.mark.django_db
def test_rnf_p_seg_03_en_la_base_queda_el_hash_y_no_el_token(cliente, crear_usuario):
    crear_usuario()
    token = solicitar(cliente)

    registro = TokenRecuperacion.objects.get()
    assert registro.token_hash != token
    assert len(registro.token_hash) == 64
    assert registro.vence - registro.creado == timedelta(minutes=20)


@pytest.mark.django_db
def test_el_enlace_permite_definir_una_nueva_contrasena(cliente, crear_usuario):
    usuario = crear_usuario()
    token = solicitar(cliente)

    assert cliente.get(f"{SOLICITAR}/{token}").json() == {"valido": True}
    respuesta = cliente.post(f"{SOLICITAR}/{token}", {"password": NUEVA}, format="json")

    assert respuesta.status_code == 200
    usuario.refresh_from_db()
    assert usuario.check_password(NUEVA)
    assert not usuario.check_password(CLAVE)


@pytest.mark.django_db
def test_ca_03_2_un_enlace_generado_hace_21_minutos_esta_vencido(cliente, crear_usuario):
    usuario = crear_usuario()
    token = solicitar(cliente)
    registro = TokenRecuperacion.objects.get()
    registro.creado -= timedelta(minutes=21)
    registro.vence -= timedelta(minutes=21)
    registro.save()

    al_abrir = cliente.get(f"{SOLICITAR}/{token}")
    al_enviar = cliente.post(f"{SOLICITAR}/{token}", {"password": NUEVA}, format="json")

    assert al_abrir.status_code == 400 and al_abrir.json()["codigo"] == "enlace_vencido"
    assert al_enviar.status_code == 400 and al_enviar.json()["codigo"] == "enlace_vencido"
    usuario.refresh_from_db()
    assert usuario.check_password(CLAVE)


@pytest.mark.django_db
def test_ca_03_3_un_enlace_ya_usado_se_rechaza(cliente, crear_usuario):
    crear_usuario()
    token = solicitar(cliente)
    assert cliente.post(f"{SOLICITAR}/{token}", {"password": NUEVA}, format="json").status_code == 200

    otra_vez = cliente.post(f"{SOLICITAR}/{token}", {"password": "Otra-clave-789"}, format="json")

    assert otra_vez.status_code == 400
    assert otra_vez.json()["codigo"] == "enlace_usado"


@pytest.mark.django_db
def test_pedir_un_enlace_nuevo_anula_el_anterior(cliente, crear_usuario):
    crear_usuario()
    primero = solicitar(cliente)
    segundo = solicitar(cliente)

    assert cliente.get(f"{SOLICITAR}/{primero}").status_code == 400
    assert cliente.get(f"{SOLICITAR}/{segundo}").status_code == 200


@pytest.mark.django_db
def test_un_token_inventado_no_sirve(cliente):
    assert cliente.get(f"{SOLICITAR}/inventado").json()["codigo"] == "enlace_invalido"


@pytest.mark.django_db
def test_correo_no_registrado_no_genera_enlace(cliente):
    respuesta = cliente.post(SOLICITAR, {"correo": "nadie@correo.com"}, format="json")
    assert respuesta.status_code == 404
    assert respuesta.json()["enlace"] is None
    assert not TokenRecuperacion.objects.exists()


@pytest.mark.django_db
def test_la_nueva_contrasena_tambien_exige_8_caracteres(cliente, crear_usuario):
    crear_usuario()
    token = solicitar(cliente)
    respuesta = cliente.post(f"{SOLICITAR}/{token}", {"password": "corta"}, format="json")
    assert respuesta.json()["codigo"] == "contrasena_invalida"
    # El enlace no se gasta con un intento inválido.
    assert cliente.get(f"{SOLICITAR}/{token}").status_code == 200


@pytest.mark.django_db
def test_cambiar_la_contrasena_cierra_las_sesiones_abiertas(cliente, crear_usuario, iniciar_sesion):
    crear_usuario()
    iniciar_sesion()
    token = solicitar(cliente)
    cliente.post(f"{SOLICITAR}/{token}", {"password": NUEVA}, format="json")

    assert cliente.post("/api/v1/identidad/token/renovar").status_code == 401


@pytest.mark.django_db
def test_abrir_y_usar_el_enlace_no_choca_con_el_limite_de_solicitudes(cliente, crear_usuario):
    """Regresión: el límite de 5/min de pedir enlaces no debe contar las visitas al enlace."""
    crear_usuario()
    token = solicitar(cliente)
    for _ in range(6):
        assert cliente.get(f"{SOLICITAR}/{token}").status_code == 200
    assert cliente.post(f"{SOLICITAR}/{token}", {"password": NUEVA}, format="json").status_code == 200
