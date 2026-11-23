"""Operaciones del diagrama de clases (MOD-01 y MOD-04) que viven en las clases del dominio: calcularTotal,
calcularDevolucion, cancelar(motivo): Cancelacion, cancelarSinResolucion(): Cancelacion, y en Usuario
registrar, iniciarSesion, actualizarPerfil, desactivar y reactivar. Los flujos completos se prueban por la API
en los demás archivos; aquí se fija que cada operación existe y hace lo que dice el diagrama."""

from decimal import Decimal

import pytest
from django.apps import apps

from apps.comun.errores import ErrorNegocio

pytestmark = pytest.mark.django_db
Reserva = lambda: apps.get_model("reservas", "Reserva")  # noqa: E731
Pago = lambda: apps.get_model("pagos", "Pago")  # noqa: E731
Usuario = lambda: apps.get_model("identidad", "Usuario")  # noqa: E731


def test_calcular_total_de_la_cotizacion():
    c = apps.get_model("reservas", "Cotizacion")(precio_base=Decimal("600000"), descuento=Decimal("0"),
                                                 tarifa_limpieza=Decimal("50000"), tarifa_servicio=Decimal("60000"),
                                                 total_adicionales=Decimal("30000"))
    assert c.calcular_total() == Decimal("740000")  # ejemplo del SRS (CA-12.1)


def test_calcular_devolucion_redondea_al_peso():
    r = Reserva()(total=Decimal("740001"))
    assert apps.get_model("reservas", "Cancelacion")(reserva=r, porcentaje_devolucion=Decimal("50")).calcular_devolucion() == Decimal("370001")


@pytest.fixture
def reserva(alojamiento_740, reservar, reloj):
    reloj("2026-11-01")
    return Reserva().objects.get(pk=reservar(alojamiento_740, "2026-11-20", "2026-11-23")["id"])


def test_cancelar_devuelve_la_cancelacion(reserva, reloj):
    reloj("2026-11-15")
    c = reserva.cancelar_reserva("Cambio de planes", porcentaje=Decimal("50"), cancelada_por_id=reserva.huesped_id)
    assert reserva.estado == "CANCELADA"
    assert (c.pk is not None, c.motivo, c.dias_anticipacion, c.valor_devolucion) == (True, "Cambio de planes", 5, Decimal("370000"))


def test_cancelar_sin_resolucion_devuelve_el_100(reserva, reloj):
    reserva.pasar_a_revision()
    reloj("2026-11-20")
    c = reserva.cancelar_sin_resolucion()
    assert (reserva.estado, c.cancelada_por_id, c.porcentaje_devolucion, c.valor_devolucion) == ("CANCELADA", None, Decimal("100"), Decimal("740000"))
    assert c.motivo == "Sin resolución antes de la llegada"


def test_resolver_mantener_no_crea_cancelacion(reserva):
    reserva.pasar_a_revision()
    assert reserva.resolver_revision(True) is None and reserva.estado == "CONFIRMADA"


def test_la_devolucion_usa_la_pasarela_del_cobro(reserva, entrar, reloj, settings, monkeypatch):
    """Un cobro hecho con Stripe (pi_...) se devuelve con AdaptadorStripe.devolver(referencia, monto)."""
    from apps.pagos.pasarela import AdaptadorStripe, ResultadoPago

    Pago().objects.filter(reserva_id=reserva.id, tipo="COBRO").update(referencia_externa="pi_prueba")
    settings.STRIPE_SECRET_KEY = "llave-falsa-solo-para-pruebas"
    llamadas = []
    monkeypatch.setattr(AdaptadorStripe, "devolver",
                        lambda self, referencia, monto: llamadas.append((referencia, monto)) or ResultadoPago("APROBADO", "re_prueba"))
    reloj("2026-11-15")
    r = entrar("huesped@correo.com", "Clave1234").post(f"/api/v1/reservas/{reserva.id}/cancelar", {"motivo": "Viaje"}, format="json")
    assert r.status_code == 200, r.content
    assert llamadas == [("pi_prueba", Decimal("370000"))]
    assert Pago().objects.get(reserva_id=reserva.id, tipo="DEVOLUCION").referencia_externa == "re_prueba"


# ---------------- Usuario (MOD-01)
def test_registrar_guarda_la_autorizacion_de_datos():
    u = Usuario().registrar("nuevo@correo.com", "Segura2026", "HUESPED", nombre_completo="Nuevo", telefono="300")
    assert u.check_password("Segura2026") and u.autorizacion_datos is not None and u.activa


def test_iniciar_sesion_verifica_correo_y_clave():
    u = Usuario().registrar("nuevo@correo.com", "Segura2026", "HUESPED", nombre_completo="Nuevo", telefono="300")
    assert u.iniciar_sesion(" Nuevo@Correo.com ", "Segura2026")
    assert not u.iniciar_sesion("nuevo@correo.com", "otra")
    assert not u.iniciar_sesion("otro@correo.com", "Segura2026")


def test_actualizar_perfil_no_deja_datos_vacios():
    u = Usuario().registrar("nuevo@correo.com", "Segura2026", "HUESPED", nombre_completo="Nuevo", telefono="300")
    assert u.actualizar_perfil(nombre=" Ana ") == ["nombre_completo"] and u.nombre_completo == "Ana"
    with pytest.raises(ErrorNegocio):
        u.actualizar_perfil(telefono="  ")


def test_desactivar_y_reactivar():
    u = Usuario().registrar("nuevo@correo.com", "Segura2026", "HUESPED", nombre_completo="Nuevo", telefono="300")
    u.desactivar_cuenta()
    assert not Usuario().objects.get(pk=u.pk).activa
    u.reactivar_cuenta()
    assert Usuario().objects.get(pk=u.pk).activa
