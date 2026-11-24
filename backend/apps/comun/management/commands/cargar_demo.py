"""Carga los datos de demostración del prototipo (mismas cuentas y publicaciones del frontend).

Uso: python manage.py cargar_demo [--reiniciar [--si]]
Contraseña de todas las cuentas: Clave1234

Sin --reiniciar nunca borra ni cambia datos: si la demostración ya está, no hace nada; si no, la agrega al lado de
lo que haya. --reiniciar VACÍA TODA LA BASE: solo con DJANGO_DEBUG=1, muestra antes cuántos usuarios, publicaciones y
reservas que no son de la demostración se van a perder y pide escribir REINICIAR (o --si para no preguntar).

Usa las interfaces públicas de cada servicio. Solo para ajustar las fechas de creación
(para que los reportes tengan datos repartidos en el año) toca las tablas con apps.get_model.
"""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from importlib import import_module

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.test import override_settings
from django.utils import timezone

from apps.catalogo import services as catalogo
from apps.comun import reloj
from apps.comun.bd import permitir_vaciado
from apps.identidad import services as identidad
from apps.reservas import services as reservas

CLAVE = "Clave1234"
USUARIOS = [
    # correo, nombre, teléfono, rol, ciudad, fecha de registro
    ("anfitrion@correo.com", "Laura Gómez", "310 555 0182", "ANFITRION", "Bogotá", "2026-03-14"),
    ("huesped@correo.com", "Carlos Ruiz", "315 222 4410", "HUESPED", "Medellín", "2026-05-02"),
    ("pedro@correo.com", "Pedro Lara", "300 410 7788", "ANFITRION", "Bogotá", "2026-07-21"),
    ("sofia@correo.com", "Sofía Mejía", "320 118 9034", "ANFITRION", "Medellín", "2026-09-08"),
    ("restringido@correo.com", "Andrés Silva", "311 902 3321", "ANFITRION", "Bogotá", "2026-10-27"),
    # Segunda tanda: anfitriones de la costa y huéspedes que reservan en los alojamientos nuevos
    ("valentina@correo.com", "Valentina Herrera", "3014567821", "ANFITRION", "Cartagena", "2026-01-20"),
    ("julian@correo.com", "Julián Ospina", "3157702418", "ANFITRION", "Santa Marta", "2026-01-28"),
    ("santiago@correo.com", "Santiago Restrepo", "3046613927", "HUESPED", "Medellín", "2026-02-05"),
    ("mariana@correo.com", "Mariana López", "3208854106", "HUESPED", "Bogotá", "2026-02-12"),
    ("camila@correo.com", "Camila Rojas", "3172290345", "HUESPED", "Cali", "2026-03-08"),
]
# Fotos de la demo: viven en frontend/public/alojamientos/ (el sitio las sirve en /alojamientos/), así funcionan sin
# conexión a internet. Son de Wikimedia Commons con licencia libre; el autor y la licencia de cada una están en
# frontend/public/alojamientos/CREDITOS.md.
IMG = "/alojamientos/"


def definir_publicacion(titulo, tipo, ciudad, ubicacion, descripcion, capacidad, precio, limpieza, servicios, reglas, imagenes, **extra):
    return dict(titulo=titulo, tipo=tipo, ciudad=ciudad, ubicacion_textual=ubicacion, descripcion=descripcion, capacidad=capacidad,
                precio_noche=Decimal(precio), tarifa_limpieza=Decimal(limpieza), servicios=servicios, reglas=reglas,
                imagenes=[f"{IMG}{i}.jpg" for i in imagenes], **extra)


