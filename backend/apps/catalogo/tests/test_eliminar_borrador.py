"""El anfitrión elimina su publicación en BORRADOR (DELETE /catalogo/mis-publicaciones/{id})."""

import pytest
from django.apps import apps

from apps.auditoria import services as auditoria

pytestmark = pytest.mark.django_db
Publicacion = lambda: apps.get_model("catalogo", "Publicacion")  # noqa: E731
ANFITRION = "anfitrion@correo.com"


def _borrador(entrar, correo=ANFITRION) -> int:
    r = entrar(correo, "Clave1234").post("/api/v1/catalogo/publicaciones", {"titulo": "Borrador de prueba"}, format="json")
    assert r.status_code == 201, r.content
    return r.json()["id"]


def test_el_anfitrion_elimina_su_borrador(demo, entrar):
    pid = _borrador(entrar)
    r = entrar(ANFITRION, "Clave1234").delete(f"/api/v1/catalogo/mis-publicaciones/{pid}")
    assert r.status_code == 204
    assert not Publicacion().objects.filter(pk=pid).exists()
    evento = auditoria.consultar(accion="PublicacionEliminada").get()
    assert evento.entidad_id == pid and evento.detalle["titulo"] == "Borrador de prueba"


@pytest.mark.parametrize("estado", ["ACTIVA", "PENDIENTE_REVISION", "PAUSADA", "BLOQUEADA"])
def test_solo_se_elimina_en_borrador(demo, entrar, estado):
    p = Publicacion().objects.filter(anfitrion__correo=ANFITRION, estado=estado).first()
    if not p:
        pytest.skip(f"La demo no tiene una publicación {estado} de este anfitrión")
    r = entrar(ANFITRION, "Clave1234").delete(f"/api/v1/catalogo/mis-publicaciones/{p.id}")
    assert r.status_code == 409 and "borrador" in r.json()["detalle"]
    assert Publicacion().objects.filter(pk=p.id).exists()


def test_no_se_elimina_el_borrador_de_otro_anfitrion(demo, entrar):
    apps.get_model("identidad", "Usuario").registrar("otro.anfitrion@correo.com", "Clave1234", "ANFITRION", nombre_completo="Otro", telefono="300")
    pid = _borrador(entrar)
    r = entrar("otro.anfitrion@correo.com", "Clave1234").delete(f"/api/v1/catalogo/mis-publicaciones/{pid}")
    assert r.status_code == 403
    assert Publicacion().objects.filter(pk=pid).exists()


def test_el_administrador_no_elimina_borradores(demo, entrar):
    pid = _borrador(entrar)
    assert entrar("admin@inversioneslr.com", "Clave1234").delete(f"/api/v1/catalogo/mis-publicaciones/{pid}").status_code == 403
    assert Publicacion().objects.filter(pk=pid).exists()
