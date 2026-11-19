"""El teléfono solo acepta números (con espacios opcionales para separarlos), entre 7 y 15 dígitos, al registrarse
y al editar el perfil."""

import pytest

pytestmark = pytest.mark.django_db
NUEVO = {"nombre_completo": "Ana Torres", "correo": "ana.tel@correo.com", "password": "Segura2026", "rol": "HUESPED",
         "acepta_datos": True}
MALOS = ["300 12a 4567", "abc1234567", "+57 300 123 4567", "300-123-4567", "123456", "1234567890123456", "３００１２３４５６７"]
BUENOS = [("3001234567", "3001234567"), ("300 123 4567", "300 123 4567"), ("  601   555 0100 ", "601 555 0100"), ("1234567", "1234567")]


@pytest.mark.parametrize("telefono", MALOS)
def test_registro_rechaza_telefono_con_letras_o_simbolos(cliente, telefono):
    r = cliente.post("/api/v1/identidad/registro", {**NUEVO, "telefono": telefono}, format="json")
    assert r.status_code == 400 and r.json()["campo"] == "telefono", r.content


@pytest.mark.parametrize("telefono,guardado", BUENOS)
def test_registro_acepta_solo_numeros(cliente, telefono, guardado):
    r = cliente.post("/api/v1/identidad/registro", {**NUEVO, "telefono": telefono}, format="json")
    assert r.status_code == 201, r.content
    assert r.json()["telefono"] == guardado


@pytest.mark.parametrize("telefono", MALOS)
def test_perfil_no_guarda_telefono_con_letras(demo, entrar, telefono):
    c = entrar("huesped@correo.com", "Clave1234")
    antes = c.get("/api/v1/identidad/perfil").json()["telefono"]
    r = c.patch("/api/v1/identidad/perfil", {"telefono": telefono}, format="json")
    assert r.status_code == 400 and r.json()["campo"] == "telefono", r.content
    assert c.get("/api/v1/identidad/perfil").json()["telefono"] == antes


def test_perfil_guarda_un_telefono_valido(demo, entrar):
    c = entrar("huesped@correo.com", "Clave1234")
    r = c.patch("/api/v1/identidad/perfil", {"telefono": "310 555 0182"}, format="json")
    assert r.status_code == 200 and r.json()["telefono"] == "310 555 0182"
