"""Utilidades de prueba compartidas."""

import pytest
from django.core.cache import cache
from django.core.management import call_command
from rest_framework.test import APIClient

CLAVE = "Clave1234"


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
    """Acciones registradas en la auditoría (requiere pruebas con transaction=True)."""
    from apps.auditoria import services

    return lambda **f: list(services.consultar(**f).values_list("accion", flat=True))
