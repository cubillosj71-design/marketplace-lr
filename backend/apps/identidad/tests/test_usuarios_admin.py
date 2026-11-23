"""HU-21 Usuarios para el administrador (RF-D-ADM-02.1): GET /admin/usuarios?rol&q.

CA-21.1 y CA-21.3 están en test_restriccion.py; CA-21.2 (anfitrión restringido fuera de la búsqueda) en
apps/busqueda/tests/test_busqueda.py::test_ca_21_2_anfitrion_restringido_no_aparece."""

import pytest

pytestmark = pytest.mark.django_db
USUARIOS = "/api/v1/admin/usuarios"


def test_lista_con_activa_restringida_y_motivo(demo, entrar):
    lista = entrar("admin@inversioneslr.com").get(USUARIOS).json()
    assert len(lista) == 11
    restringido = next(u for u in lista if u["correo"] == "restringido@correo.com")
    assert restringido["activa"] is True and restringido["restringida"] is True
    assert "cobros por fuera" in restringido["motivo_restriccion"] and restringido["restriccion_hasta"]
    libre = next(u for u in lista if u["correo"] == "huesped@correo.com")
    assert libre["restringida"] is False and libre["motivo_restriccion"] is None


@pytest.mark.parametrize("filtros,correos", [
    ({"q": "sofía"}, {"sofia@correo.com"}),
    ({"q": "PEDRO@"}, {"pedro@correo.com"}),
    ({"rol": "HUESPED"}, {"huesped@correo.com", "santiago@correo.com", "mariana@correo.com", "camila@correo.com"}),
    ({"rol": "ANFITRION", "q": "a"}, {"anfitrion@correo.com", "pedro@correo.com", "sofia@correo.com", "restringido@correo.com",
                                     "valentina@correo.com", "julian@correo.com"}),
])
def test_busca_por_nombre_o_correo_y_filtra_por_rol(demo, entrar, filtros, correos):
    lista = entrar("admin@inversioneslr.com").get(USUARIOS, filtros).json()
    assert {u["correo"] for u in lista} == correos


def test_restringir_y_quitar_desde_la_lista(demo, entrar):
    admin = entrar("admin@inversioneslr.com")
    pedro = admin.get(USUARIOS, {"q": "pedro"}).json()[0]
    r = admin.post(f"/api/v1/admin/usuarios/{pedro['id']}/restriccion", {"motivo": "Revisión", "fecha_fin": "2030-01-01T00:00:00Z"}, format="json")
    assert r.status_code == 201
    assert admin.get(USUARIOS, {"q": "pedro"}).json()[0]["restringida"] is True
    assert admin.delete(f"/api/v1/admin/usuarios/{pedro['id']}/restriccion").status_code == 204
    assert admin.get(USUARIOS, {"q": "pedro"}).json()[0]["restringida"] is False


def test_solo_el_administrador_y_rol_valido(demo, entrar):
    assert entrar("anfitrion@correo.com").get(USUARIOS).status_code == 403
    assert entrar("admin@inversioneslr.com").get(USUARIOS, {"rol": "OTRO"}).status_code == 400
