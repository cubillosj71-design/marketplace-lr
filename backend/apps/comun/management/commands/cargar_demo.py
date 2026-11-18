"""Carga los datos de demostración del prototipo (mismas cuentas y publicaciones del frontend).

Uso: python manage.py cargar_demo [--reiniciar]
Contraseña de todas las cuentas: Clave1234

Usa las interfaces públicas de cada servicio. Solo para ajustar las fechas de creación
(para que los reportes tengan datos repartidos en el año) toca las tablas con apps.get_model.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from importlib import import_module

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from apps.catalogo import services as catalogo
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
IMG = "https://placehold.co/800x600?text="


def pub(titulo, tipo, ciudad, ubicacion, descripcion, capacidad, precio, limpieza, servicios, reglas, imagenes, **extra):
    return dict(titulo=titulo, tipo=tipo, ciudad=ciudad, ubicacion_textual=ubicacion, descripcion=descripcion, capacidad=capacidad,
                precio_noche=Decimal(precio), tarifa_limpieza=Decimal(limpieza), servicios=servicios, reglas=reglas,
                imagenes=[IMG + i.replace(" ", "+") for i in imagenes], **extra)


PUBLICACIONES = [
    # dueño, fecha de creación, estado final, datos, (acción de moderación, observación)
    ("anfitrion@correo.com", "2026-04-02", "ACTIVA", pub(
        "Apartamento con vista a Monserrate", "Apartamento", "Bogotá", "La Candelaria, a 3 cuadras del Chorro de Quevedo",
        "Apartamento luminoso de dos habitaciones con vista a los cerros, cocina equipada y balcón.", 4, 220000, 50000,
        ["Wi-Fi", "Parqueadero", "Cocina", "Agua caliente"], ["No fumar", "Sin fiestas", "Silencio después de las 10 p. m."],
        ["Sala", "Habitación", "Vista"], descuento_porcentaje=Decimal(10), descuento_min_noches=7,
        servicios_adicionales=[{"nombre": "Desayuno", "precio": Decimal(25000)}, {"nombre": "Traslado al aeropuerto", "precio": Decimal(70000)}],
    ), None),
    ("anfitrion@correo.com", "2026-05-18", "PAUSADA", pub(
        "Cabaña El Roble", "Cabaña", "Guatavita", "Vereda El Roble, km 4", "Cabaña de madera junto al embalse, con chimenea y zona de fogata.",
        5, 310000, 60000, ["Wi-Fi", "Parqueadero", "Cocina"], ["Mascotas pequeñas permitidas"], ["Fachada", "Chimenea"]), None),
    ("anfitrion@correo.com", "2026-06-30", "PENDIENTE_REVISION", pub(
        "Habitación cerca al centro", "Habitación", "Bogotá", "Calle 19 con carrera 4",
        "Habitación privada con baño, a 10 minutos del centro histórico. Incluye Wi-Fi y agua caliente.", 2, 95000, 20000,
        ["Wi-Fi", "Agua caliente"], ["Llegada desde las 3:00 p. m."], ["Habitación", "Baño", "Escritorio", "Edificio"]), None),
    ("anfitrion@correo.com", "2026-08-12", "BORRADOR", pub(
        "Casa familiar en Villa de Leyva", "Casa", "Villa de Leyva", "Vereda El Roble, a 5 min de la plaza",
        "Casa de dos pisos a 5 minutos de la plaza principal, con patio y zona BBQ.", 6, 280000, 60000,
        ["Wi-Fi", "Parqueadero", "Cocina"], ["No fumar", "Mascotas pequeñas permitidas"], ["Fachada"]),
        ("DEVOLVER", "Las fotos no corresponden al alojamiento. Sube fotos reales de la casa.")),
    ("anfitrion@correo.com", "2026-10-05", "BLOQUEADA", pub(
        "Loft Chapinero", "Apartamento", "Bogotá", "Chapinero Alto", "Loft moderno con terraza.", 2, 180000, 40000,
        ["Wi-Fi", "TV"], ["No fumar"], ["Loft"]), ("BLOQUEAR", "La dirección publicada no coincide con la del alojamiento.")),
    ("pedro@correo.com", "2026-08-01", "PENDIENTE_REVISION", pub(
        "Estudio Usaquén", "Apartamento", "Bogotá", "Usaquén, cerca del parque", "Estudio para dos con cocineta.", 2, 150000, 30000,
        ["Wi-Fi", "Cocina"], ["No fumar"], ["Estudio", "Cocineta"]), None),
    ("sofia@correo.com", "2026-09-15", "ACTIVA", pub(
        "Cabaña del Lago", "Cabaña", "Guatapé", "Orilla del embalse, sector La Piedra", "Cabaña con muelle propio y kayak.", 5, 280000, 60000,
        ["Wi-Fi", "Parqueadero", "Cocina"], ["Sin fiestas"], ["Muelle", "Sala"]), None),
    ("sofia@correo.com", "2026-10-01", "ACTIVA", pub(
        "Casa campestre La Ceja", "Casa", "La Ceja", "Vía La Ceja - La Unión, km 2", "Casa campestre con jardín amplio y BBQ.", 8, 390000, 80000,
        ["Wi-Fi", "Parqueadero", "Cocina", "Piscina"], ["No fumar"], ["Jardín", "Piscina"]), None),
    ("sofia@correo.com", "2026-11-03", "ACTIVA", pub(
        "Habitación Laureles", "Habitación", "Medellín", "Laureles, circular 1", "Habitación privada en casa familiar.", 2, 110000, 20000,
        ["Wi-Fi", "Agua caliente"], ["Silencio después de las 10 p. m."], ["Habitación"]), None),
    ("restringido@correo.com", "2026-10-28", "ACTIVA", pub(
        "Apartamento El Poblado", "Apartamento", "Medellín", "El Poblado",
        "No aparece en búsquedas porque la cuenta del anfitrión está restringida.", 3, 240000, 40000, ["Wi-Fi"], ["No fumar"], ["Sala"]), None),
]
RESERVAS = [  # índice de la publicación, llegada, salida, huéspedes
    (0, "2026-11-20", "2026-11-23", 2), (0, "2026-12-05", "2026-12-09", 3), (6, "2026-12-20", "2026-12-22", 2),
]


class Command(BaseCommand):
    help = "Carga cuentas, publicaciones, revisiones, una restricción y reservas de demostración."

    def add_arguments(self, parser):
        parser.add_argument("--reiniciar", action="store_true", help="Vacía toda la base (solo desarrollo) y vuelve a cargar los datos.")

    def handle(self, *args, reiniciar=False, **_):
        Usuario = apps.get_model("identidad", "Usuario")
        if reiniciar:
            # El registro de auditoría es de solo inserción (RNF-E-CON-01): un trigger rechaza UPDATE, DELETE
            # y TRUNCATE. flush vacía la base con TRUNCATE, así que solo en desarrollo se apaga el trigger de
            # vaciado mientras corre y se vuelve a encender al terminar, falle o no.
            if not settings.DEBUG:
                raise CommandError("--reiniciar solo se permite en desarrollo (DJANGO_DEBUG=1).")
            with connection.cursor() as c:
                c.execute("ALTER TABLE evento_auditoria DISABLE TRIGGER evento_auditoria_sin_vaciar")
            try:
                call_command("flush", interactive=False, verbosity=0)
            finally:
                with connection.cursor() as c:
                    c.execute("ALTER TABLE evento_auditoria ENABLE TRIGGER evento_auditoria_sin_vaciar")
        # Catálogos fijos y tarifa inicial (las mismas cargas de las migraciones; no duplican datos)
        for modulo in ("apps.catalogo.migrations.0002_catalogos_iniciales", "apps.reservas.migrations.0002_tarifa_inicial"):
            import_module(modulo).cargar(apps, None)
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
        cat = catalogo.catalogos()
        ciudad = {c["nombre"]: c["id"] for c in cat["ciudades"]}
        tipo = {t["nombre"]: t["id"] for t in cat["tipos"]}
        servicio = {s["nombre"]: s["id"] for s in cat["servicios"]}
        politica = apps.get_model("catalogo", "PoliticaCancelacion").objects.get(nombre="Moderada").id

        admin = Usuario.objects.create_user(
            correo="admin@inversioneslr.com", password=CLAVE, nombre_completo="Admin LR", telefono="601 555 0100",
            rol="ADMINISTRADOR", ciudad="Bogotá", autorizacion_datos=timezone.now(),
        )
        cuentas = {"admin@inversioneslr.com": admin}
        fechas = {"admin@inversioneslr.com": "2026-01-10"}
        for correo, nombre, tel, rol, ciu, registro in USUARIOS:
            datos = identidad.registrar(nombre_completo=nombre, correo=correo, telefono=tel, password=CLAVE, rol=rol,
                                        acepta_datos=True, ciudad=ciu)
            cuentas[correo] = Usuario.objects.get(pk=datos.id)
            fechas[correo] = registro
        for correo, f in fechas.items():
            momento = timezone.make_aware(datetime.fromisoformat(f + "T10:00:00"))
            Usuario.objects.filter(correo=correo).update(fecha_registro=momento, autorizacion_datos=momento)

        creadas = []
        for dueno, creada, estado, d, moderacion in PUBLICACIONES:
            entrada = {**{k: v for k, v in d.items() if k not in ("tipo", "ciudad", "servicios")},
                       "ciudad": ciudad[d["ciudad"]], "tipo_alojamiento": tipo[d["tipo"]], "politica": politica,
                       "servicios": [servicio[s] for s in d["servicios"]]}
            p = catalogo.crear(cuentas[dueno], entrada)
            momento = timezone.make_aware(datetime.fromisoformat(creada + "T09:00:00"))
            creadas.append(p.id)
            if estado != "BORRADOR" or moderacion:
                catalogo.cambiar_estado(cuentas[dueno], p.id, "PENDIENTE_REVISION")
            if estado in ("ACTIVA", "PAUSADA", "BLOQUEADA"):
                catalogo.revisar(admin, p.id, "APROBAR", None)
            if estado == "PAUSADA":
                catalogo.cambiar_estado(cuentas[dueno], p.id, "PAUSADA")
            if moderacion and moderacion[0] == "DEVOLVER":
                catalogo.revisar(admin, p.id, "DEVOLVER", moderacion[1])
            if moderacion and moderacion[0] == "BLOQUEAR":
                catalogo.bloquear(admin, p.id, moderacion[1])
            Publicacion.objects.filter(pk=p.id).update(creada=momento)
            Revision.objects.filter(publicacion_id=p.id).update(fecha=momento + timedelta(days=1))

        # Fechas no disponibles de ejemplo en el primer alojamiento
        catalogo.modificar_calendario(cuentas["anfitrion@correo.com"], creadas[0], date(2026, 12, 12), date(2026, 12, 15), "NO_DISPONIBLE")

        for i, llegada, salida, huespedes in RESERVAS:
            reservas.crear_reserva_confirmada(
                cuentas["huesped@correo.com"].id, catalogo.resumen_publicacion(creadas[i]),
                date.fromisoformat(llegada), date.fromisoformat(salida), huespedes,
            )

        identidad.restringir(admin, cuentas["restringido@correo.com"].id,
                             "Reportes de huéspedes por cobros por fuera de la plataforma.",
                             timezone.make_aware(datetime(2026, 12, 31, 23, 59)))