PUBLICACIONES = [
    # dueño, fecha de creación, estado final, datos, (acción de moderación, observación)
    ("anfitrion@correo.com", "2026-04-02", "ACTIVA", definir_publicacion(
        "Apartamento con vista a Monserrate", "Apartamento", "Bogotá", "La Candelaria, a 3 cuadras del Chorro de Quevedo",
        "Apartamento luminoso de dos habitaciones con vista a los cerros, cocina equipada y balcón.", 4, 220000, 50000,
        ["Wi-Fi", "Parqueadero", "Cocina", "Agua caliente"], ["No fumar", "Sin fiestas", "Silencio después de las 10 p. m."],
        ["monserrate-vista", "monserrate-sala", "monserrate-habitacion", "monserrate-cocina", "monserrate-bano"], descuento_porcentaje=Decimal(10), descuento_min_noches=7,
        servicios_adicionales=[{"nombre": "Desayuno", "precio": Decimal(25000)}, {"nombre": "Traslado al aeropuerto", "precio": Decimal(70000)}],
    ), None),
    ("anfitrion@correo.com", "2026-05-18", "PAUSADA", definir_publicacion(
        "Cabaña El Roble", "Cabaña", "Guatavita", "Vereda El Roble, km 4", "Cabaña de madera junto al embalse, con chimenea y zona de fogata.",
        5, 310000, 60000, ["Wi-Fi", "Parqueadero", "Cocina"], ["Mascotas pequeñas permitidas"], ["roble-fachada", "roble-chimenea", "roble-habitacion", "roble-cocina", "roble-fogata"]), None),
    ("anfitrion@correo.com", "2026-06-30", "PENDIENTE_REVISION", definir_publicacion(
        "Habitación cerca al centro", "Habitación", "Bogotá", "Calle 19 con carrera 4",
        "Habitación privada con baño, a 10 minutos del centro histórico. Incluye Wi-Fi y agua caliente.", 2, 95000, 20000,
        ["Wi-Fi", "Agua caliente"], ["Llegada desde las 3:00 p. m."], ["centro-edificio", "centro-habitacion", "centro-bano", "centro-escritorio", "centro-calle"]), None),
    ("anfitrion@correo.com", "2026-08-12", "BORRADOR", definir_publicacion(
        "Casa familiar en Villa de Leyva", "Casa", "Villa de Leyva", "Vereda El Roble, a 5 min de la plaza",
        "Casa de dos pisos a 5 minutos de la plaza principal, con patio y zona BBQ.", 6, 280000, 60000,
        ["Wi-Fi", "Parqueadero", "Cocina"], ["No fumar", "Mascotas pequeñas permitidas"], ["leyva-fachada", "leyva-sala", "leyva-habitacion", "leyva-cocina", "leyva-patio"]),
        ("DEVOLVER", "Las fotos no corresponden al alojamiento. Sube fotos reales de la casa.")),
    ("anfitrion@correo.com", "2026-10-05", "BLOQUEADA", definir_publicacion(
        "Loft Chapinero", "Apartamento", "Bogotá", "Chapinero Alto", "Loft moderno con terraza.", 2, 180000, 40000,
        ["Wi-Fi", "TV"], ["No fumar"], ["chapinero-sala", "chapinero-loft", "chapinero-cocina", "chapinero-bano", "chapinero-terraza"]), ("BLOQUEAR", "La dirección publicada no coincide con la del alojamiento.")),
    ("pedro@correo.com", "2026-08-01", "PENDIENTE_REVISION", definir_publicacion(
        "Estudio Usaquén", "Apartamento", "Bogotá", "Usaquén, cerca del parque", "Estudio para dos con cocineta.", 2, 150000, 30000,
        ["Wi-Fi", "Cocina"], ["No fumar"], ["usaquen-estudio", "usaquen-cocineta", "usaquen-bano", "usaquen-plaza", "usaquen-parque"]), None),
    ("sofia@correo.com", "2026-09-15", "ACTIVA", definir_publicacion(
        "Cabaña del Lago", "Cabaña", "Guatapé", "Orilla del embalse, sector La Piedra", "Cabaña con muelle propio y kayak.", 5, 280000, 60000,
        ["Wi-Fi", "Parqueadero", "Cocina"], ["Sin fiestas"], ["lago-sala", "lago-muelle", "lago-exterior", "lago-habitacion", "lago-embalse"]), None),
    ("sofia@correo.com", "2026-10-01", "ACTIVA", definir_publicacion(
        "Casa campestre La Ceja", "Casa", "La Ceja", "Vía La Ceja - La Unión, km 2", "Casa campestre con jardín amplio y BBQ.", 8, 390000, 80000,
        ["Wi-Fi", "Parqueadero", "Cocina", "Piscina"], ["No fumar"], ["ceja-fachada", "ceja-sala", "ceja-habitacion", "ceja-piscina", "ceja-jardin"]), None),
    ("sofia@correo.com", "2026-11-03", "ACTIVA", definir_publicacion(
        "Habitación Laureles", "Habitación", "Medellín", "Laureles, circular 1", "Habitación privada en casa familiar.", 2, 110000, 20000,
        ["Wi-Fi", "Agua caliente"], ["Silencio después de las 10 p. m."], ["laureles-sala", "laureles-habitacion", "laureles-cocina", "laureles-bano", "laureles-barrio"]), None),
    ("restringido@correo.com", "2026-10-28", "ACTIVA", definir_publicacion(
        "Apartamento El Poblado", "Apartamento", "Medellín", "El Poblado",
        "No aparece en búsquedas porque la cuenta del anfitrión está restringida.", 3, 240000, 40000, ["Wi-Fi"], ["No fumar"], ["poblado-sala", "poblado-habitacion", "poblado-cocina", "poblado-bano", "poblado-vista"]), None),
    # ---- Segunda tanda (índices 10 a 19): costa Caribe, Cali, Guatapé, Medellín y Bogotá
    ("valentina@correo.com", "2026-02-10", "ACTIVA", definir_publicacion(
        "Apartamento frente al mar en Bocagrande", "Apartamento", "Cartagena", "Bocagrande, avenida San Martín con calle 6",
        "Apartamento en piso alto con balcón frente al mar Caribe, a una cuadra de la playa. Edificio con piscina y portería.",
        4, 380000, 70000, ["Wi-Fi", "Aire acondicionado", "Piscina", "Cocina", "TV"], ["No fumar", "Sin fiestas", "Llegada desde las 3:00 p. m."],
        ["bocagrande-exterior", "bocagrande-sala", "bocagrande-habitacion", "bocagrande-bano", "bocagrande-playa"],
        descuento_porcentaje=Decimal(10), descuento_min_noches=7,
        servicios_adicionales=[{"nombre": "Kit de playa", "precio": Decimal(40000)}, {"nombre": "Traslado al aeropuerto", "precio": Decimal(60000)}],
    ), None),
    ("valentina@correo.com", "2026-02-20", "ACTIVA", definir_publicacion(
        "Casa colonial en Getsemaní", "Casa", "Cartagena", "Getsemaní, calle del Guerrero",
        "Casa colonial restaurada de tres habitaciones, con patio interior y piscina pequeña, a pasos de la plaza de la Trinidad.",
        6, 650000, 100000, ["Wi-Fi", "Aire acondicionado", "Piscina", "Cocina", "Lavadora"], ["No fumar", "Silencio después de las 11 p. m."],
        ["getsemani-fachada", "getsemani-sala", "getsemani-habitacion", "getsemani-bano", "getsemani-patio"],
        servicios_adicionales=[{"nombre": "Desayuno típico", "precio": Decimal(35000)}],
    ), None),
    ("sofia@correo.com", "2026-03-05", "ACTIVA", definir_publicacion(
        "Habitación en el Centro Histórico de Cartagena", "Habitación", "Cartagena", "Centro amurallado, calle de la Factoría",
        "Habitación privada con baño en una casa colonial dentro de las murallas, con terraza compartida.",
        2, 190000, 30000, ["Wi-Fi", "Aire acondicionado", "Agua caliente"], ["No fumar", "No se admiten visitas"],
        ["murallas-balcon", "murallas-habitacion", "murallas-bano", "murallas-calle", "murallas-vista"],
    ), None),
    ("julian@correo.com", "2026-02-15", "ACTIVA", definir_publicacion(
        "Cabaña en Minca", "Cabaña", "Santa Marta", "Minca, vía a Pozo Azul",
        "Cabaña de madera en la Sierra Nevada, rodeada de bosque, con vista a la bahía de Santa Marta y a 15 minutos a pie de las cascadas.",
        4, 220000, 40000, ["Wi-Fi", "Cocina", "Agua caliente", "Parqueadero"], ["Mascotas pequeñas permitidas", "No hacer fogatas fuera del área señalada"],
        ["minca-vista", "minca-habitacion", "minca-bano", "minca-cascada", "minca-rio"],
        servicios_adicionales=[{"nombre": "Desayuno", "precio": Decimal(25000)}],
    ), None),
    ("julian@correo.com", "2026-03-15", "ACTIVA", definir_publicacion(
        "Apartamento en El Rodadero", "Apartamento", "Santa Marta", "El Rodadero, carrera 1 con calle 9",
        "Apartamento familiar a media cuadra de la playa de El Rodadero, con piscina en el edificio.",
        5, 320000, 60000, ["Wi-Fi", "Aire acondicionado", "Piscina", "Cocina", "TV", "Parqueadero"], ["No fumar", "Sin fiestas"],
        ["rodadero-playa", "rodadero-sala", "rodadero-habitacion", "rodadero-cocina", "rodadero-bahia"],
        descuento_porcentaje=Decimal(8), descuento_min_noches=5,
        servicios_adicionales=[{"nombre": "Kit de playa", "precio": Decimal(35000)}, {"nombre": "Traslado al aeropuerto", "precio": Decimal(50000)}],
    ), None),
    ("pedro@correo.com", "2026-04-08", "ACTIVA", definir_publicacion(
        "Casa en San Antonio", "Casa", "Cali", "Barrio San Antonio, carrera 10 con calle 2",
        "Casa tradicional de dos pisos en el barrio San Antonio, cerca de la capilla y de los restaurantes del barrio.",
        6, 300000, 60000, ["Wi-Fi", "Aire acondicionado", "Cocina", "Lavadora"], ["No fumar", "Silencio después de las 10 p. m."],
        ["sanantonio-fachada", "sanantonio-sala", "sanantonio-habitacion", "sanantonio-cocina", "sanantonio-vista"],
    ), None),
    ("pedro@correo.com", "2026-11-12", "PENDIENTE_REVISION", definir_publicacion(
        "Habitación en Granada", "Habitación", "Cali", "Barrio Granada, cerca de la avenida Sexta",
        "Habitación privada con baño propio en un apartamento tranquilo, a dos cuadras de la zona gastronómica.",
        2, 120000, 25000, ["Wi-Fi", "Aire acondicionado", "Agua caliente"], ["No fumar"],
        ["granada-habitacion", "granada-bano", "granada-cocina", "granada-calle", "granada-avenida"],
    ), None),
    ("sofia@correo.com", "2026-05-20", "PAUSADA", definir_publicacion(
        "Cabaña frente al Peñol", "Cabaña", "Guatapé", "Vía Guatapé - El Peñol, km 3",
        "Cabaña con vista a la Piedra del Peñol y salida directa al embalse.",
        6, 360000, 70000, ["Wi-Fi", "Parqueadero", "Cocina", "TV"], ["Sin fiestas", "Chalecos salvavidas obligatorios en el muelle"],
        ["penol-piedra", "penol-sala", "penol-habitacion", "penol-cocina", "penol-pueblo"],
        servicios_adicionales=[{"nombre": "Paseo en lancha", "precio": Decimal(80000)}],
    ), None),
    ("anfitrion@correo.com", "2026-06-03", "ACTIVA", definir_publicacion(
        "Apartamento en Provenza", "Apartamento", "Medellín", "El Poblado, sector Provenza, carrera 35",
        "Apartamento moderno con balcón, a dos cuadras de los cafés y restaurantes de Provenza.",
        3, 280000, 50000, ["Wi-Fi", "Cocina", "Lavadora", "TV", "Agua caliente"], ["No fumar", "Sin fiestas"],
        ["provenza-sala", "provenza-habitacion", "provenza-cocina", "provenza-barrio", "provenza-vista"],
        descuento_porcentaje=Decimal(12), descuento_min_noches=7,
    ), None),
    ("anfitrion@correo.com", "2026-06-10", "ACTIVA", definir_publicacion(
        "Apartamento en La Macarena", "Apartamento", "Bogotá", "La Macarena, carrera 4A con calle 26",
        "Apartamento de dos habitaciones en el barrio La Macarena, cerca del Museo Nacional y con vista a los cerros.",
        4, 240000, 50000, ["Wi-Fi", "Cocina", "Agua caliente", "TV"], ["No fumar", "Silencio después de las 10 p. m."],
        ["macarena-fachada", "macarena-sala", "macarena-habitacion", "macarena-calle", "macarena-vista"],
        servicios_adicionales=[{"nombre": "Desayuno", "precio": Decimal(22000)}],
    ), None),
    # ---- Tercera tanda (MAL-35, índices 20 a 33): una ACTIVA en cada ciudad que no tenía ninguna, para que ninguna
    # búsqueda por ciudad salga vacía (las 12 de la migración 0006 más Guatavita y Villa de Leyva)
    ("valentina@correo.com", "2026-03-05", "ACTIVA", definir_publicacion(
        "Apartamento frente al mar en San Andrés", "Apartamento", "San Andrés", "Spratt Bight, avenida Colombia",
        "Apartamento con terraza frente a la playa de Spratt Bight y al mar de siete colores, a pocos minutos del muelle "
        "de las lanchas a Johnny Cay.",
        4, 420000, 70000, ["Wi-Fi", "Aire acondicionado", "Cocina", "TV", "Agua caliente"], ["No fumar", "Sin fiestas", "No se permiten mascotas"],
        ["sanandres-playa", "sanandres-sala", "sanandres-habitacion", "sanandres-bano", "sanandres-cayo"],
        descuento_porcentaje=Decimal(10), descuento_min_noches=5,
        servicios_adicionales=[{"nombre": "Tour a Johnny Cay y el Acuario", "precio": Decimal(90000)}],
    ), None),
    ("valentina@correo.com", "2026-01-25", "ACTIVA", definir_publicacion(
        "Casa en El Prado", "Casa", "Barranquilla", "El Prado, carrera 54 con calle 64",
        "Casa republicana de dos pisos en el barrio El Prado, con jardín y terraza, cerca del Museo del Caribe y del "
        "recorrido del Carnaval.",
        8, 350000, 60000, ["Wi-Fi", "Aire acondicionado", "Parqueadero", "Cocina", "Lavadora"], ["No fumar", "Silencio después de las 11 p. m."],
        ["prado-fachada", "prado-sala", "prado-habitacion", "prado-cocina", "prado-barrio"],
    ), None),
    ("julian@correo.com", "2026-03-18", "ACTIVA", definir_publicacion(
        "Apartamento en Cabecera", "Apartamento", "Bucaramanga", "Cabecera del Llano, carrera 35 con calle 48",
        "Apartamento de dos habitaciones en Cabecera, a una cuadra de parques y centros comerciales, con portería las 24 horas.",
        4, 200000, 45000, ["Wi-Fi", "Aire acondicionado", "Cocina", "TV", "Parqueadero"], ["No fumar", "Sin fiestas"],
        ["cabecera-edificio", "cabecera-sala", "cabecera-habitacion", "cabecera-cocina", "cabecera-parque"],
        descuento_porcentaje=Decimal(8), descuento_min_noches=7,
    ), None),
    ("julian@correo.com", "2026-04-08", "ACTIVA", definir_publicacion(
        "Cabaña junto al río Fonce", "Cabaña", "San Gil", "Vereda Ojo de Agua, vía al Páramo",
        "Cabaña de madera a orillas del río Fonce, a diez minutos del parque El Gallineral y de los planes de rafting.",
        5, 240000, 50000, ["Wi-Fi", "Parqueadero", "Cocina", "Agua caliente"], ["No fumar", "Fogatas solo en el área marcada"],
        ["sangil-rio", "sangil-sala", "sangil-habitacion", "sangil-bano", "sangil-vista"],
        servicios_adicionales=[{"nombre": "Traslado al rafting", "precio": Decimal(40000)}],
    ), None),
    ("julian@correo.com", "2026-02-14", "ACTIVA", definir_publicacion(
        "Casa colonial en Barichara", "Casa", "Barichara", "Calle 5 con carrera 7, a dos cuadras del parque principal",
        "Casa de tapia pisada con patio central y vista al cañón del río Suárez, en el centro histórico de Barichara.",
        6, 420000, 70000, ["Wi-Fi", "Cocina", "Agua caliente", "Lavadora"], ["No fumar", "Silencio después de las 10 p. m."],
        ["barichara-calle", "barichara-sala", "barichara-habitacion", "barichara-bano", "barichara-vista"],
        servicios_adicionales=[{"nombre": "Desayuno santandereano", "precio": Decimal(28000)}],
    ), None),
    ("sofia@correo.com", "2026-05-02", "ACTIVA", definir_publicacion(
        "Casa de balcones en Jardín", "Casa", "Jardín", "Calle 9 con carrera 4, frente al parque principal",
        "Casa típica antioqueña de balcones de colores, a media cuadra de la basílica y del parque de Jardín.",
        6, 300000, 60000, ["Wi-Fi", "Cocina", "Agua caliente", "TV"], ["No fumar", "Sin fiestas"],
        ["jardin-balcones", "jardin-sala", "jardin-habitacion", "jardin-cocina", "jardin-basilica"],
    ), None),
    ("sofia@correo.com", "2026-06-12", "ACTIVA", definir_publicacion(
        "Casa con piscina en Santa Fe de Antioquia", "Casa", "Santa Fe de Antioquia", "Barrio Jesús, calle de la Amargura",
        "Casa colonial con piscina y patio de palmas, a pocas cuadras de la plaza mayor y del Puente de Occidente.",
        8, 480000, 80000, ["Wi-Fi", "Aire acondicionado", "Piscina", "Cocina", "Parqueadero"], ["No fumar", "Sin fiestas", "Niños en la piscina con un adulto"],
        ["santafe-fachada", "santafe-sala", "santafe-habitacion", "santafe-bano", "santafe-puente"],
        descuento_porcentaje=Decimal(12), descuento_min_noches=7,
    ), None),
    ("sofia@correo.com", "2026-03-22", "ACTIVA", definir_publicacion(
        "Cabaña cafetera en Salento", "Cabaña", "Salento", "Vereda Palestina, vía al Valle de Cocora",
        "Cabaña en una finca cafetera con vista a las montañas del Quindío, a quince minutos del Valle de Cocora.",
        4, 260000, 50000, ["Wi-Fi", "Parqueadero", "Cocina", "Agua caliente"], ["No fumar", "Sin mascotas"],
        ["salento-cocora", "salento-sala", "salento-habitacion", "salento-bano", "salento-fachada"],
        servicios_adicionales=[{"nombre": "Recorrido por la finca cafetera", "precio": Decimal(45000)}],
    ), None),
    ("pedro@correo.com", "2026-02-26", "ACTIVA", definir_publicacion(
        "Habitación en el centro histórico de Popayán", "Habitación", "Popayán", "Calle 4 con carrera 6, centro histórico",
        "Habitación privada con baño en una casona blanca del centro histórico, a dos cuadras del parque Caldas.",
        2, 110000, 20000, ["Wi-Fi", "Agua caliente", "TV"], ["No fumar", "Silencio después de las 10 p. m."],
        ["popayan-fachada", "popayan-habitacion", "popayan-bano", "popayan-sala", "popayan-tejados"],
    ), None),
    ("pedro@correo.com", "2026-04-20", "ACTIVA", definir_publicacion(
        "Habitación cerca de la Plaza Mayor", "Habitación", "Villa de Leyva", "Calle 12 con carrera 9, a una cuadra de la Plaza Mayor",
        "Habitación con baño privado en una casa colonial, a una cuadra de la Plaza Mayor de Villa de Leyva.",
        2, 150000, 25000, ["Wi-Fi", "Agua caliente"], ["No fumar", "Llegada antes de las 10 p. m."],
        ["leyva2-calle", "leyva2-habitacion", "leyva2-bano", "leyva2-sala", "leyva2-plaza"],
        servicios_adicionales=[{"nombre": "Desayuno boyacense", "precio": Decimal(20000)}],
    ), None),
    ("pedro@correo.com", "2026-05-15", "ACTIVA", definir_publicacion(
        "Cabaña junto al embalse de Tominé", "Cabaña", "Guatavita", "Vereda Potrero Largo, orilla del embalse",
        "Cabaña de madera a la orilla del embalse de Tominé, a diez minutos del pueblo de Guatavita, con chimenea.",
        4, 280000, 50000, ["Wi-Fi", "Parqueadero", "Cocina", "Agua caliente"], ["No fumar", "Sin fiestas"],
        ["tomine-embalse", "tomine-sala", "tomine-habitacion", "tomine-cocina", "tomine-lancha"],
    ), None),
    ("anfitrion@correo.com", "2026-07-08", "ACTIVA", definir_publicacion(
        "Apartamento en Pereira", "Apartamento", "Pereira", "Pinares, avenida Circunvalar con calle 10",
        "Apartamento con balcón y vista a la ciudad, cerca de la avenida Circunvalar y a diez minutos del centro.",
        4, 190000, 40000, ["Wi-Fi", "Cocina", "Lavadora", "TV", "Agua caliente"], ["No fumar", "Sin fiestas"],
        ["pereira-vista", "pereira-sala", "pereira-habitacion", "pereira-cocina", "pereira-plaza"],
    ), None),
    ("anfitrion@correo.com", "2026-08-03", "ACTIVA", definir_publicacion(
        "Apartamento en Chipre", "Apartamento", "Manizales", "Chipre, avenida 12 de Octubre",
        "Apartamento en el barrio Chipre, a pasos del Monumento a los Colonizadores y de la torre de Chipre, con atardeceres "
        "sobre la cordillera.",
        3, 180000, 40000, ["Wi-Fi", "Cocina", "Agua caliente", "TV"], ["No fumar", "Silencio después de las 10 p. m."],
        ["chipre-vista", "chipre-sala", "chipre-habitacion", "chipre-bano", "chipre-torre"],
    ), None),
    ("anfitrion@correo.com", "2026-02-02", "ACTIVA", definir_publicacion(
        "Casa campestre en los Llanos", "Casa", "Villavicencio", "Vereda La Llanerita, vía a Puerto López",
        "Casa campestre con piscina y kiosco, rodeada de llanura, a veinte minutos de Villavicencio.",
        8, 350000, 70000, ["Wi-Fi", "Aire acondicionado", "Piscina", "Parqueadero", "Cocina"], ["No fumar", "Sin música después de las 11 p. m."],
        ["llanos-caballo", "llanos-sala", "llanos-habitacion", "llanos-cocina", "llanos-atardecer"],
        servicios_adicionales=[{"nombre": "Asado llanero", "precio": Decimal(60000)}],
    ), None),
]
# Reservas por el flujo real (cotizar y reservar con el pago simulado). El reloj de la aplicación fija la fecha de
# creación, que es la que usan el tablero y los reportes (RF-D-ADM-05). Octubre y noviembre de 2026 muestran todos
# los estados: COMPLETADA, CONFIRMADA, EN_REVISION y una CANCELADA con devolución parcial.
RESERVAS = [  # índice de la publicación, llegada, salida, huéspedes, creada, (cancelada el, motivo) o None[, correo del huésped]
    (6, "2026-10-10", "2026-10-12", 2, "2026-10-01", None),   # Cabaña del Lago: COMPLETADA
    (7, "2026-10-24", "2026-10-26", 4, "2026-10-05", None),   # Casa campestre La Ceja: COMPLETADA
    (4, "2026-12-10", "2026-12-12", 2, "2026-10-20", None),   # Loft Chapinero: EN_REVISION al bloquearlo
    (6, "2026-12-20", "2026-12-22", 2, "2026-10-25", None),   # Cabaña del Lago: CONFIRMADA
    (0, "2026-11-20", "2026-11-23", 2, "2026-11-02", None),   # Monserrate: CONFIRMADA
    (0, "2026-12-05", "2026-12-09", 3, "2026-11-05", None),   # Monserrate: CONFIRMADA
    (8, "2026-11-15", "2026-11-17", 2, "2026-11-04", ("2026-11-10", "Cambio de planes")),  # Laureles: CANCELADA, 5 días: 50 %
    # ---- Segunda tanda: alojamientos nuevos, creadas de febrero a septiembre de 2026 (octubre y noviembre quedan como
    # estaban). Las que terminan antes del 18 de noviembre de 2026 quedan COMPLETADA; las de diciembre y enero, CONFIRMADA.
    # Pedro Lara no tiene reservas pendientes: las pruebas lo usan como el anfitrión que puede desactivar su cuenta.
    (10, "2026-03-20", "2026-03-24", 2, "2026-03-02", None, "mariana@correo.com"),     # Bocagrande: COMPLETADA
    (10, "2026-06-14", "2026-06-18", 3, "2026-05-10", None, "santiago@correo.com"),    # Bocagrande: COMPLETADA
    (10, "2026-12-26", "2027-01-02", 4, "2026-09-10", None, "santiago@correo.com"),    # Bocagrande: CONFIRMADA (7 noches, 10 %)
    (11, "2026-04-15", "2026-04-19", 5, "2026-04-01", None, "camila@correo.com"),      # Getsemaní: COMPLETADA
    (11, "2026-07-18", "2026-07-22", 4, "2026-07-01", None, "huesped@correo.com"),     # Getsemaní: COMPLETADA
    (11, "2026-12-28", "2027-01-03", 6, "2026-09-15", None, "camila@correo.com"),      # Getsemaní: CONFIRMADA
    (12, "2026-04-02", "2026-04-05", 2, "2026-03-20", None, "mariana@correo.com"),     # Centro Histórico: COMPLETADA
    (12, "2026-06-10", "2026-06-13", 2, "2026-05-05", ("2026-05-20", "Cambio de fechas del viaje"), "camila@correo.com"),  # 21 días: 100 %
    (13, "2026-03-12", "2026-03-15", 2, "2026-02-28", None, "santiago@correo.com"),    # Minca: COMPLETADA
    (13, "2026-08-20", "2026-08-23", 3, "2026-08-05", None, "camila@correo.com"),      # Minca: COMPLETADA
    (13, "2027-01-08", "2027-01-12", 4, "2026-08-25", None, "mariana@correo.com"),     # Minca: CONFIRMADA
    (14, "2026-06-26", "2026-07-01", 5, "2026-06-01", None, "huesped@correo.com"),     # El Rodadero: COMPLETADA (5 noches, 8 %)
    (14, "2026-08-01", "2026-08-05", 4, "2026-07-12", ("2026-07-31", "Se canceló el vuelo"), "mariana@correo.com"),  # 1 día: 0 %
    (14, "2027-01-15", "2027-01-20", 4, "2026-09-20", None, "huesped@correo.com"),     # El Rodadero: CONFIRMADA
    (15, "2026-05-29", "2026-06-01", 4, "2026-05-15", None, "camila@correo.com"),      # San Antonio: COMPLETADA
    (18, "2026-08-07", "2026-08-10", 2, "2026-07-20", None, "santiago@correo.com"),    # Provenza: COMPLETADA
    (18, "2026-12-04", "2026-12-07", 3, "2026-09-25", None, "mariana@correo.com"),     # Provenza: CONFIRMADA
    (18, "2026-12-20", "2026-12-24", 3, "2026-09-28", None, "santiago@correo.com"),    # Provenza: CONFIRMADA
    (19, "2026-07-03", "2026-07-06", 2, "2026-06-20", ("2026-06-29", "Viaje de trabajo aplazado"), "santiago@correo.com"),  # 4 días: 50 %
    (19, "2026-08-14", "2026-08-17", 3, "2026-08-01", None, "mariana@correo.com"),     # La Macarena: COMPLETADA
    (19, "2026-09-18", "2026-09-21", 2, "2026-09-03", None, "huesped@correo.com"),     # La Macarena: COMPLETADA
    # ---- Tercera tanda (MAL-35): reservas en las ciudades nuevas, creadas de febrero a septiembre de 2026. Pedro sigue
    # sin reservas pendientes (las de Popayán y Villa de Leyva ya terminaron).
    (20, "2026-05-08", "2026-05-12", 2, "2026-04-10", None, "mariana@correo.com"),     # San Andrés: COMPLETADA
    (20, "2027-01-22", "2027-01-27", 3, "2026-09-12", None, "camila@correo.com"),      # San Andrés: CONFIRMADA (5 noches, 10 %)
    (21, "2026-02-20", "2026-02-23", 6, "2026-02-05", None, "santiago@correo.com"),    # El Prado: COMPLETADA
    (22, "2026-12-11", "2026-12-14", 2, "2026-09-05", None, "huesped@correo.com"),     # Cabecera: CONFIRMADA
    (23, "2026-07-10", "2026-07-13", 4, "2026-06-15", ("2026-07-05", "Cambio en el itinerario"), "santiago@correo.com"),  # 5 días: 50 %
    (24, "2026-08-28", "2026-08-31", 5, "2026-08-02", None, "camila@correo.com"),      # Barichara: COMPLETADA
    (25, "2026-09-11", "2026-09-14", 3, "2026-08-20", None, "mariana@correo.com"),     # Jardín: COMPLETADA
    (26, "2026-12-30", "2027-01-06", 6, "2026-09-18", None, "huesped@correo.com"),     # Santa Fe: CONFIRMADA (7 noches, 12 %)
    (27, "2026-04-24", "2026-04-27", 2, "2026-04-02", None, "huesped@correo.com"),     # Salento: COMPLETADA
    (28, "2026-04-01", "2026-04-04", 1, "2026-03-10", None, "santiago@correo.com"),    # Popayán, Semana Santa: COMPLETADA
    (29, "2026-06-19", "2026-06-21", 2, "2026-06-01", None, "mariana@correo.com"),     # Villa de Leyva: COMPLETADA
    (31, "2026-12-18", "2026-12-21", 2, "2026-09-22", None, "camila@correo.com"),      # Pereira: CONFIRMADA
    (32, "2026-09-25", "2026-09-28", 2, "2026-09-08", None, "santiago@correo.com"),    # Chipre: COMPLETADA
    (33, "2026-03-27", "2026-03-30", 6, "2026-03-05", None, "camila@correo.com"),      # Llanos: COMPLETADA
]


