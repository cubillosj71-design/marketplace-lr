"""HU-16 Notificaciones (RF-D-RES-04.1): CA-16.1, CA-16.2 y CA-16.3 (un caso por fila del esquema).

Los avisos se crean DESPUÉS de confirmar la transacción: las pruebas ejecutan los callbacks de on_commit con
django_capture_on_commit_callbacks."""

import pytest
from django.apps import apps

from apps.auditoria import services as auditoria

pytestmark = pytest.mark.django_db
BANDEJA = "/api/v1/notificaciones"


def _no_leidas(entrar, correo):
    return [n["tipo"] for n in entrar(correo).get(BANDEJA).json()["notificaciones"] if not n["leida"]]


@pytest.fixture
def reserva(alojamiento_740, reservar, reloj, django_capture_on_commit_callbacks):
    reloj("2026-11-01")
    with django_capture_on_commit_callbacks(execute=True):
        return reservar(alojamiento_740, "2026-11-20", "2026-11-23")


def test_ca_16_1_el_anfitrion_ve_la_nueva_reserva(reserva, entrar):
    b = entrar("anfitrion@correo.com").get(BANDEJA).json()
    nueva = next(n for n in b["notificaciones"] if n["tipo"] == "ReservaConfirmada")
    assert nueva["leida"] is False and nueva["entidad_id"] == reserva["id"] and "Ejemplo 740" in nueva["mensaje"]
    assert b["no_leidas"] >= 1


def test_ca_16_2_primero_las_no_leidas_y_se_marcan(reserva, entrar, reloj, django_capture_on_commit_callbacks):
    h = entrar("huesped@correo.com")
    primera = h.get(BANDEJA).json()["notificaciones"][0]
    assert h.post(f"{BANDEJA}/{primera['id']}/leida").json()["leida"] is True
    reloj("2026-11-10")
    with django_capture_on_commit_callbacks(execute=True):
        h.post(f"/api/v1/reservas/{reserva['id']}/cancelar", {"motivo": "Cambio de planes"}, format="json")
    lista = h.get(BANDEJA).json()["notificaciones"]
    leidas = [n["leida"] for n in lista]
    assert leidas == sorted(leidas) and leidas[0] is False and leidas[-1] is True  # no leídas primero
    assert h.post(f"{BANDEJA}/leidas").json()["marcadas"] >= 1
    assert h.get(BANDEJA).json()["no_leidas"] == 0


def test_solo_se_ven_y_marcan_las_propias(reserva, entrar):
    ajena = entrar("anfitrion@correo.com").get(BANDEJA).json()["notificaciones"][0]["id"]
    assert entrar("sofia@correo.com").post(f"{BANDEJA}/{ajena}/leida").status_code == 404
    assert entrar("sofia@correo.com").get(BANDEJA).json()["no_leidas"] == 0


# ---------------- CA-16.3 Esquema: evento -> destinatarios
def test_ca_16_3_reserva_confirmada_huesped_y_anfitrion(reserva, entrar):
    for correo in ("huesped@correo.com", "anfitrion@correo.com"):
        assert "ReservaConfirmada" in _no_leidas(entrar, correo)


def test_ca_16_3_reserva_cancelada_huesped_y_anfitrion(reserva, entrar, reloj, django_capture_on_commit_callbacks):
    reloj("2026-11-15")
    with django_capture_on_commit_callbacks(execute=True):
        entrar("huesped@correo.com").post(f"/api/v1/reservas/{reserva['id']}/cancelar", {"motivo": "Cambio"}, format="json")
    for correo in ("huesped@correo.com", "anfitrion@correo.com"):
        assert "ReservaCancelada" in _no_leidas(entrar, correo)


