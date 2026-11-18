"""HU-05 Proteger las funciones por rol (MAL-5) - RF-D-USU-02.1, ADR-005.

También cubre las rutas de restricción (HU-21, RF-D-ADM-02.1), que usan los
mismos permisos y de las que depende CA-02.3.
"""

from types import SimpleNamespace

import pytest
from rest_framework.test import APIRequestFactory

from apps.auditoria import services as auditoria
from apps.identidad.permisos import EsDuenoOAdministrador, Rol, solo_roles

from .conftest import CLAVE


def restriccion_url(usuario_id):
    return f"/api/v1/admin/usuarios/{usuario_id}/restriccion"


@pytest.mark.django_db
def test_ca_05_1_un_visitante_sin_sesion_debe_iniciar_sesion(cliente):
    respuesta = cliente.get("/api/v1/identidad/perfil")
    assert respuesta.status_code == 401  # el front-end lo manda a la pantalla de inicio de sesión


@pytest.mark.django_db
def test_ca_05_2_un_huesped_no_entra_a_funciones_de_administrador_y_queda_registrado(cliente, crear_usuario, iniciar_sesion):
    huesped = crear_usuario()
    otro = crear_usuario(correo="otro@correo.com")
    iniciar_sesion()

    respuesta = cliente.post(restriccion_url(otro.pk), {"motivo": "x"}, format="json")

    assert respuesta.status_code == 403
    [evento] = auditoria.consultar(accion="ACCESO_DENEGADO")
    assert evento["actor_id"] == huesped.pk
    assert evento["detalle"]["ruta"] == restriccion_url(otro.pk)


def _peticion(usuario):
    peticion = APIRequestFactory().patch("/api/v1/catalogo/publicaciones/1")
    peticion.user = usuario
    return peticion


@pytest.mark.django_db
def test_ca_05_3_un_anfitrion_no_puede_modificar_la_publicacion_de_otro(crear_usuario):
    dueno = crear_usuario(correo="dueno@correo.com", rol="ANFITRION")
    intruso = crear_usuario(correo="intruso@correo.com", rol="ANFITRION")
    administrador = crear_usuario(correo="admin@lr.com", rol="ADMINISTRADOR")
    vista = SimpleNamespace(campo_dueno="anfitrion_id")
    publicacion = SimpleNamespace(anfitrion_id=dueno.pk)
    permiso = EsDuenoOAdministrador()

    assert permiso.has_object_permission(_peticion(dueno), vista, publicacion) is True
    assert permiso.has_object_permission(_peticion(intruso), vista, publicacion) is False
    assert permiso.has_object_permission(_peticion(administrador), vista, publicacion) is True
    assert len(auditoria.consultar(accion="ACCESO_DENEGADO", actor_id=intruso.pk)) == 1


@pytest.mark.django_db
def test_solo_roles_admite_varios_roles_sin_registrar_falsos_negados(crear_usuario):
    permiso = solo_roles(Rol.ANFITRION, Rol.ADMINISTRADOR)()
    vista = SimpleNamespace()
    assert permiso.has_permission(_peticion(crear_usuario(correo="a@c.com", rol="ADMINISTRADOR")), vista)
    assert permiso.has_permission(_peticion(crear_usuario(correo="b@c.com", rol="ANFITRION")), vista)
    assert not permiso.has_permission(_peticion(crear_usuario(correo="c@c.com", rol="HUESPED")), vista)
    assert len(auditoria.consultar(accion="ACCESO_DENEGADO")) == 1


@pytest.mark.django_db
def test_hu_21_el_administrador_restringe_y_quita_la_restriccion(cliente, crear_usuario, iniciar_sesion):
    huesped = crear_usuario()
    crear_usuario(correo="admin@lr.com", rol="ADMINISTRADOR")
    iniciar_sesion(correo="admin@lr.com")

    assert cliente.post(restriccion_url(huesped.pk), {"motivo": "Incumplió las reglas"}, format="json").status_code == 201
    huesped.refresh_from_db()
    assert huesped.estado == "RESTRINGIDA"
    assert huesped.restricciones.get().motivo == "Incumplió las reglas"

    otro = cliente.__class__()
    assert otro.post("/api/v1/identidad/token", {"correo": "ana@correo.com", "password": CLAVE}, format="json").status_code == 403

    assert cliente.delete(restriccion_url(huesped.pk)).status_code == 204
    huesped.refresh_from_db()
    assert huesped.estado == "ACTIVA"
    assert huesped.restricciones.get().fecha_fin is not None
    assert otro.post("/api/v1/identidad/token", {"correo": "ana@correo.com", "password": CLAVE}, format="json").status_code == 200


@pytest.mark.django_db
def test_hu_21_la_restriccion_exige_motivo_y_no_aplica_a_administradores(cliente, crear_usuario, iniciar_sesion):
    huesped = crear_usuario()
    otro_admin = crear_usuario(correo="admin2@lr.com", rol="ADMINISTRADOR")
    crear_usuario(correo="admin@lr.com", rol="ADMINISTRADOR")
    iniciar_sesion(correo="admin@lr.com")

    assert cliente.post(restriccion_url(huesped.pk), {"motivo": "   "}, format="json").status_code == 400
    assert cliente.post(restriccion_url(otro_admin.pk), {"motivo": "x"}, format="json").status_code == 400
    assert cliente.delete(restriccion_url(huesped.pk)).status_code == 400  # no tenía restricción
