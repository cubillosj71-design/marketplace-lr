"""MAL-35: 21 ciudades en el catálogo y una demo con al menos un alojamiento ACTIVO en cada una.

La migración 0006 agrega 12 ciudades sin repetir (get_or_create) y tiene reversa. cargar_demo deja 27 publicaciones
ACTIVAS (13 de antes + 14 nuevas, una por cada ciudad que no tenía ninguna), conserva las 7 que no están activas y es
idempotente."""

from collections import Counter
from importlib import import_module
from pathlib import Path

import pytest
from django.apps import apps
from django.conf import settings
from django.core.management import call_command

from apps.catalogo import services as catalogo
from apps.comun.management.commands.cargar_demo import PUBLICACIONES

pytestmark = pytest.mark.django_db

Ciudad = lambda: apps.get_model("catalogo", "Ciudad")  # noqa: E731
Publicacion = lambda: apps.get_model("catalogo", "Publicacion")  # noqa: E731
migracion = import_module("apps.catalogo.migrations.0006_mas_ciudades")
NUEVAS = {nombre for nombre, _ in migracion.CIUDADES_NUEVAS}
FOTOS = Path(settings.BASE_DIR).parent / "frontend" / "public" / "alojamientos"


def _conteos():
    modelos = ["identidad.Usuario", "catalogo.Ciudad", "catalogo.Publicacion", "catalogo.ImagenPublicacion",
               "catalogo.ServicioAdicional", "reservas.Reserva", "reservas.Cotizacion", "reservas.Cancelacion", "pagos.Pago"]
    return {m: apps.get_model(*m.split(".")).objects.count() for m in modelos}


# ---------------- Migración 0006
def test_la_migracion_deja_21_ciudades_sin_duplicados():
    filas = list(Ciudad().objects.values_list("nombre", "departamento"))
    assert len(filas) == 21 and len(set(filas)) == 21
    assert len({n for n, _ in filas}) == 21  # tampoco se repite el nombre
    assert NUEVAS <= {n for n, _ in filas}
    assert ("San Andrés", "San Andrés y Providencia") in filas and ("Barichara", "Santander") in filas


def test_la_migracion_es_idempotente_y_tiene_reversa():
    migracion.agregar(apps, None)  # otra vez: no duplica
    assert Ciudad().objects.count() == 21
    migracion.quitar(apps, None)
    assert Ciudad().objects.count() == 9 and not Ciudad().objects.filter(nombre__in=NUEVAS).exists()
    migracion.agregar(apps, None)
    assert Ciudad().objects.count() == 21


def test_la_reversa_no_borra_una_ciudad_con_publicaciones(publicar):
    publicar("Casa en Salento", ciudad="Salento", tipo="Casa")
    migracion.quitar(apps, None)
    assert Ciudad().objects.filter(nombre="Salento").exists()


def test_las_ciudades_salen_en_orden_alfabetico(cliente):
    nombres = [c["nombre"] for c in cliente.get("/api/v1/catalogo/ciudades").json()]
    assert nombres == sorted(nombres, key=catalogo.clave_alfabetica)
    assert nombres[:3] == ["Barichara", "Barranquilla", "Bogotá"]
    # "San Andrés" y "San Gil" van antes de "Santa Fe de Antioquia" y "Santa Marta"; las tildes no cambian el orden
    assert nombres.index("San Andrés") < nombres.index("San Gil") < nombres.index("Santa Fe de Antioquia") < nombres.index("Santa Marta")
    assert nombres.index("Pereira") < nombres.index("Popayán") < nombres.index("Salento")


# ---------------- Demo
def test_la_demo_tiene_27_activas_y_conserva_las_7_que_no_lo_estan(demo):
    estados = Counter(Publicacion().objects.values_list("estado", flat=True))
    assert estados == {"ACTIVA": 27, "PAUSADA": 2, "PENDIENTE_REVISION": 3, "BORRADOR": 1, "BLOQUEADA": 1}


def test_cada_ciudad_tiene_al_menos_una_activa_y_su_busqueda_no_sale_vacia(demo, cliente):
    activas = Counter(Publicacion().objects.filter(estado="ACTIVA").values_list("ciudad__nombre", flat=True))
    ciudades = list(Ciudad().objects.values_list("id", "nombre"))
    assert {n for _, n in ciudades} == set(activas)
    for cid, nombre in ciudades:  # búsqueda pública sin sesión, la misma de Explorar
        assert cliente.get("/api/v1/busqueda/publicaciones", {"ciudad": cid}).json(), nombre


def test_los_alojamientos_nuevos_tienen_5_fotos_que_existen_y_variedad(demo):
    nuevos = [d for _, _, _, d, _ in PUBLICACIONES[20:]]
    assert len(nuevos) == 14 and {d["ciudad"] for d in nuevos} == NUEVAS | {"Guatavita", "Villa de Leyva"}
    assert {d["tipo"] for d in nuevos} == {"Apartamento", "Casa", "Cabaña", "Habitación"}
    assert any(d.get("descuento_porcentaje") for d in nuevos) and any(d.get("servicios_adicionales") for d in nuevos)
    rutas = [r for d in nuevos for r in d["imagenes"]]
    assert all(len(d["imagenes"]) == 5 for d in nuevos) and len(set(rutas)) == len(rutas)
    for r in rutas:
        assert (FOTOS / Path(r).name).is_file(), r
    todas = [r for _, _, _, d, _ in PUBLICACIONES for r in d["imagenes"]]
    assert len(set(todas)) == len(todas)  # ninguna foto se repite entre alojamientos


def test_hay_reservas_en_las_ciudades_nuevas_pasadas_proximas_y_una_cancelada(demo):
    Reserva = apps.get_model("reservas", "Reserva")
    qs = Reserva.objects.filter(publicacion__ciudad__nombre__in=NUEVAS)
    assert set(qs.values_list("estado", flat=True)) == {"COMPLETADA", "CONFIRMADA", "CANCELADA"}
    assert qs.values("publicacion__ciudad").distinct().count() >= 10


def test_correr_cargar_demo_dos_veces_no_duplica_nada(demo):
    antes = _conteos()
    call_command("cargar_demo", verbosity=0)
    assert _conteos() == antes
