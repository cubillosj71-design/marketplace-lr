"""HU-21 Restringir usuario (RF-D-ADM-02.1): CA-21.1 y CA-21.3.

"Restringida" no es una columna de usuario: se deriva de una RestriccionUsuario vigente.
Restringir no modifica la cuenta ni sus reservas; solo crea la restricción.
"""

import pytest
from django.apps import apps

from apps.reservas import services as reservas

pytestmark = pytest.mark.django_db
TOKEN = "/api/v1/identidad/token"


def _url(usuario_id):
    return f"/api/v1/admin/usuarios/{usuario_id}/restriccion"


def test_ca_21_1_usuario_restringido_no_inicia_sesion(demo, entrar, cliente):
    huesped = entrar("huesped@correo.com")
    admin = entrar("admin@inversioneslr.com")
    assert admin.post(_url(huesped.usuario["id"]), {"motivo": "Cobros por fuera"}, format="json").status_code == 201
    r = cliente.post(TOKEN, {"correo": "huesped@correo.com", "password": "Clave1234"}, format="json")
    assert r.status_code == 403 and r.json()["motivo"] == "Cobros por fuera"
    assert huesped.get("/api/v1/identidad/perfil").status_code == 401  # pierde el acceso en la siguiente petición


def test_restringir_no_cambia_la_cuenta_ni_el_estado_de_sus_reservas(demo, entrar):
    huesped = entrar("huesped@correo.com")
    uid = huesped.usuario["id"]
    antes = {r["id"]: r["estado"] for r in reservas.listar_reservas_para_reporte() if r["huesped"] == uid}
    assert antes and "CONFIRMADA" in set(antes.values())
    entrar("admin@inversioneslr.com").post(_url(uid), {"motivo": "Prueba"}, format="json")
    despues = {r["id"]: r["estado"] for r in reservas.listar_reservas_para_reporte() if r["huesped"] == uid}
    assert despues == antes
    cuenta = apps.get_model("identidad", "Usuario").objects.get(pk=uid)
    assert cuenta.activa is True and cuenta.esta_restringida is True and cuenta.is_active is False


def test_ca_21_3_al_levantar_la_restriccion_vuelve_a_entrar(demo, entrar, cliente):
    restringido = apps.get_model("identidad", "Usuario").objects.get(correo="restringido@correo.com")
    assert cliente.post(TOKEN, {"correo": "restringido@correo.com", "password": "Clave1234"}, format="json").status_code == 403
    assert entrar("admin@inversioneslr.com").delete(_url(restringido.id)).status_code == 204
    restriccion = apps.get_model("identidad", "RestriccionUsuario").objects.get(usuario=restringido)
    assert restriccion.fecha_fin is not None and not restriccion.esta_vigente()  # levantarla pone fecha_fin = ahora
    u = entrar("restringido@correo.com").usuario
    assert u["activa"] is True and u["restringida"] is False
