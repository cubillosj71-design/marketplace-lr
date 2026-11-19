"""RBAC dinámico (RF-D-USU-02.1, HU-05, ADR-010): el Administrador cambia los permisos de cada rol.

Los roles son fijos (Visitante, Huésped, Anfitrión, Administrador); los permisos de cada rol viven en rol_permiso.
"""

import pytest

from apps.comun import rbac
from apps.identidad import services

ROLES = "/api/v1/identidad/roles"
PERMISOS = "/api/v1/identidad/permisos"


def url(rol, codigo):
    return f"/api/v1/admin/roles/{rol}/permisos/{codigo}"


@pytest.fixture
def admin(demo, entrar):
    return entrar("admin@inversioneslr.com")


def test_la_matriz_inicial_es_la_del_srs(demo, cliente):
    r = cliente.get(ROLES).json()
    assert {x["rol"]: set(x["permisos"]) for x in r["roles"]} == {k: set(v) for k, v in rbac.PERMISOS.items()}
    assert {p["codigo"] for p in r["permisos"]} == rbac.TODOS
    assert all(p["descripcion"] for p in r["permisos"])


def test_retirar_un_permiso_rige_desde_la_siguiente_peticion(admin, entrar):
    huesped = entrar("huesped@correo.com")
    assert huesped.get("/api/v1/reservas/mias").status_code == 200
    r = admin.delete(url("HUESPED", "reservas.ver_propias"))
    assert r.status_code == 200 and "reservas.ver_propias" not in r.json()["permisos"]
    # Con el mismo token: el permiso se revisa en cada petición, no se guarda en el token
    assert huesped.get("/api/v1/reservas/mias").status_code == 403
    assert "reservas.ver_propias" not in huesped.get(PERMISOS).json()["permisos"]


def test_devolver_el_permiso_lo_restablece(admin, entrar):
    huesped = entrar("huesped@correo.com")
    admin.delete(url("HUESPED", "reservas.ver_propias"))
    assert admin.put(url("HUESPED", "reservas.ver_propias")).status_code == 200
    assert huesped.get("/api/v1/reservas/mias").status_code == 200


def test_conceder_una_consulta_de_administracion_a_otro_rol(admin, entrar):
    anfitrion = entrar("anfitrion@correo.com")
    assert anfitrion.get("/api/v1/admin/tablero").status_code == 403
    assert admin.put(url("ANFITRION", "tablero.ver")).status_code == 200
    assert anfitrion.get("/api/v1/admin/tablero").status_code == 200


def test_no_se_concede_un_permiso_que_el_service_ata_a_otro_rol(admin):
    r = admin.put(url("ANFITRION", "publicaciones.moderar"))
    assert r.status_code == 400 and r.json()["campo"] == "permiso"


def test_el_visitante_solo_tiene_permisos_publicos(admin):
    assert admin.put(url("VISITANTE", "reservas.crear")).status_code == 400


@pytest.mark.parametrize("rol, codigo", [("ADMINISTRADOR", "roles.gestionar"), ("HUESPED", "catalogo.ver")])
def test_los_permisos_fijos_no_se_quitan(admin, rol, codigo):
    r = admin.delete(url(rol, codigo))
    assert r.status_code == 400
    assert codigo in services.permisos_del_rol(rol)


def test_rol_o_permiso_inexistente(admin):
    assert admin.put(url("SOPORTE", "tablero.ver")).status_code == 404
    assert admin.put(url("HUESPED", "reservas.inventado")).status_code == 404


def test_solo_el_administrador_cambia_la_matriz(demo, entrar, cliente):
    assert entrar("anfitrion@correo.com").put(url("ANFITRION", "tablero.ver")).status_code == 403
    assert cliente.put(url("ANFITRION", "tablero.ver")).status_code == 401


def test_cada_cambio_queda_en_el_registro_de_acciones(admin, eventos):
    admin.put(url("ANFITRION", "tablero.ver"))
    admin.delete(url("ANFITRION", "tablero.ver"))
    assert eventos(tipo="permisos")[:2] == ["PermisoRetirado", "PermisoConcedido"]


def test_repetir_un_cambio_no_registra_nada_nuevo(admin, eventos):
    admin.put(url("ANFITRION", "tablero.ver"))
    admin.put(url("ANFITRION", "tablero.ver"))
    assert eventos(tipo="permisos").count("PermisoConcedido") == 1


def test_volver_a_migrar_no_deshace_los_cambios_del_administrador(admin):
    admin.delete(url("HUESPED", "reservas.ver_propias"))
    services.asegurar_matriz()  # lo que corre en post_migrate en cada despliegue
    assert "reservas.ver_propias" not in services.permisos_del_rol("HUESPED")


def test_las_reglas_de_la_matriz_son_coherentes():
    for rol in rbac.ROLES:
        assert rbac.FIJOS[rol] <= rbac.PERMISOS[rol] <= rbac.ASIGNABLES[rol] <= rbac.TODOS, rol
