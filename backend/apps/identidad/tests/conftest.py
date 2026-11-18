import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

CLAVE = "Clave-segura-123"


@pytest.fixture(autouse=True)
def limpiar_limites_de_intentos():
    # Los límites por IP (throttling) se cuentan en la caché; se limpia para
    # que una prueba no gaste los intentos de la siguiente.
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def cliente():
    return APIClient()


@pytest.fixture
def crear_usuario(django_user_model):
    def _crear(correo="ana@correo.com", rol="HUESPED", password=CLAVE, **extra):
        return django_user_model.objects.create_user(
            correo=correo,
            password=password,
            nombre_completo=extra.pop("nombre_completo", "Ana Pérez"),
            telefono=extra.pop("telefono", "3001234567"),
            rol=rol,
            acepta_datos_en=timezone.now(),
            **extra,
        )

    return _crear


@pytest.fixture
def iniciar_sesion(cliente):
    """Inicia sesión y deja el token de acceso en el encabezado del cliente."""

    def _iniciar(correo="ana@correo.com", password=CLAVE):
        respuesta = cliente.post("/api/v1/identidad/token", {"correo": correo, "password": password}, format="json")
        assert respuesta.status_code == 200, respuesta.content
        cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {respuesta.json()['access']}")
        return respuesta

    return _iniciar
