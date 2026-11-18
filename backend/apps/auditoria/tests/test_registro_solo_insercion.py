"""RNF-E-CON-01: nadie puede modificar ni borrar el registro de acciones (CA-23.2)."""

import pytest
from django.db import DatabaseError, connection, transaction

from apps.auditoria import services
from apps.auditoria.models import EventoAuditoria


@pytest.mark.django_db
def test_registrar_guarda_el_evento():
    services.registrar("PRUEBA", exitoso=True, detalle={"a": 1}, ip="10.0.0.1")
    evento = EventoAuditoria.objects.get()
    assert evento.accion == "PRUEBA" and evento.exitoso and evento.detalle == {"a": 1}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "operacion",
    [
        lambda: EventoAuditoria.objects.update(exitoso=False),
        lambda: EventoAuditoria.objects.all().delete(),
    ],
    ids=["update", "delete"],
)
def test_la_base_rechaza_modificar_o_borrar_eventos(operacion):
    services.registrar("PRUEBA", exitoso=True)
    with pytest.raises(DatabaseError, match="solo inserción"), transaction.atomic():
        operacion()
    assert EventoAuditoria.objects.filter(exitoso=True).count() == 1


@pytest.mark.django_db
def test_la_base_rechaza_truncate():
    with pytest.raises(DatabaseError, match="solo inserción"), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("TRUNCATE evento_auditoria")


def test_ip_toma_el_valor_que_agrega_el_proxy():
    peticion = type("P", (), {"META": {"HTTP_X_FORWARDED_FOR": "1.1.1.1, 200.1.2.3", "REMOTE_ADDR": "10.0.0.2"}})()
    assert services.ip_de_la_peticion(peticion) == "200.1.2.3"
