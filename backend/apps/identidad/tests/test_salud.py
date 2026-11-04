import pytest


@pytest.mark.django_db
def test_ruta_de_salud_responde_ok(client):
    respuesta = client.get("/api/v1/salud")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}


@pytest.mark.django_db
def test_crear_usuario_guarda_la_contrasena_con_argon2(django_user_model):
    from django.utils import timezone

    usuario = django_user_model.objects.create_user(
        correo="huesped@ejemplo.com",
        password="Clave-segura-123",
        nombre_completo="Huésped de Prueba",
        telefono="3000000000",
        rol="HUESPED",
        acepta_datos_en=timezone.now(),
    )
    assert usuario.password.startswith("argon2")
    assert usuario.check_password("Clave-segura-123")