CORREOS_DEMO = {"admin@inversioneslr.com"} | {u[0] for u in USUARIOS}


def contar_datos_ajenos() -> dict[str, int]:
    """Usuarios, publicaciones y reservas que no salen de esta demostración: lo que --reiniciar borraría de más.
    Una publicación es de la demo si su anfitrión y su título son los de PUBLICACIONES; una reserva, si además coinciden
    el huésped y las fechas de RESERVAS."""
    Usuario = apps.get_model("identidad", "Usuario")
    Publicacion = apps.get_model("catalogo", "Publicacion")
    Reserva = apps.get_model("reservas", "Reserva")
    pubs_demo = {(dueno, d["titulo"]) for dueno, _, _, d, _ in PUBLICACIONES}
    res_demo = {(PUBLICACIONES[i][3]["titulo"], llegada, salida, (quien or ["huesped@correo.com"])[0])
                for i, llegada, salida, _, _, _, *quien in RESERVAS}
    ajenas = [pid for pid, dueno, titulo in Publicacion.objects.values_list("id", "anfitrion__correo", "titulo")
              if (dueno, titulo) not in pubs_demo]
    reservas_ajenas = sum(
        1 for titulo, llegada, salida, correo in Reserva.objects.values_list("publicacion__titulo", "fecha_llegada", "fecha_salida", "huesped__correo")
        if (titulo, llegada.isoformat(), salida.isoformat(), correo) not in res_demo)
    return {"usuarios": Usuario.objects.exclude(correo__in=CORREOS_DEMO).count(), "publicaciones": len(ajenas),
            "reservas": reservas_ajenas}


