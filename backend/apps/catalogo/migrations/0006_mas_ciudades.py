"""MAL-35: 12 ciudades más para la búsqueda (21 en total con las 9 de la 0002).

Idempotente: get_or_create por nombre y departamento, así que no repite las que ya existan. La reversa quita solo
estas ciudades y solo si ninguna publicación las usa (publicacion.ciudad es PROTECT)."""

from django.db import migrations

CIUDADES_NUEVAS = [
    ("San Andrés", "San Andrés y Providencia"), ("Barranquilla", "Atlántico"), ("Pereira", "Risaralda"),
    ("Salento", "Quindío"), ("Manizales", "Caldas"), ("Bucaramanga", "Santander"), ("Barichara", "Santander"),
    ("San Gil", "Santander"), ("Popayán", "Cauca"), ("Jardín", "Antioquia"), ("Santa Fe de Antioquia", "Antioquia"),
    ("Villavicencio", "Meta"),
]


def agregar(apps, schema_editor):
    Ciudad = apps.get_model("catalogo", "Ciudad")
    for nombre, departamento in CIUDADES_NUEVAS:
        Ciudad.objects.get_or_create(nombre=nombre, departamento=departamento)


def quitar(apps, schema_editor):
    Ciudad = apps.get_model("catalogo", "Ciudad")
    Publicacion = apps.get_model("catalogo", "Publicacion")
    for nombre, departamento in CIUDADES_NUEVAS:
        ciudad = Ciudad.objects.filter(nombre=nombre, departamento=departamento).first()
        if ciudad and not Publicacion.objects.filter(ciudad=ciudad).exists():
            ciudad.delete()


class Migration(migrations.Migration):
    dependencies = [("catalogo", "0005_v_publicacion_reporte")]
    operations = [migrations.RunPython(agregar, quitar)]
