"""HU-01 Registrarse (MAL-1) - RF-D-USU-01.1, CU-USU-01.

Cada prueba corresponde a un criterio de aceptación o a un flujo alterno del caso de uso.
"""

import pytest

from apps.auditoria import services as auditoria
from apps.identidad.models import Usuario

URL = "/api/v1/identidad/registro"


def datos(**cambios):
    base = {
        "nombre_completo": "Ana Pérez",
        "correo": "ana@correo.com",
        "telefono": "3001234567",
        "password": "Clave-segura-123",
        "rol": "HUESPED",
        "acepta_datos": True,
    }
    base.update(cambios)
    return base


@pytest.mark.django_db
def test_ca_01_1_registro_valido_crea_cuenta_activa_con_rol_huesped_y_permite_iniciar_sesion(cliente):
    respuesta = cliente.post(URL, datos(), format="json")

    assert respuesta.status_code == 201
    usuario = Usuario.objects.get(correo="ana@correo.com")
    assert usuario.rol == "HUESPED"
    assert usuario.estado == "ACTIVA"
    assert usuario.acepta_datos_en is not None
    assert "password" not in respuesta.json()["usuario"]

    ingreso = cliente.post("/api/v1/identidad/token", {"correo": "ana@correo.com", "password": "Clave-segura-123"}, format="json")
    assert ingreso.status_code == 200


@pytest.mark.django_db
def test_ca_01_1_tambien_se_puede_registrar_como_anfitrion(cliente):
    respuesta = cliente.post(URL, datos(rol="ANFITRION"), format="json")
    assert respuesta.status_code == 201
    assert respuesta.json()["usuario"]["rol"] == "ANFITRION"


@pytest.mark.django_db
def test_ca_01_2_correo_ya_registrado_no_crea_la_cuenta(cliente, crear_usuario):
    crear_usuario(correo="ana@correo.com")

    respuesta = cliente.post(URL, datos(correo="ana@correo.com"), format="json")

    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "correo_registrado"
    assert Usuario.objects.count() == 1


@pytest.mark.django_db
def test_ca_01_2_el_correo_repetido_se_detecta_sin_importar_mayusculas(cliente, crear_usuario):
    crear_usuario(correo="ana@correo.com")
    respuesta = cliente.post(URL, datos(correo="  Ana@Correo.COM "), format="json")
    assert respuesta.status_code == 409
    assert Usuario.objects.count() == 1


@pytest.mark.django_db
def test_ca_01_3_contrasena_de_7_caracteres_no_crea_la_cuenta_e_indica_el_minimo(cliente):
    respuesta = cliente.post(URL, datos(password="1234567"), format="json")

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "contrasena_invalida"
    assert "8" in cuerpo["mensaje"]
    assert not Usuario.objects.exists()


@pytest.mark.django_db
def test_contrasena_de_exactamente_8_caracteres_se_acepta(cliente):
    assert cliente.post(URL, datos(password="12345678"), format="json").status_code == 201


@pytest.mark.django_db
def test_flujo_3a_sin_autorizacion_de_datos_no_crea_la_cuenta(cliente):
    respuesta = cliente.post(URL, datos(acepta_datos=False), format="json")

    assert respuesta.status_code == 400
    assert respuesta.json()["codigo"] == "autorizacion_datos_requerida"
    assert not Usuario.objects.exists()


@pytest.mark.django_db
def test_nadie_se_puede_registrar_como_administrador(cliente):
    respuesta = cliente.post(URL, datos(rol="ADMINISTRADOR"), format="json")
    assert respuesta.status_code == 400
    assert not Usuario.objects.exists()


@pytest.mark.django_db
def test_faltan_datos_obligatorios(cliente):
    respuesta = cliente.post(URL, {"correo": "ana@correo.com"}, format="json")
    assert respuesta.status_code == 400
    assert {"nombre_completo", "telefono", "password", "rol", "acepta_datos"} <= set(respuesta.json())


@pytest.mark.django_db
def test_postcondicion_el_registro_queda_en_la_auditoria_sin_la_contrasena(cliente):
    cliente.post(URL, datos(), format="json")

    [evento] = auditoria.consultar(accion="REGISTRO")
    assert evento["exitoso"] is True
    assert evento["actor_id"] == Usuario.objects.get(correo="ana@correo.com").pk
    assert "Clave-segura-123" not in str(evento["detalle"])


@pytest.mark.django_db
def test_rnf_p_seg_01_la_contrasena_se_guarda_como_hash_argon2(cliente):
    cliente.post(URL, datos(), format="json")
    usuario = Usuario.objects.get()
    assert usuario.password.startswith("argon2")
    assert "Clave-segura-123" not in usuario.password
