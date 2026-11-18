"""HU-23 Registro de acciones: CA-23.3 (filtrar por tipo de acción) y los tipos disponibles para el filtro.

Las acciones se producen por la API real: Auditoría no importa otras apps, ni siquiera en sus pruebas."""

import uuid

import pytest

pytestmark = pytest.mark.django_db
REGISTRO = "/api/v1/admin/auditoria"


def _pausar_publicacion(entrar, **_):
    admin = entrar("admin@inversioneslr.com")
    pid = next(p["id"] for p in admin.get("/api/v1/admin/publicaciones", {"estado": "ACTIVA"}).json()["results"]
               if p["titulo"] == "Apartamento con vista a Monserrate")
    assert admin.post(f"/api/v1/catalogo/publicaciones/{pid}/pausar").status_code == 200
    return "PublicacionPausada", "Admin LR", True


def _acceso_no_permitido(entrar, **_):
    assert entrar("huesped@correo.com").get("/api/v1/admin/tablero").status_code == 403
    return "AccesoDenegado", "Carlos Ruiz", False


def _reservar(entrar, alojamiento_740, reservar, dias, **_):
    reservar(alojamiento_740, dias(30).isoformat(), dias(33).isoformat())
    return "ReservaConfirmada", "Carlos Ruiz", True


def _reserva_rechazada(entrar, alojamiento_740, dias, **_):
    h = entrar("huesped@correo.com")
    cot = h.post("/api/v1/reservas/cotizaciones", {"publicacion": alojamiento_740, "fecha_llegada": dias(30).isoformat(),
                                                   "fecha_salida": dias(33).isoformat(), "num_huespedes": 2}, format="json").json()
    r = h.post("/api/v1/reservas", {"cotizacion": cot["id"], "clave_idempotencia": str(uuid.uuid4()), "medio_pago": "rechazar"}, format="json")
    assert r.status_code == 402
    return "ReservaRechazada", "Carlos Ruiz", False


def _cancelar(entrar, alojamiento_740, reservar, dias, **_):
    rid = reservar(alojamiento_740, dias(30).isoformat(), dias(33).isoformat())["id"]
    assert entrar("huesped@correo.com").post(f"/api/v1/reservas/{rid}/cancelar", {"motivo": "Viaje cancelado"}, format="json").status_code == 200
    return "ReservaCancelada", "Carlos Ruiz", True


def _restringir(entrar, **_):
    admin = entrar("admin@inversioneslr.com")
    pedro = next(u for u in admin.get("/api/v1/admin/usuarios", {"q": "pedro"}).json())
    assert admin.post(f"/api/v1/admin/usuarios/{pedro['id']}/restriccion", {"motivo": "Prueba"}, format="json").status_code == 201
    return "CuentaRestringida", "Admin LR", True


def _descargar(entrar, **_):
    assert entrar("admin@inversioneslr.com").get("/api/v1/admin/reportes/usuarios", {"formato": "xlsx"}).status_code == 200
    return "ReporteDescargado", "Admin LR", True


@pytest.mark.parametrize("tipo,accion", [
    ("acceso_no_permitido", _acceso_no_permitido),
    ("estado_publicacion", _pausar_publicacion),
    ("estado_reserva", _reservar),
    ("reserva_rechazada", _reserva_rechazada),
    ("cancelacion", _cancelar),
    ("accion_administrador", _restringir),
    ("descarga_reporte", _descargar),
])
def test_ca_23_3_el_filtro_por_tipo_muestra_quien_sobre_que_cuando_y_resultado(demo, entrar, alojamiento_740, reservar, dias, tipo, accion):
    esperado, quien, exitoso = accion(entrar=entrar, alojamiento_740=alojamiento_740, reservar=reservar, dias=dias)
    filas = entrar("admin@inversioneslr.com").get(REGISTRO, {"tipo": tipo}).json()["results"]
    fila = next(f for f in filas if f["accion"] == esperado)
    assert fila["actor_nombre"] == quien  # quién
    assert fila["entidad"] or (fila["detalle"] or {}).get("ruta") or (fila["detalle"] or {}).get("tipo")  # sobre qué
    assert fila["fecha"]  # cuándo
    assert fila["exitoso"] is exitoso  # con qué resultado
    if tipo == "accion_administrador":
        assert {f["actor_rol"] for f in filas} == {"ADMINISTRADOR"}


def test_el_registro_trae_los_tipos_de_accion_para_el_filtro(demo, entrar):
    datos = entrar("admin@inversioneslr.com").get(REGISTRO).json()
    claves = {t["clave"] for t in datos["tipos"]}
    assert {"inicio_sesion", "acceso_no_permitido", "estado_publicacion", "estado_reserva", "reserva_rechazada",
            "cancelacion", "accion_administrador", "descarga_reporte"} <= claves
    assert all(t["nombre"] for t in datos["tipos"])


def test_ca_23_1_tipo_inicio_de_sesion_por_usuario(demo, entrar, cliente):
    for _ in range(3):
        cliente.post("/api/v1/identidad/token", {"correo": "pedro@correo.com", "password": "mala"}, format="json")
    admin = entrar("admin@inversioneslr.com")
    pedro = admin.get("/api/v1/admin/usuarios", {"q": "pedro"}).json()[0]["id"]
    filas = admin.get(REGISTRO, {"usuario": pedro, "tipo": "inicio_sesion"}).json()["results"]
    assert len(filas) == 3 and all(f["exitoso"] is False and f["fecha"] for f in filas)


def test_tipo_desconocido_responde_400(demo, entrar):
    assert entrar("admin@inversioneslr.com").get(REGISTRO, {"tipo": "otro"}).status_code == 400