def test_ca_16_3_reserva_en_revision_huesped_y_anfitrion(reserva, entrar, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        entrar("admin@inversioneslr.com").post(f"/api/v1/admin/publicaciones/{reserva['publicacion']}/bloqueo", {"motivo": "Fraude"}, format="json")
    for correo in ("huesped@correo.com", "anfitrion@correo.com"):
        assert "ReservaEnRevision" in _no_leidas(entrar, correo)


def test_ca_16_3_reserva_resuelta_solo_huesped(reserva, entrar, django_capture_on_commit_callbacks):
    admin = entrar("admin@inversioneslr.com")
    admin.post(f"/api/v1/admin/publicaciones/{reserva['publicacion']}/bloqueo", {"motivo": "Fraude"}, format="json")
    with django_capture_on_commit_callbacks(execute=True):
        admin.post(f"/api/v1/admin/reservas/{reserva['id']}/resolver", {"mantener": True}, format="json")
    assert "ReservaResuelta" in _no_leidas(entrar, "huesped@correo.com")
    assert "ReservaResuelta" not in _no_leidas(entrar, "anfitrion@correo.com")


@pytest.mark.parametrize("evento,accion", [
    ("PublicacionAprobada", "aprobar"), ("PublicacionDevuelta", "devolver"),
    ("PublicacionBloqueada", "bloquear"), ("PublicacionDesbloqueada", "desbloquear"),
])
def test_ca_16_3_moderacion_avisa_al_anfitrion(demo, entrar, django_capture_on_commit_callbacks, evento, accion):
    Publicacion = apps.get_model("catalogo", "Publicacion")
    admin = entrar("admin@inversioneslr.com")
    pendiente = Publicacion.objects.get(titulo="Habitación cerca al centro").id
    activa = Publicacion.objects.get(titulo="Cabaña El Roble").id  # PAUSADA de Laura: se puede bloquear
    with django_capture_on_commit_callbacks(execute=True):
        if accion == "aprobar":
            admin.post(f"/api/v1/admin/publicaciones/{pendiente}/revision", {"accion": "APROBAR"}, format="json")
        elif accion == "devolver":
            admin.post(f"/api/v1/admin/publicaciones/{pendiente}/revision", {"accion": "DEVOLVER", "observacion": "Faltan fotos"}, format="json")
        else:
            admin.post(f"/api/v1/admin/publicaciones/{activa}/bloqueo", {"motivo": "Revisar"}, format="json")
            if accion == "desbloquear":
                admin.delete(f"/api/v1/admin/publicaciones/{activa}/bloqueo")
    assert evento in _no_leidas(entrar, "anfitrion@correo.com")
    assert evento not in _no_leidas(entrar, "huesped@correo.com")


@pytest.mark.parametrize("evento,ruta", [("PublicacionPausada", "pausar"), ("PublicacionReactivada", "reactivar")])
def test_ca_16_3_pausar_y_reactivar_solo_avisan_si_fue_el_administrador(demo, entrar, django_capture_on_commit_callbacks, evento, ruta):
    Publicacion = apps.get_model("catalogo", "Publicacion")
    pid = Publicacion.objects.get(titulo="Apartamento con vista a Monserrate").id  # ACTIVA de Laura
    laura, admin = entrar("anfitrion@correo.com"), entrar("admin@inversioneslr.com")
    if ruta == "reactivar":
        laura.post(f"/api/v1/catalogo/publicaciones/{pid}/pausar")
    with django_capture_on_commit_callbacks(execute=True):  # lo hace el anfitrión: sin aviso
        laura.post(f"/api/v1/catalogo/publicaciones/{pid}/{ruta}")
    assert evento not in _no_leidas(entrar, "anfitrion@correo.com")
    laura.post(f"/api/v1/catalogo/publicaciones/{pid}/{'reactivar' if ruta == 'pausar' else 'pausar'}")
    with django_capture_on_commit_callbacks(execute=True):  # lo hace el administrador: con aviso
        assert admin.post(f"/api/v1/catalogo/publicaciones/{pid}/{ruta}").status_code == 200
    assert evento in _no_leidas(entrar, "anfitrion@correo.com")


def test_un_aviso_fallido_no_rompe_la_reserva(alojamiento_740, reservar, reloj, monkeypatch, django_capture_on_commit_callbacks):
    Notificacion = apps.get_model("notificaciones", "Notificacion")

    def fallar(*a, **kw):
        raise RuntimeError("La tabla de avisos no responde")

    monkeypatch.setattr(Notificacion.objects, "bulk_create", fallar)
    reloj("2026-11-01")
    with django_capture_on_commit_callbacks(execute=True):
        r = reservar(alojamiento_740, "2026-11-20", "2026-11-23")  # responde 201
    assert apps.get_model("reservas", "Reserva").objects.get(pk=r["id"]).estado == "CONFIRMADA"
    falla = auditoria.consultar_eventos(accion="NotificacionFallida").get()
    assert falla.exitoso is False and falla.detalle["evento"] == "ReservaConfirmada"


def test_los_avisos_se_crean_despues_de_confirmar(alojamiento_740, reservar, reloj):
    """Sin ejecutar on_commit no hay avisos: se crean solo cuando la transacción se confirma."""
    reloj("2026-11-01")
    reservar(alojamiento_740, "2026-11-20", "2026-11-23")
    assert not apps.get_model("notificaciones", "Notificacion").objects.filter(tipo="ReservaConfirmada").exists()
