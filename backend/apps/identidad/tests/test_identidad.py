"""SRV-01 Identidad: HU-01 a HU-05 y RF-D-ADM-02.1."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.identidad import services

pytestmark = pytest.mark.django_db
REGISTRO = "/api/v1/identidad/registro"
NUEVO = {"nombre_completo": "Marta Ríos", "correo": "marta@correo.com", "telefono": "300 111 2233",
         "password": "Segura2026", "rol": "HUESPED", "acepta_datos": True}


def test_salud(cliente):
    assert cliente.get("/api/v1/salud").json() == {"estado": "ok"}


# ---------------- HU-01 Registro
def test_registro_guarda_autorizacion_y_clave_argon2(cliente, django_user_model):
    r = cliente.post(REGISTRO, NUEVO, format="json")
    assert r.status_code == 201
    assert r.json()["acepta_datos_en"] and r.json()["fecha_registro"]
    assert django_user_model.objects.get(correo="marta@correo.com").password.startswith("argon2")


def test_registro_con_ciudad_del_catalogo(cliente):
    ciudad = cliente.get("/api/v1/catalogo/ciudades").json()[0]["id"]
    assert cliente.post(REGISTRO, {**NUEVO, "ciudad": ciudad}, format="json").json()["ciudad"] == ciudad
    r = cliente.post(REGISTRO, {**NUEVO, "correo": "otra@correo.com", "ciudad": 99999}, format="json")
    assert r.status_code == 400 and r.json()["campo"] == "ciudad"


def test_ca_01_2_correo_repetido(cliente):
    cliente.post(REGISTRO, NUEVO, format="json")
    r = cliente.post(REGISTRO, {**NUEVO, "correo": "MARTA@correo.com"}, format="json")
    assert r.status_code == 409 and "ya está registrado" in r.json()["detalle"]


def test_ca_01_3_clave_corta(cliente):
    r = cliente.post(REGISTRO, {**NUEVO, "password": "abc12"}, format="json")
    assert r.status_code == 400 and r.json()["campo"] == "password"


def test_ca_01_4_sin_autorizacion_de_datos_no_crea_cuenta(cliente, django_user_model):
    r = cliente.post(REGISTRO, {**NUEVO, "acepta_datos": False}, format="json")
    assert r.status_code == 400 and not django_user_model.objects.filter(correo=NUEVO["correo"]).exists()


def test_no_se_registra_administrador(cliente):
    assert cliente.post(REGISTRO, {**NUEVO, "rol": "ADMINISTRADOR"}, format="json").status_code == 400


# ---------------- HU-02 Iniciar sesión
def test_inicio_de_sesion_y_perfil(demo, entrar):
    c = entrar("huesped@correo.com")
    assert c.usuario["rol"] == "HUESPED"
    assert c.get("/api/v1/identidad/perfil").json()["correo"] == "huesped@correo.com"


def test_ca_02_2_credenciales_incorrectas(demo, cliente):
    r = cliente.post("/api/v1/identidad/token", {"correo": "huesped@correo.com", "password": "mala"}, format="json")
    assert r.status_code == 401


def test_ca_02_3_cuenta_restringida_muestra_motivo(demo, cliente):
    r = cliente.post("/api/v1/identidad/token", {"correo": "restringido@correo.com", "password": "Clave1234"}, format="json")
    assert r.status_code == 403 and "Reportes de huéspedes" in r.json()["motivo"]


def test_sin_token_no_hay_acceso(cliente):
    assert cliente.get("/api/v1/identidad/perfil").status_code == 401


def test_salir_invalida_el_refresh(demo, entrar):
    c = entrar("huesped@correo.com")
    assert c.post("/api/v1/identidad/salir", {"refresh": c.refresh}, format="json").status_code == 204
    assert c.post("/api/v1/identidad/token/renovar", {"refresh": c.refresh}, format="json").status_code == 401


# ---------------- HU-03 Recuperar contraseña
def test_recuperacion_no_revela_si_el_correo_existe(cliente):
    r = cliente.post("/api/v1/identidad/recuperacion", {"correo": "nadie@correo.com"}, format="json")
    assert r.status_code == 202 and "enlace" not in r.json()


def test_restablecer_y_ca_03_3_enlace_usado(demo, cliente, entrar):
    token = services.solicitar_recuperacion("huesped@correo.com")
    url = f"/api/v1/identidad/recuperacion/{token}"
    assert cliente.get(url).json()["estado"] == "valido"
    assert cliente.post(url, {"password": "NuevaClave2026"}, format="json").status_code == 200
    entrar("huesped@correo.com", "NuevaClave2026")
    assert cliente.post(url, {"password": "OtraClave2026"}, format="json").status_code == 410


def test_ca_03_2_enlace_vencido_a_los_20_minutos(demo, cliente):
    from django.apps import apps

    token = services.solicitar_recuperacion("huesped@correo.com")
    apps.get_model("identidad", "TokenRecuperacion").objects.update(vence=timezone.now() - timedelta(minutes=1))
    r = cliente.post(f"/api/v1/identidad/recuperacion/{token}", {"password": "NuevaClave2026"}, format="json")
    assert r.status_code == 410 and "venció" in r.json()["detalle"]


def test_solo_se_guarda_el_hash_del_token(demo):
    from django.apps import apps

    token = services.solicitar_recuperacion("huesped@correo.com")
    assert not apps.get_model("identidad", "TokenRecuperacion").objects.filter(token_hash=token).exists()


# ---------------- HU-04 Perfil · HU-05 Desactivar
def test_perfil_no_cambia_correo_ni_rol(demo, entrar):
    c = entrar("huesped@correo.com")
    r = c.patch("/api/v1/identidad/perfil", {"telefono": "301 000 0000", "correo": "x@x.com", "rol": "ADMINISTRADOR"}, format="json")
    assert r.status_code == 200 and r.json()["telefono"] == "301 000 0000"
    assert r.json()["correo"] == "huesped@correo.com" and r.json()["rol"] == "HUESPED"


def test_cambiar_clave_exige_la_actual(demo, entrar):
    c = entrar("huesped@correo.com")
    r = c.patch("/api/v1/identidad/perfil", {"password_actual": "mala", "password_nueva": "NuevaClave2026"}, format="json")
    assert r.status_code == 400 and r.json()["campo"] == "password_actual"


def test_ca_04_2_no_desactiva_con_reservas_confirmadas(demo, entrar):
    for correo in ("huesped@correo.com", "anfitrion@correo.com"):
        r = entrar(correo).post("/api/v1/identidad/perfil/desactivar")
        assert r.status_code == 409 and r.json()["reservas"]


def test_ca_04_4_desactivar_y_reactivar_al_ingresar(demo, entrar):
    c = entrar("pedro@correo.com")
    assert c.post("/api/v1/identidad/perfil/desactivar").status_code == 200
    assert c.get("/api/v1/identidad/perfil").status_code == 401  # el token deja de servir
    nuevo = entrar("pedro@correo.com")
    assert nuevo.usuario["estado"] == "ACTIVA"


def test_administrador_no_se_desactiva(demo, entrar):
    assert entrar("admin@inversioneslr.com").post("/api/v1/identidad/perfil/desactivar").status_code == 403


# ---------------- RF-D-ADM-02.1 Restricción
def test_restringir_corta_el_acceso_de_inmediato_y_levantar_lo_devuelve(demo, entrar, cliente):
    sofia = entrar("sofia@correo.com")
    admin = entrar("admin@inversioneslr.com")
    url = f"/api/v1/admin/usuarios/{sofia.usuario['id']}/restriccion"
    assert admin.post(url, {"motivo": "Prueba"}, format="json").status_code == 201
    assert sofia.get("/api/v1/identidad/perfil").status_code == 401  # ADR-005: estado revisado en cada petición
    assert admin.delete(url).status_code == 204
    entrar("sofia@correo.com")


def test_restriccion_vencida_libera_la_cuenta(demo, entrar):
    from django.apps import apps

    ahora = timezone.now()
    apps.get_model("identidad", "RestriccionUsuario").objects.update(fecha_inicio=ahora - timedelta(days=2), fecha_fin=ahora - timedelta(minutes=1))
    assert entrar("restringido@correo.com").usuario["estado"] == "ACTIVA"


def test_solo_el_administrador_restringe(demo, entrar):
    c = entrar("anfitrion@correo.com")
    assert c.post(f"/api/v1/admin/usuarios/{c.usuario['id']}/restriccion", {"motivo": "x"}, format="json").status_code == 403
