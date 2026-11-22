"""Utilidades de prueba compartidas."""

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.db.models.signals import post_migrate
from rest_framework.test import APIClient

CLAVE = "Clave1234"


@pytest.fixture(autouse=True)
def pasarela_simulada(settings):
    """Las pruebas usan siempre el AdaptadorSimulado de Pagos, aunque haya STRIPE_SECRET_KEY en el entorno."""
    settings.STRIPE_SECRET_KEY = ""


def _es_transaccional(item) -> bool:
    marca = item.get_closest_marker("django_db")
    return bool(marca and (marca.kwargs.get("transaction") or (marca.args and marca.args[0])))


def _reactivar_triggers(sender, **kwargs):
    """flush emite post_migrate justo después del TRUNCATE: ahí se vuelven a encender los triggers."""
    if sender.name == "apps.pagos":
        from apps.comun.bd import _cambiar

        _cambiar("ENABLE")


post_migrate.connect(_reactivar_triggers, dispatch_uid="pruebas_reactivar_triggers")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item, nextitem):
    """Las pruebas con transaction=True limpian la base con flush, que usa TRUNCATE. evento_auditoria, reserva y
    pago rechazan TRUNCATE (RNF-E-CON-01): solo durante esa limpieza se apagan esos triggers, igual que en
    `cargar_demo --reiniciar`. Se encienden otra vez en _reactivar_triggers, al terminar el flush."""
    if _es_transaccional(item):
        from pytest_django.plugin import blocking_manager_key

        from apps.comun.bd import _cambiar

        with item.config.stash[blocking_manager_key].unblock():
            _cambiar("DISABLE")
    yield


@pytest.fixture(autouse=True)
def limpiar_limites_de_intentos():
    """Los límites por IP (throttling) se cuentan en la caché: se limpian para que una
    prueba no gaste los intentos de la siguiente."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def demo(db):
    """Datos de demostración (mismas cuentas y publicaciones del prototipo)."""
    call_command("cargar_demo", verbosity=0)


@pytest.fixture
def cliente():
    return APIClient()


@pytest.fixture
def entrar():
    """Devuelve un APIClient con sesión iniciada por la API real (POST /identidad/token)."""

    def _entrar(correo, clave=CLAVE):
        c = APIClient()
        r = c.post("/api/v1/identidad/token", {"correo": correo, "password": clave}, format="json")
        assert r.status_code == 200, r.content
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.json()['access']}")
        c.refresh = r.cookies["renovacion"].value  # el refresh llega en la cookie httpOnly
        c.usuario = r.json()["usuario"]
        return c

    return _entrar


@pytest.fixture
def eventos():
    """Acciones registradas en la auditoría. registrar() escribe en la misma transacción, así que no
    hace falta transaction=True (que además no sirve: flush usa TRUNCATE y el trigger lo rechaza)."""
    from apps.auditoria import services

    return lambda **f: list(services.consultar_eventos(**f).values_list("accion", flat=True))


@pytest.fixture
def publicar(demo):
    """Crea una publicación ACTIVA por los services reales (crear, enviar a revisión y aprobar).

    Uso: publicar(titulo="...", ciudad="Cartagena", tipo="Apartamento", precio=200000, servicios=["Wi-Fi"],
    adicionales=[("Desayuno", 30000)], descuento=(10, 7), capacidad=4, anfitrion="anfitrion@correo.com")."""
    from decimal import Decimal

    from django.apps import apps

    from apps.catalogo import services as catalogo

    Usuario = apps.get_model("identidad", "Usuario")
    cat = catalogo.listar_catalogos()
    ciudades = {c["nombre"]: c["id"] for c in cat["ciudades"]}
    tipos = {t["nombre"]: t["id"] for t in cat["tipos"]}
    ids_servicio = {s["nombre"]: s["id"] for s in cat["servicios"]}
    politica = apps.get_model("catalogo", "PoliticaCancelacion").objects.get(nombre="Moderada").id
    admin = Usuario.objects.get(correo="admin@inversioneslr.com")

    def _publicar(titulo, ciudad="Cartagena", tipo="Apartamento", precio=200000, capacidad=4, limpieza=50000,
                  servicios=(), adicionales=(), descuento=None, anfitrion="anfitrion@correo.com"):
        dueno = Usuario.objects.get(correo=anfitrion)
        datos = {
            "titulo": titulo, "descripcion": "Alojamiento de prueba.", "ciudad": ciudades[ciudad], "tipo_alojamiento": tipos[tipo],
            "politica": politica, "ubicacion_textual": "Centro", "capacidad": capacidad, "precio_noche": Decimal(precio),
            "tarifa_limpieza": Decimal(limpieza), "servicios": [ids_servicio[s] for s in servicios],
            "servicios_adicionales": [{"nombre": n, "precio": Decimal(p)} for n, p in adicionales],
            "reglas": ["No fumar"], "imagenes": [f"https://placehold.co/600x400?text={titulo.replace(' ', '+')}"],
            **({"descuento_porcentaje": Decimal(descuento[0]), "descuento_min_noches": descuento[1]} if descuento else {}),
        }
        p = catalogo.crear_publicacion(dueno, datos)
        catalogo.cambiar_estado(dueno, p.id, "PENDIENTE_REVISION")
        catalogo.revisar_publicacion(admin, p.id, "APROBAR", None)
        return p.id

    return _publicar


@pytest.fixture
def dias():
    """dias(n) -> fecha de hoy + n días. Las pruebas usan fechas relativas para respetar el límite de 12 meses."""
    from datetime import timedelta

    from django.utils import timezone

    return lambda n: timezone.localdate() + timedelta(days=n)


@pytest.fixture
def reloj():
    """reloj("2026-11-15") fija el día (hora de Colombia, 09:00) para las reglas que dependen de la fecha."""
    from datetime import datetime

    from django.utils import timezone

    from apps.comun import reloj as r

    def _fijar(texto: str):
        r.fijar(timezone.make_aware(datetime.fromisoformat(texto if "T" in texto else texto + "T09:00")))

    yield _fijar
    r.fijar(None)


@pytest.fixture
def alojamiento_740(publicar):
    """Ejemplo del SRS: $200.000 por noche, limpieza $50.000 y desayuno $30.000. Con 3 noches, desayuno y la
    tarifa del 10 %, la reserva cuesta $740.000 (CA-12.1, CA-15.1)."""
    return publicar("Ejemplo 740", precio=200000, limpieza=50000, adicionales=[("Desayuno", 30000)], capacidad=4)


@pytest.fixture
def reservar(entrar):
    """Cotiza y reserva por la API real con el pago simulado. Devuelve el JSON de la reserva."""
    import uuid

    from django.apps import apps

    def _reservar(pid, llegada, salida, huespedes=2, desayuno=True, correo="huesped@correo.com", clave="Clave1234"):
        h = entrar(correo, clave)
        adicionales = list(apps.get_model("catalogo", "ServicioAdicional").objects.filter(publicacion_id=pid).values_list("id", flat=True)) if desayuno else []
        cot = h.post("/api/v1/reservas/cotizaciones", {"publicacion": pid, "fecha_llegada": llegada, "fecha_salida": salida,
                                                       "num_huespedes": huespedes, "adicionales": adicionales}, format="json")
        assert cot.status_code == 201, cot.content
        r = h.post("/api/v1/reservas", {"cotizacion": cot.json()["id"], "clave_idempotencia": str(uuid.uuid4()),
                                        "medio_pago": "simulado"}, format="json")
        assert r.status_code == 201, r.content
        return r.json()

    return _reservar
