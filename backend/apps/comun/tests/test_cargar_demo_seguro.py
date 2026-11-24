"""cargar_demo no borra datos que no son de la demostración (MAL-34).

- Sin --reiniciar nunca borra ni cambia nada: lo que creó un anfitrión sigue ahí después de correrlo.
- --reiniciar solo con DJANGO_DEBUG=1, muestra cuántos datos ajenos a la demo se van a borrar y pide escribir
  REINICIAR (salvo --si). Cualquier otra respuesta cancela sin tocar la base."""

from io import StringIO

import pytest
from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.comun.management.commands import cargar_demo
from apps.identidad import services as identidad

pytestmark = pytest.mark.django_db

Publicacion = lambda: apps.get_model("catalogo", "Publicacion")  # noqa: E731
Usuario = lambda: apps.get_model("identidad", "Usuario")  # noqa: E731
CORREO = "nueva.anfitriona@prueba.com"


@pytest.fixture
def casa_ajena(publicar):
    """Con la demo cargada: una anfitriona que no es de la demo y su casa en Bogotá (ACTIVA)."""
    identidad.registrar_usuario(nombre_completo="Nueva Anfitriona", correo=CORREO, telefono="3001112233", password="Clave1234",
                                rol="ANFITRION", acepta_datos=True)
    return publicar("Casa nueva en Bogotá", ciudad="Bogotá", tipo="Casa", anfitrion=CORREO)


def _correr(*args, respuesta=None, monkeypatch=None):
    if respuesta is not None:
        def leer(_pregunta):
            if isinstance(respuesta, BaseException):
                raise respuesta
            return respuesta
        monkeypatch.setattr(cargar_demo.Command, "leer_respuesta", staticmethod(leer))
    salida = StringIO()
    call_command("cargar_demo", *args, stdout=salida)
    return salida.getvalue()


# ---------------- Sin --reiniciar
def test_sin_reiniciar_no_borra_la_publicacion_de_un_anfitrion_nuevo(casa_ajena):
    antes = Publicacion().objects.values("titulo", "estado", "precio_noche", "anfitrion__correo").get(pk=casa_ajena)
    total = Publicacion().objects.count()
    salida = _correr()
    assert "ya existen" in salida
    assert Publicacion().objects.values("titulo", "estado", "precio_noche", "anfitrion__correo").get(pk=casa_ajena) == antes
    assert Publicacion().objects.count() == total and Usuario().objects.filter(correo=CORREO).exists()


def test_sin_reiniciar_en_una_base_sin_demo_agrega_la_demo_y_conserva_lo_que_habia(db):
    from apps.catalogo import services as catalogo

    ajena = identidad.registrar_usuario(nombre_completo="Nueva Anfitriona", correo=CORREO, telefono="3001112233",
                                        password="Clave1234", rol="ANFITRION", acepta_datos=True)
    p = catalogo.crear_publicacion(ajena, {"titulo": "Borrador propio", "imagenes": ["https://placehold.co/600x400"]})
    _correr()
    assert Publicacion().objects.filter(pk=p.id, titulo="Borrador propio", anfitrion__correo=CORREO).exists()
    assert Usuario().objects.filter(correo="admin@inversioneslr.com").exists()  # y la demo quedó cargada


# ---------------- --reiniciar
def test_reiniciar_exige_debug(casa_ajena, settings, monkeypatch):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DJANGO_DEBUG=1"):
        _correr("--reiniciar", "--si")
    assert Publicacion().objects.filter(pk=casa_ajena).exists()


@pytest.mark.parametrize("respuesta", ["", "si", "reiniciar", EOFError()])
def test_reiniciar_sin_escribir_REINICIAR_cancela_sin_tocar_la_base(casa_ajena, settings, monkeypatch, respuesta):
    settings.DEBUG = True
    total = Publicacion().objects.count()
    with pytest.raises(CommandError, match="Cancelado: la base no se tocó"):
        _correr("--reiniciar", respuesta=respuesta, monkeypatch=monkeypatch)
    assert Publicacion().objects.filter(pk=casa_ajena).exists() and Publicacion().objects.count() == total


@pytest.mark.django_db(transaction=True)  # flush (TRUNCATE) no corre dentro de la transacción de la prueba
def test_reiniciar_muestra_lo_que_se_borra_y_con_REINICIAR_vacia_y_recarga(casa_ajena, reservar, dias, settings, monkeypatch):
    reservar(casa_ajena, dias(30).isoformat(), dias(32).isoformat())  # una reserva de un huésped de la demo en la casa ajena
    assert cargar_demo.contar_datos_ajenos() == {"usuarios": 1, "publicaciones": 1, "reservas": 1}
    settings.DEBUG = True
    salida = _correr("--reiniciar", respuesta="REINICIAR", monkeypatch=monkeypatch)
    assert "Se borrarán 1 usuarios, 1 publicaciones y 1 reservas que NO son de la demostración" in salida
    assert "VACÍA TODA LA BASE" in salida and "Datos de demostración cargados" in salida
    assert not Publicacion().objects.filter(titulo="Casa nueva en Bogotá").exists()
    assert cargar_demo.contar_datos_ajenos() == {"usuarios": 0, "publicaciones": 0, "reservas": 0}


@pytest.mark.django_db(transaction=True)  # flush (TRUNCATE) no corre dentro de la transacción de la prueba
def test_reiniciar_con_si_no_pregunta(demo, settings, monkeypatch):
    settings.DEBUG = True

    def no_preguntar(_):
        raise AssertionError("con --si no debe preguntar")

    monkeypatch.setattr(cargar_demo.Command, "leer_respuesta", staticmethod(no_preguntar))
    salida = StringIO()
    call_command("cargar_demo", "--reiniciar", "--si", stdout=salida)
    assert "Se borrarán 0 usuarios, 0 publicaciones y 0 reservas" in salida.getvalue()


def test_la_demo_recien_cargada_no_tiene_datos_ajenos(demo):
    assert cargar_demo.contar_datos_ajenos() == {"usuarios": 0, "publicaciones": 0, "reservas": 0}


def test_mostrar_base_dice_a_que_base_apunta(demo):
    salida = StringIO()
    call_command("mostrar_base", stdout=salida)
    texto = salida.getvalue()
    assert "Base: test_" in texto and "publicaciones: 34" in texto and "Primer evento de auditoría" in texto
