"""HU-04 Mantener el perfil (MAL-4) - RF-D-USU-01.4, CU-USU-04, CU-USU-05."""

import pytest

from apps.auditoria import services as auditoria
from apps.identidad import services

PERFIL = "/api/v1/identidad/perfil"
DESACTIVAR = "/api/v1/identidad/perfil/desactivar"


@pytest.fixture
def con_reservas_pendientes(monkeypatch):
    """Simula la respuesta de SRV-04 mientras Reservas no tenga su tabla."""
    monkeypatch.setattr("apps.reservas.services.tiene_reservas_confirmadas_pendientes", lambda usuario_id: True)


@pytest.mark.django_db
def test_consultar_el_perfil(cliente, crear_usuario, iniciar_sesion):
    crear_usuario()
    iniciar_sesion()
    cuerpo = cliente.get(PERFIL).json()
    assert cuerpo["correo"] == "ana@correo.com"
    assert cuerpo["telefono"] == "3001234567"
    assert "password" not in cuerpo


@pytest.mark.django_db
def test_ca_04_1_cambiar_nombre_y_telefono_muestra_los_datos_nuevos(cliente, crear_usuario, iniciar_sesion):
    crear_usuario()
    iniciar_sesion()

    respuesta = cliente.patch(PERFIL, {"nombre_completo": "Ana María Pérez", "telefono": "3109876543"}, format="json")

    assert respuesta.status_code == 200
    assert cliente.get(PERFIL).json()["telefono"] == "3109876543"
    assert cliente.get(PERFIL).json()["nombre_completo"] == "Ana María Pérez"
    [evento] = auditoria.consultar(accion="ACTUALIZACION_PERFIL")
    assert evento["detalle"] == {"campos": ["nombre_completo", "telefono"]}  # sin los valores


@pytest.mark.django_db
def test_el_correo_y_el_rol_no_se_cambian_desde_el_perfil(cliente, crear_usuario, iniciar_sesion):
    crear_usuario()
    iniciar_sesion()
    cliente.patch(PERFIL, {"correo": "otro@correo.com", "rol": "ADMINISTRADOR"}, format="json")
    cuerpo = cliente.get(PERFIL).json()
    assert cuerpo["correo"] == "ana@correo.com"
    assert cuerpo["rol"] == "HUESPED"


@pytest.mark.django_db
def test_telefono_invalido_se_rechaza(cliente, crear_usuario, iniciar_sesion):
    crear_usuario()
    iniciar_sesion()
    assert cliente.patch(PERFIL, {"telefono": "abc"}, format="json").status_code == 400


@pytest.mark.django_db
def test_ca_04_2_anfitrion_con_reserva_confirmada_pendiente_no_puede_desactivar(
    cliente, crear_usuario, iniciar_sesion, con_reservas_pendientes
):
    usuario = crear_usuario(rol="ANFITRION")
    iniciar_sesion()

    respuesta = cliente.post(DESACTIVAR)

    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "reservas_pendientes"
    usuario.refresh_from_db()
    assert usuario.estado == "ACTIVA"


@pytest.mark.django_db
def test_ca_04_3_anfitrion_desactivado_deja_de_aparecer_en_las_busquedas(cliente, crear_usuario, iniciar_sesion):
    anfitrion = crear_usuario(rol="ANFITRION")
    otro = crear_usuario(correo="otro@correo.com", rol="ANFITRION")
    iniciar_sesion()

    assert cliente.post(DESACTIVAR).status_code == 200

    anfitrion.refresh_from_db()
    assert anfitrion.estado == "DESACTIVADA"
    # SRV-03 Búsqueda excluye las publicaciones de estos anfitriones.
    assert services.anfitriones_ocultos_ids() == [anfitrion.pk]
    assert otro.pk not in services.anfitriones_ocultos_ids()


@pytest.mark.django_db
def test_desactivar_cierra_la_sesion(cliente, crear_usuario, iniciar_sesion):
    crear_usuario()
    iniciar_sesion()
    cliente.post(DESACTIVAR)

    assert cliente.get(PERFIL).status_code == 401
    assert cliente.post("/api/v1/identidad/token/renovar").status_code == 401


@pytest.mark.django_db
def test_el_administrador_no_tiene_perfil_ni_puede_desactivarse(cliente, crear_usuario, iniciar_sesion):
    crear_usuario(correo="admin@lr.com", rol="ADMINISTRADOR")
    iniciar_sesion(correo="admin@lr.com")
    assert cliente.get(PERFIL).status_code == 403
    assert cliente.post(DESACTIVAR).status_code == 403