class Command(BaseCommand):
    help = "Carga cuentas, publicaciones, revisiones, una restricción y reservas de demostración."

    def add_arguments(self, parser):
        parser.add_argument("--reiniciar", action="store_true",
                            help="VACÍA TODA LA BASE (solo con DJANGO_DEBUG=1) y vuelve a cargar los datos. Pide escribir REINICIAR.")
        parser.add_argument("--si", action="store_true", help="Con --reiniciar: no pide la confirmación.")

    def handle(self, *args, reiniciar=False, si=False, **_):
        Usuario = apps.get_model("identidad", "Usuario")
        if reiniciar:
            # evento_auditoria, reserva y pago tienen un trigger que rechaza TRUNCATE (RNF-E-CON-01). flush vacía
            # la base con TRUNCATE, así que solo en desarrollo se apagan esos triggers mientras corre.
            if not settings.DEBUG:
                raise CommandError("--reiniciar solo se permite en desarrollo (DJANGO_DEBUG=1).")
            self._confirmar_reinicio(si)
            with permitir_vaciado():
                call_command("flush", interactive=False, verbosity=0)
        # Catálogos fijos (la misma carga de la migración; no duplica datos)
        import_module("apps.catalogo.migrations.0002_catalogos_iniciales").cargar(apps, None)
        import_module("apps.catalogo.migrations.0006_mas_ciudades").agregar(apps, None)
        if not reiniciar and Usuario.objects.filter(correo="admin@inversioneslr.com").exists():
            self.stdout.write(self.style.WARNING("Los datos de demostración ya existen. Usa --reiniciar para vaciar la base y cargarlos de nuevo."))
            return
        with transaction.atomic():
            self._cargar_datos()
        self.stdout.write(self.style.SUCCESS("Datos de demostración cargados. Contraseña de todas las cuentas: Clave1234"))

    def _confirmar_reinicio(self, si: bool) -> None:
        """Muestra qué base se va a vaciar y cuántos datos que no son de la demostración se pierden; sin --si, exige
        escribir REINICIAR. Cualquier otra respuesta (o no poder preguntar) cancela sin tocar la base."""
        ajena = contar_datos_ajenos()
        b = connection.settings_dict
        self.stdout.write(self.style.WARNING(
            f"--reiniciar VACÍA TODA LA BASE {b.get('NAME')} en {b.get('HOST') or 'localhost'}:{b.get('PORT') or 5432}.\n"
            f"Se borrarán {ajena['usuarios']} usuarios, {ajena['publicaciones']} publicaciones y {ajena['reservas']} reservas "
            f"que NO son de la demostración (además de todos los datos de la demostración)."))
        if si:
            return
        try:
            respuesta = self.leer_respuesta("Escribe REINICIAR para continuar: ")
        except EOFError:
            respuesta = ""
        if respuesta.strip() != "REINICIAR":
            raise CommandError("Cancelado: la base no se tocó.")

    @staticmethod
    def leer_respuesta(pregunta: str) -> str:
        return input(pregunta)

    def _cargar_datos(self):
        Usuario = apps.get_model("identidad", "Usuario")
        Publicacion = apps.get_model("catalogo", "Publicacion")
        Revision = apps.get_model("catalogo", "RevisionPublicacion")
        cat = catalogo.listar_catalogos()
        ciudad = {c["nombre"]: c["id"] for c in cat["ciudades"]}
        tipo = {t["nombre"]: t["id"] for t in cat["tipos"]}
        servicio = {s["nombre"]: s["id"] for s in cat["servicios"]}
        politica = apps.get_model("catalogo", "PoliticaCancelacion").objects.get(nombre="Moderada").id

        admin = Usuario.objects.create_user(
            correo="admin@inversioneslr.com", password=CLAVE, nombre_completo="Admin LR", telefono="601 555 0100",
            rol="ADMINISTRADOR", ciudad="Bogotá", autorizacion_datos=timezone.now(),
        )
        # Tarifa inicial del 10 %: la fija el administrador (tarifa_servicio.administrador_id NOT NULL)
        reservas.asegurar_tarifa_inicial(admin)
        cuentas = {"admin@inversioneslr.com": admin}
        fechas = {"admin@inversioneslr.com": "2026-01-10"}
        for correo, nombre, tel, rol, ciu, registro in USUARIOS:
            datos = identidad.registrar_usuario(nombre_completo=nombre, correo=correo, telefono=tel, password=CLAVE, rol=rol,
                                        acepta_datos=True, ciudad=ciu)
            cuentas[correo] = Usuario.objects.get(pk=datos.id)
            fechas[correo] = registro
        for correo, f in fechas.items():
            momento = timezone.make_aware(datetime.fromisoformat(f + "T10:00:00"))
            Usuario.objects.filter(correo=correo).update(fecha_registro=momento, autorizacion_datos=momento)

        creadas, por_bloquear = [], []
        for dueno, creada, estado, d, moderacion in PUBLICACIONES:
            entrada = {**{k: v for k, v in d.items() if k not in ("tipo", "ciudad", "servicios")},
                       "ciudad": ciudad[d["ciudad"]], "tipo_alojamiento": tipo[d["tipo"]], "politica": politica,
                       "servicios": [servicio[s] for s in d["servicios"]]}
            p = catalogo.crear_publicacion(cuentas[dueno], entrada)
            momento = timezone.make_aware(datetime.fromisoformat(creada + "T09:00:00"))
            creadas.append(p.id)
            if estado != "BORRADOR" or moderacion:
                catalogo.cambiar_estado(cuentas[dueno], p.id, "PENDIENTE_REVISION")
            if estado in ("ACTIVA", "PAUSADA", "BLOQUEADA"):
                catalogo.revisar_publicacion(admin, p.id, "APROBAR", None)
            if estado == "PAUSADA":
                catalogo.cambiar_estado(cuentas[dueno], p.id, "PAUSADA")
            if moderacion and moderacion[0] == "DEVOLVER":
                catalogo.revisar_publicacion(admin, p.id, "DEVOLVER", moderacion[1])
            if moderacion and moderacion[0] == "BLOQUEAR":  # se bloquea después de reservar (queda EN_REVISION)
                por_bloquear.append((p.id, moderacion[1]))
            Publicacion.objects.filter(pk=p.id).update(creada=momento)
            Revision.objects.filter(publicacion_id=p.id).update(fecha=momento + timedelta(days=1))

        # Fechas no disponibles de ejemplo en el primer alojamiento
        reservas.modificar_calendario(cuentas["anfitrion@correo.com"], creadas[0], date(2026, 12, 12), date(2026, 12, 15), "NO_DISPONIBLE")

        huesped = cuentas["huesped@correo.com"]
        reloj_anterior = reloj._fijo  # se restaura al final (las pruebas pueden fijar "hoy" antes de cargar)
        try:
            # La demostración siempre paga con el adaptador simulado, aunque haya STRIPE_SECRET_KEY en el entorno
            simulado = override_settings(STRIPE_SECRET_KEY="")
            simulado.enable()
            for i, llegada, salida, huespedes, creada, cancelacion, *quien in RESERVAS:
                h = cuentas[quien[0]] if quien else huesped
                reloj.fijar_fecha_hora(timezone.make_aware(datetime.fromisoformat(creada + "T10:00:00")))
                cot = reservas.cotizar_estancia(h, creadas[i], date.fromisoformat(llegada), date.fromisoformat(salida), huespedes)
                r, _ = reservas.reservar_alojamiento(h, cot.id, uuid.uuid4(), "simulado")
                if cancelacion:
                    reloj.fijar_fecha_hora(timezone.make_aware(datetime.fromisoformat(cancelacion[0] + "T10:00:00")))
                    reservas.cancelar_reserva(h, r["id"], cancelacion[1])
        finally:
            simulado.disable()
            reloj.fijar_fecha_hora(reloj_anterior)
        # Con la fecha real: bloquear (sus reservas futuras pasan a EN_REVISION) y completar las que ya terminaron
        for pid, motivo in por_bloquear:
            catalogo.bloquear_publicacion(admin, pid, motivo)
        reservas.completar_reservas_vencidas()

        identidad.restringir_usuario(admin, cuentas["restringido@correo.com"].id,
                             "Reportes de huéspedes por cobros por fuera de la plataforma.",
                             timezone.make_aware(datetime(2026, 12, 31, 23, 59)))
