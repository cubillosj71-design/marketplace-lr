"""SRV-08 Auditoría (MOD-08): HU-23 y el registro de accesos negados (CA-05.2) y fallas (RNF-O-OPE-01).

Cada módulo llama a auditoria.services.registrar() en la misma transacción de su cambio; los
inicios fallidos, los accesos negados y las fallas se registran aunque la petición falle.
"""

import pytest
from django.db import DatabaseError, connection, transaction

from apps.auditoria import services

pytestmark = pytest.mark.django_db
AUDITORIA = "/api/v1/admin/auditoria"


def test_ca_23_1_tres_inicios_fallidos_se_ven_filtrando_por_usuario_y_accion(demo, entrar, cliente):
    for _ in range(3):
        assert cliente.post("/api/v1/identidad/token", {"correo": "huesped@correo.com", "password": "mala"}, format="json").status_code == 401
    huesped = entrar("huesped@correo.com")  # un inicio exitoso que no debe confundirse con los fallidos
    admin = entrar("admin@inversioneslr.com")
    filas = admin.get(AUDITORIA, {"usuario": huesped.usuario["id"], "accion": "InicioSesion", "exitoso": "false"}).json()["results"]
    assert len(filas) == 3
    assert all(f["actor_id"] == huesped.usuario["id"] and f["exitoso"] is False and f["fecha"] for f in filas)
    todas = admin.get(AUDITORIA, {"usuario": huesped.usuario["id"], "accion": "InicioSesion", "desde": "2026-01-01"}).json()["results"]
    assert len(todas) == 4


@pytest.mark.parametrize("sql", [
    "UPDATE evento_auditoria SET accion = 'x'",
    "DELETE FROM evento_auditoria",
    "TRUNCATE evento_auditoria",
])
def test_ca_23_2_update_delete_y_truncate_fallan(demo, entrar, sql):
    entrar("admin@inversioneslr.com")
    antes = services.consultar().count()
    assert antes > 0
    with connection.cursor() as c:
        # La prueba corre dentro de una transacción con revisiones de FK diferidas pendientes; PostgreSQL
        # no permite TRUNCATE con eventos pendientes, así que se resuelven antes para llegar al trigger.
        c.execute("SET CONSTRAINTS ALL IMMEDIATE")
    with pytest.raises(DatabaseError, match="solo inserción"), transaction.atomic(), connection.cursor() as c:
        c.execute(sql)
    assert services.consultar().count() == antes


def test_ca_05_2_huesped_en_la_revision_de_publicaciones_queda_registrado(demo, entrar):
    huesped = entrar("huesped@correo.com")
    assert huesped.get("/api/v1/admin/publicaciones", {"estado": "PENDIENTE_REVISION"}).status_code == 403
    evento = services.consultar(actor_id=huesped.usuario["id"], accion="AccesoDenegado").get()
    assert evento.exitoso is False and evento.detalle["ruta"] == "/api/v1/admin/publicaciones"


def test_falla_no_controlada_queda_registrada_con_exitoso_false(rf):
    from apps.comun.errores import manejar_excepcion

    request = rf.get("/api/v1/algo")
    respuesta = manejar_excepcion(RuntimeError("se cayó"), {"request": request, "view": None})
    assert respuesta.status_code == 500
    evento = services.consultar(accion="ErrorOperacion").get()
    assert evento.exitoso is False and evento.detalle["error"] == "RuntimeError"


def test_registrar_escribe_en_la_misma_transaccion_del_cambio(demo):
    """Si la transacción del cambio se revierte, el evento tampoco queda (C4 nivel 3, vista b)."""
    antes = services.consultar().count()
    with pytest.raises(RuntimeError), transaction.atomic():
        services.registrar(None, "CambioQueSeRevierte")
        raise RuntimeError
    assert services.consultar().count() == antes


def test_auditoria_no_escucha_eventos_de_dominio():
    import weakref

    from apps.comun.eventos import evento_dominio

    refs = [entrada[1] for entrada in evento_dominio.receivers]
    receptores = [r() if isinstance(r, weakref.ReferenceType) else r for r in refs]
    assert receptores  # Reservas sí escucha PublicacionBloqueada
    assert all(getattr(r, "__module__", "") != "apps.auditoria.services" for r in receptores)
