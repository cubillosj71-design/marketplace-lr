"""Carga los datos de demostración del prototipo (mismas cuentas y publicaciones del frontend).

Uso: python manage.py cargar_demo [--reiniciar]
Contraseña de todas las cuentas: Clave1234

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
from django.db import transaction
from django.test import override_settings
from django.utils import timezone

from apps.catalogo import services as catalogo
from apps.comun import reloj
from apps.comun.bd import vaciado_permitido
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
]
# Fotos de la demo: viven en frontend/public/alojamientos/ (el sitio las sirve en /alojamientos/), así funcionan sin
# conexión a internet. Son de Wikimedia Commons con licencia libre; el autor y la licencia de cada una están en
# frontend/public/alojamientos/CREDITOS.md.
IMG = "/alojamientos/"


def pub(titulo, tipo, ciudad, ubicacion, descripcion, capacidad, precio, limpieza, servicios, reglas, imagenes, **extra):
    return dict(titulo=titulo, tipo=tipo, ciudad=ciudad, ubicacion_textual=ubicacion, descripcion=descripcion, capacidad=capacidad,
                precio_noche=Decimal(precio), tarifa_limpieza=Decimal(limpieza), servicios=servicios, reglas=reglas,
                imagenes=[f"{IMG}{i}.jpg" for i in imagenes], **extra)


PUBLICACIONES = [
    # dueño, fecha de creación, estado final, datos, (acción de moderación, observación)
    ("anfitrion@correo.com", "2026-04-02", "ACTIVA", pub(
        "Apartamento con vista a Monserrate", "Apartamento", "Bogotá", "La Candelaria, a 3 cuadras del Chorro de Quevedo",
        "Apartamento luminoso de dos habitaciones con vista a los cerros, cocina equipada y balcón.", 4, 220000, 50000,
        ["Wi-Fi", "Parqueadero", "Cocina", "Agua caliente"], ["No fumar", "Sin fiestas", "Silencio después de las 10 p. m."],
        ["monserrate-sala", "monserrate-vista", "monserrate-habitacion", "monserrate-cocina", "monserrate-bano"], descuento_porcentaje=Decimal(10), descuento_min_noches=7,
        servicios_adicionales=[{"nombre": "Desayuno", "precio": Decimal(25000)}, {"nombre": "Traslado al aeropuerto", "precio": Decimal(70000)}],
    ), None),
    ("anfitrion@correo.com", "2026-05-18", "PAUSADA", pub(
        "Cabaña El Roble", "Cabaña", "Guatavita", "Vereda El Roble, km 4", "Cabaña de madera junto al embalse, con chimenea y zona de fogata.",
        5, 310000, 60000, ["Wi-Fi", "Parqueadero", "Cocina"], ["Mascotas pequeñas permitidas"], ["roble-fachada", "roble-chimenea", "roble-habitacion", "roble-cocina", "roble-fogata"]), None),
    ("anfitrion@correo.com", "2026-06-30", "PENDIENTE_REVISION", pub(
        "Habitación cerca al centro", "Habitación", "Bogotá", "Calle 19 con carrera 4",
        "Habitación privada con baño, a 10 minutos del centro histórico. Incluye Wi-Fi y agua caliente.", 2, 95000, 20000,
        ["Wi-Fi", "Agua caliente"], ["Llegada desde las 3:00 p. m."], ["centro-edificio", "centro-habitacion", "centro-bano", "centro-escritorio", "centro-calle"]), None),
    ("anfitrion@correo.com", "2026-08-12", "BORRADOR", pub(
        "Casa familiar en Villa de Leyva", "Casa", "Villa de Leyva", "Vereda El Roble, a 5 min de la plaza",
        "Casa de dos pisos a 5 minutos de la plaza principal, con patio y zona BBQ.", 6, 280000, 60000,
        ["Wi-Fi", "Parqueadero", "Cocina"], ["No fumar", "Mascotas pequeñas permitidas"], ["leyva-fachada", "leyva-sala", "leyva-habitacion", "leyva-cocina", "leyva-patio"]),
        ("DEVOLVER", "Las fotos no corresponden al alojamiento. Sube fotos reales de la casa.")),
    ("anfitrion@correo.com", "2026-10-05", "BLOQUEADA", pub(
        "Loft Chapinero", "Apartamento", "Bogotá", "Chapinero Alto", "Loft moderno con terraza.", 2, 180000, 40000,
        ["Wi-Fi", "TV"], ["No fumar"], ["chapinero-sala", "chapinero-loft", "chapinero-cocina", "chapinero-bano", "chapinero-terraza"]), ("BLOQUEAR", "La dirección publicada no coincide con la del alojamiento.")),
    ("pedro@correo.com", "2026-08-01", "PENDIENTE_REVISION", pub(
        "Estudio Usaquén", "Apartamento", "Bogotá", "Usaquén, cerca del parque", "Estudio para dos con cocineta.", 2, 150000, 30000,
        ["Wi-Fi", "Cocina"], ["No fumar"], ["usaquen-estudio", "usaquen-cocineta", "usaquen-bano", "usaquen-plaza", "usaquen-parque"]), None),
    ("sofia@correo.com", "2026-09-15", "ACTIVA", pub(
        "Cabaña del Lago", "Cabaña", "Guatapé", "Orilla del embalse, sector La Piedra", "Cabaña con muelle propio y kayak.", 5, 280000, 60000,
        ["Wi-Fi", "Parqueadero", "Cocina"], ["Sin fiestas"], ["lago-sala", "lago-muelle", "lago-exterior", "lago-habitacion", "lago-kayak"]), None),
    ("sofia@correo.com", "2026-10-01", "ACTIVA", pub(
        "Casa campestre La Ceja", "Casa", "La Ceja", "Vía La Ceja - La Unión, km 2", "Casa campestre con jardín amplio y BBQ.", 8, 390000, 80000,
        ["Wi-Fi", "Parqueadero", "Cocina", "Piscina"], ["No fumar"], ["ceja-fachada", "ceja-sala", "ceja-habitacion", "ceja-piscina", "ceja-jardin"]), None),
    ("sofia@correo.com", "2026-11-03", "ACTIVA", pub(
        "Habitación Laureles", "Habitación", "Medellín", "Laureles, circular 1", "Habitación privada en casa familiar.", 2, 110000, 20000,
        ["Wi-Fi", "Agua caliente"], ["Silencio después de las 10 p. m."], ["laureles-sala", "laureles-habitacion", "laureles-cocina", "laureles-bano", "laureles-barrio"]), None),
    ("restringido@correo.com", "2026-10-28", "ACTIVA", pub(
        "Apartamento El Poblado", "Apartamento", "Medellín", "El Poblado",
        "No aparece en búsquedas porque la cuenta del anfitrión está restringida.", 3, 240000, 40000, ["Wi-Fi"], ["No fumar"], ["poblado-sala", "poblado-habitacion", "poblado-cocina", "poblado-bano", "poblado-vista"]), None),
]
# Reservas por el flujo real (cotizar y reservar con el pago simulado). El reloj de la aplicación fija la fecha de
# creación, que es la que usan el tablero y los reportes (RF-D-ADM-05). Octubre y noviembre de 2026 muestran todos
# los estados: COMPLETADA, CONFIRMADA, EN_REVISION y una CANCELADA con devolución parcial.
RESERVAS = [  # índice de la publicación, llegada, salida, huéspedes, creada, (cancelada el, motivo) o None
    (6, "2026-10-10", "2026-10-12", 2, "2026-10-01", None),   # Cabaña del Lago: COMPLETADA
    (7, "2026-10-24", "2026-10-26", 4, "2026-10-05", None),   # Casa campestre La Ceja: COMPLETADA
    (4, "2026-12-10", "2026-12-12", 2, "2026-10-20", None),   # Loft Chapinero: EN_REVISION al bloquearlo
    (6, "2026-12-20", "2026-12-22", 2, "2026-10-25", None),   # Cabaña del Lago: CONFIRMADA
    (0, "2026-11-20", "2026-11-23", 2, "2026-11-02", None),   # Monserrate: CONFIRMADA
    (0, "2026-12-05", "2026-12-09", 3, "2026-11-05", None),   # Monserrate: CONFIRMADA
    (8, "2026-11-15", "2026-11-17", 2, "2026-11-04", ("2026-11-10", "Cambio de planes")),  # Laureles: CANCELADA, 5 días: 50 %
]


class Command(BaseCommand):
    help = "Carga cuentas, publicaciones, revisiones, una restricción y reservas de demostración."

    def add_arguments(self, parser):
        parser.add_argument("--reiniciar", action="store_true", help="Vacía toda la base (solo desarrollo) y vuelve a cargar los datos.")

    def handle(self, *args, reiniciar=False, **_):
        Usuario = apps.get_model("identidad", "Usuario")
        if reiniciar:
            # evento_auditoria, reserva y pago tienen un trigger que rechaza TRUNCATE (RNF-E-CON-01). flush vacía
            # la base con TRUNCATE, así que solo en desarrollo se apagan esos triggers mientras corre.
            if not settings.DEBUG:
                raise CommandError("--reiniciar solo se permite en desarrollo (DJANGO_DEBUG=1).")
            with vaciado_permitido():
                call_command("flush", interactive=False, verbosity=0)
        # Catálogos fijos (la misma carga de la migración; no duplica datos)
        import_module("apps.catalogo.migrations.0002_catalogos_iniciales").cargar(apps, None)
        if not reiniciar and Usuario.objects.filter(correo="admin@inversioneslr.com").exists():
            self.stdout.write(self.style.WARNING("Los datos de demostración ya existen. Usa --reiniciar para vaciar la base y cargarlos de nuevo."))
            return
        with transaction.atomic():
            self._cargar()
        self.stdout.write(self.style.SUCCESS("Datos de demostración cargados. Contraseña de todas las cuentas: Clave1234"))

    def _cargar(self):
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
            for i, llegada, salida, huespedes, creada, cancelacion in RESERVAS:
                reloj.fijar(timezone.make_aware(datetime.fromisoformat(creada + "T10:00:00")))
                cot = reservas.cotizar_estancia(huesped, creadas[i], date.fromisoformat(llegada), date.fromisoformat(salida), huespedes)
                r, _ = reservas.reservar_alojamiento(huesped, cot.id, uuid.uuid4(), "simulado")
                if cancelacion:
                    reloj.fijar(timezone.make_aware(datetime.fromisoformat(cancelacion[0] + "T10:00:00")))
                    reservas.cancelar_reserva(huesped, r["id"], cancelacion[1])
        finally:
            simulado.disable()
            reloj.fijar(reloj_anterior)
        # Con la fecha real: bloquear (sus reservas futuras pasan a EN_REVISION) y completar las que ya terminaron
        for pid, motivo in por_bloquear:
            catalogo.bloquear_publicacion(admin, pid, motivo)
        reservas.completar_reservas_vencidas()

        identidad.restringir_usuario(admin, cuentas["restringido@correo.com"].id,
                             "Reportes de huéspedes por cobros por fuera de la plataforma.",
                             timezone.make_aware(datetime(2026, 12, 31, 23, 59)))
