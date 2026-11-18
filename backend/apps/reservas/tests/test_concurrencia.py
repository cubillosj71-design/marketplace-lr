"""CA-13.2: dos huéspedes confirman las mismas fechas al mismo tiempo; solo una reserva queda CONFIRMADA y la
otra recibe "Las fechas ya no están disponibles". Corre con transaction=True para que cada hilo use su propia
conexión y vea lo que la otra confirmó (la limpieza de la base la maneja conftest.py)."""

import threading
import uuid

import pytest
from django.apps import apps
from django.db import connection
from rest_framework.test import APIClient

NUEVO = {"nombre_completo": "Ana Torres", "correo": "ana@correo.com", "telefono": "300 000 0000",
         "password": "Segura2026", "rol": "HUESPED", "acepta_datos": True}


@pytest.mark.django_db(transaction=True)
def test_ca_13_2_dos_reservas_simultaneas_solo_una_confirma(publicar, cliente, entrar, dias):
    pid = publicar("Muy pedido")
    assert cliente.post("/api/v1/identidad/registro", NUEVO, format="json").status_code == 201
    huespedes = [entrar("huesped@correo.com"), entrar("ana@correo.com", "Segura2026")]
    cotizaciones = []
    for h in huespedes:
        r = h.post("/api/v1/reservas/cotizaciones", {"publicacion": pid, "fecha_llegada": dias(30).isoformat(),
                                                     "fecha_salida": dias(33).isoformat(), "num_huespedes": 2}, format="json")
        assert r.status_code == 201, r.content
        cotizaciones.append(r.json()["id"])

    salida = threading.Barrier(2)
    respuestas: dict[int, object] = {}

    def confirmar(i):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=huespedes[i]._credentials["HTTP_AUTHORIZATION"])
        try:
            salida.wait()  # las dos solicitudes salen al mismo tiempo
            respuestas[i] = c.post("/api/v1/reservas", {"cotizacion": cotizaciones[i], "clave_idempotencia": str(uuid.uuid4()),
                                                        "medio_pago": "tarjeta"}, format="json")
        finally:
            connection.close()  # cada hilo cierra su conexión

    hilos = [threading.Thread(target=confirmar, args=(i,)) for i in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=60)

    codigos = sorted(r.status_code for r in respuestas.values())
    assert codigos == [201, 409], [r.content for r in respuestas.values()]
    perdedora = next(r for r in respuestas.values() if r.status_code == 409)
    assert perdedora.json()["detalle"] == "Las fechas ya no están disponibles."
    Reserva = apps.get_model("reservas", "Reserva")
    assert Reserva.objects.filter(publicacion_id=pid, estado="CONFIRMADA").count() == 1
    assert apps.get_model("pagos", "Pago").objects.filter(reserva__publicacion_id=pid).count() == 1
