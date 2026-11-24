"""Muestra a qué base de datos apunta el backend (la de DATABASE_URL en backend/.env o en el entorno) y qué tiene.

Uso: python manage.py mostrar_base
No muestra la contraseña. Sirve para comprobar que el backend y quien lo prueba usan la misma base.
"""

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone


class Command(BaseCommand):
    """Comando `python manage.py mostrar_base`: muestra a qué base está conectado el backend.

    Imprime servidor, puerto, nombre de la base, versión de PostgreSQL, cuántos usuarios,
    publicaciones y reservas tiene y la fecha del primer evento de auditoría (si es muy reciente,
    la base se vació en ese momento).
    """
    help = "Muestra el servidor, el puerto y el nombre de la base que usa el backend, con cuántos datos tiene."

    def handle(self, *args, **_):
        b = connection.settings_dict
        with connection.cursor() as c:
            c.execute("SELECT version(), inet_server_port(), min(fecha) FROM evento_auditoria")
            version, puerto_real, primer_evento = c.fetchone()
        contar = lambda modelo: apps.get_model(*modelo.split(".")).objects.count()  # noqa: E731
        self.stdout.write(
            f"Base: {b.get('NAME')}  servidor: {b.get('HOST') or 'localhost'}:{b.get('PORT') or 5432}  usuario: {b.get('USER')}\n"
            f"PostgreSQL: {version.split(' on ')[0]} (puerto dentro del servidor: {puerto_real})\n"
            f"Usuarios: {contar('identidad.Usuario')}  publicaciones: {contar('catalogo.Publicacion')}  "
            f"reservas: {contar('reservas.Reserva')}\n"
            f"Primer evento de auditoría: {timezone.localtime(primer_evento) if primer_evento else '(ninguno)'}  <- si es muy reciente, la base se vació en ese momento"
        )
