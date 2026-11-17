"""Catálogos fijos del MVP: ciudades, tipos de alojamiento, servicios incluidos y la política Moderada."""

from decimal import Decimal

from django.db import migrations

CIUDADES = [
    ("Bogotá", "Bogotá D. C."), ("Medellín", "Antioquia"), ("Cartagena", "Bolívar"), ("Santa Marta", "Magdalena"),
    ("Cali", "Valle del Cauca"), ("Guatapé", "Antioquia"), ("Guatavita", "Cundinamarca"),
    ("Villa de Leyva", "Boyacá"), ("La Ceja", "Antioquia"),
]
TIPOS = ["Apartamento", "Casa", "Habitación", "Cabaña"]
SERVICIOS = ["Wi-Fi", "Parqueadero", "Cocina", "TV", "Agua caliente", "Aire acondicionado", "Piscina", "Lavadora"]
# Política Moderada (SRS): 7 días o más 100 %, de 2 a 6 días 50 %, menos de 2 días 0 %
TRAMOS = [(7, None, Decimal("100")), (2, 6, Decimal("50")), (0, 1, Decimal("0"))]


def cargar(apps, schema_editor):
    Ciudad = apps.get_model("catalogo", "Ciudad")
    TipoAlojamiento = apps.get_model("catalogo", "TipoAlojamiento")
    Servicio = apps.get_model("catalogo", "Servicio")
    PoliticaCancelacion = apps.get_model("catalogo", "PoliticaCancelacion")
    TramoPolitica = apps.get_model("catalogo", "TramoPolitica")
    for nombre, depto in CIUDADES:
        Ciudad.objects.get_or_create(nombre=nombre, departamento=depto)
    for nombre in TIPOS:
        TipoAlojamiento.objects.get_or_create(nombre=nombre)
    for nombre in SERVICIOS:
        Servicio.objects.get_or_create(nombre=nombre)
    moderada, creada = PoliticaCancelacion.objects.get_or_create(
        nombre="Moderada",
        defaults={"descripcion": "Devolución según los días que falten para la llegada.", "activa": True},
    )
    if creada:
        for minimos, maximos, pct in TRAMOS:
            TramoPolitica.objects.create(politica=moderada, dias_minimos=minimos, dias_maximos=maximos, porcentaje_devolucion=pct)


class Migration(migrations.Migration):
    dependencies = [("catalogo", "0001_initial")]
    operations = [migrations.RunPython(cargar, migrations.RunPython.noop)]
