"""MOD-03 Búsqueda: HU-10 (CA-10.1 a CA-10.4), HU-11 (CA-11.2, CA-11.3), CA-04.3, CA-21.2 y el límite de 12 meses."""

from datetime import timedelta

import pytest
from django.apps import apps

from apps.catalogo import services as catalogo
from apps.comun.fechas import fecha_maxima
from apps.comun.management.commands.cargar_demo import PUBLICACIONES

pytestmark = pytest.mark.django_db
BUSCAR = "/api/v1/busqueda/publicaciones"


def _ids_catalogo():
    cat = catalogo.listar_catalogos()
    return ({c["nombre"]: c["id"] for c in cat["ciudades"]}, {t["nombre"]: t["id"] for t in cat["tipos"]},
            {s["nombre"]: s["id"] for s in cat["servicios"]})


# La demo también tiene alojamientos en Cartagena: las pruebas solo miran los que crean ellas mismas
DEMO = {datos["titulo"] for _, _, _, datos, _ in PUBLICACIONES}


def _titulos(r):
    assert r.status_code == 200, r.content
    return {p["titulo"] for p in r.json()} - DEMO


def _reservar(entrar, pid, llegada, salida, huespedes=2):
    """Reserva por la API real: cotiza y paga con el adaptador simulado."""
    import uuid

    h = entrar("huesped@correo.com")
    cot = h.post("/api/v1/reservas/cotizaciones", {"publicacion": pid, "fecha_llegada": llegada.isoformat(),
                                                   "fecha_salida": salida.isoformat(), "num_huespedes": huespedes}, format="json")
    assert cot.status_code == 201, cot.content
    r = h.post("/api/v1/reservas", {"cotizacion": cot.json()["id"], "clave_idempotencia": str(uuid.uuid4()),
                                    "medio_pago": "tarjeta"}, format="json")
    assert r.status_code == 201, r.content
    return r.json()


def test_ca_10_1_busca_por_ciudad_fechas_y_capacidad(publicar, cliente, dias):
    ciudades, _, _ = _ids_catalogo()
    publicar("Cartagena para 4", capacidad=4)
    publicar("Cartagena para 6", capacidad=6)
    publicar("Cartagena para 2", capacidad=2)
    publicar("Medellín para 4", ciudad="Medellín", capacidad=4)
    r = cliente.get(BUSCAR, {"ciudad": ciudades["Cartagena"], "llegada": dias(40), "salida": dias(43), "huespedes": 4})
    assert _titulos(r) == {"Cartagena para 4", "Cartagena para 6"}


def test_ca_10_2_no_aparece_pausada_ni_con_noche_reservada(publicar, cliente, entrar, dias):
    ciudades, _, _ = _ids_catalogo()
    libre = publicar("Libre")
    pausada = publicar("Pausada")
    reservada = publicar("Reservada")
    entrar("anfitrion@correo.com").post(f"/api/v1/catalogo/publicaciones/{pausada}/pausar")
    _reservar(entrar, reservada, dias(42), dias(44))  # una noche (la 42) cae en el rango buscado
    r = cliente.get(BUSCAR, {"ciudad": ciudades["Cartagena"], "llegada": dias(40), "salida": dias(43)})
    assert _titulos(r) == {"Libre"} and libre


def test_ca_09_3_el_dia_de_salida_queda_libre_para_otra_llegada(publicar, cliente, entrar, dias):
    ciudades, _, _ = _ids_catalogo()
    pid = publicar("Salida y llegada el mismo día")
    _reservar(entrar, pid, dias(40), dias(43))
    assert _titulos(cliente.get(BUSCAR, {"ciudad": ciudades["Cartagena"], "llegada": dias(43), "salida": dias(45)})) == {"Salida y llegada el mismo día"}


def test_noches_cerradas_en_el_calendario_tampoco_aparecen(publicar, cliente, entrar, dias):
    ciudades, _, _ = _ids_catalogo()
    pid = publicar("Con calendario cerrado")
    entrar("anfitrion@correo.com").post(f"/api/v1/catalogo/publicaciones/{pid}/calendario",
                                        {"fecha_inicio": dias(41).isoformat(), "fecha_fin": dias(42).isoformat(), "tipo": "NO_DISPONIBLE"}, format="json")
    assert _titulos(cliente.get(BUSCAR, {"ciudad": ciudades["Cartagena"], "llegada": dias(40), "salida": dias(43)})) == set()


def test_ca_10_3_salida_igual_o_anterior_no_busca(cliente, dias):
    for salida in (dias(40), dias(39)):
        r = cliente.get(BUSCAR, {"llegada": dias(40), "salida": salida})
        assert r.status_code == 400 and r.json()["campo"] == "salida"


def test_ca_10_4_filtros_combinados(publicar, cliente, dias):
    ciudades, tipos, servicios = _ids_catalogo()
    publicar("Apartamento Wi-Fi", tipo="Apartamento", precio=150000, servicios=["Wi-Fi"])
    publicar("Casa Wi-Fi", tipo="Casa", precio=300000, servicios=["Wi-Fi"])
    publicar("Apartamento sin Wi-Fi", tipo="Apartamento", precio=150000, servicios=["Cocina"])
    r = cliente.get(BUSCAR, {"ciudad": ciudades["Cartagena"], "llegada": dias(40), "salida": dias(43), "tipo": tipos["Apartamento"],
                             "precio_min": 100000, "precio_max": 200000, "servicios": servicios["Wi-Fi"]})
    assert _titulos(r) == {"Apartamento Wi-Fi"}


def test_varios_servicios_exigen_todos(publicar, cliente):
    ciudades, _, servicios = _ids_catalogo()
    publicar("Wi-Fi y cocina", servicios=["Wi-Fi", "Cocina"])
    publicar("Solo Wi-Fi", servicios=["Wi-Fi"])
    r = cliente.get(BUSCAR, {"ciudad": ciudades["Cartagena"], "servicios": f"{servicios['Wi-Fi']},{servicios['Cocina']}"})
    assert _titulos(r) == {"Wi-Fi y cocina"}


def test_ca_04_3_anfitrion_desactivado_no_aparece(publicar, cliente, entrar):
    ciudades, _, _ = _ids_catalogo()
    publicar("De Pedro", anfitrion="pedro@correo.com")
    consulta = {"ciudad": ciudades["Cartagena"]}
    assert _titulos(cliente.get(BUSCAR, consulta)) == {"De Pedro"}
    assert entrar("pedro@correo.com").post("/api/v1/identidad/perfil/desactivar").status_code == 200
    assert _titulos(cliente.get(BUSCAR, consulta)) == set()
    entrar("pedro@correo.com")  # CA-04.4: al reactivarse vuelve a aparecer
    assert _titulos(cliente.get(BUSCAR, consulta)) == {"De Pedro"}


def test_ca_21_2_anfitrion_restringido_no_aparece(publicar, cliente, entrar):
    ciudades, _, _ = _ids_catalogo()
    publicar("De Pedro", anfitrion="pedro@correo.com")
    consulta = {"ciudad": ciudades["Cartagena"]}
    pedro = apps.get_model("identidad", "Usuario").objects.get(correo="pedro@correo.com")
    admin = entrar("admin@inversioneslr.com")
    admin.post(f"/api/v1/admin/usuarios/{pedro.id}/restriccion", {"motivo": "Prueba"}, format="json")
    assert _titulos(cliente.get(BUSCAR, consulta)) == set()
    admin.delete(f"/api/v1/admin/usuarios/{pedro.id}/restriccion")  # CA-21.3
    assert _titulos(cliente.get(BUSCAR, consulta)) == {"De Pedro"}


def test_la_cuenta_restringida_de_la_demo_no_aparece(demo, cliente):
    assert "Apartamento El Poblado" not in _titulos(cliente.get(BUSCAR))


def test_limite_de_12_meses_en_la_busqueda(cliente):
    limite = fecha_maxima()
    r = cliente.get(BUSCAR, {"llegada": limite - timedelta(days=2), "salida": limite + timedelta(days=1)})
    assert r.status_code == 400 and "12 meses" in r.json()["detalle"]
    assert cliente.get(BUSCAR, {"llegada": limite - timedelta(days=2), "salida": limite}).status_code == 200


# ---------------- HU-11 Detalle
def test_ca_11_2_y_11_3_detalle_con_noches_ocupadas_y_politica(publicar, cliente, entrar, dias):
    pid = publicar("Detalle completo", servicios=["Wi-Fi", "Cocina"], adicionales=[("Desayuno", 30000)], descuento=(10, 7))
    _reservar(entrar, pid, dias(50), dias(52))
    r = cliente.get(f"{BUSCAR}/{pid}", {"desde": dias(45), "hasta": dias(60)})
    assert r.status_code == 200
    d = r.json()
    assert d["disponibilidad"]["noches_no_disponibles"] == [dias(50).isoformat(), dias(51).isoformat()]  # CA-11.2
    tramos = [(t["dias_minimos"], t["dias_maximos"], t["porcentaje_devolucion"]) for t in d["politica"]["tramos"]]
    assert d["politica"]["nombre"] == "Moderada" and tramos == [(7, None, "100.00"), (2, 6, "50.00"), (0, 1, "0.00")]  # CA-11.3
    assert [s["nombre"] for s in d["servicios"]] == ["Cocina", "Wi-Fi"]
    assert d["servicios_adicionales"][0]["nombre"] == "Desayuno" and d["servicios_adicionales"][0]["precio"] == "30000.00"
    assert d["reglas"] == [{"descripcion": "No fumar", "orden": 1}] and d["imagenes"][0]["orden"] == 1
    assert d["calificacion"] == {"promedio": None, "total": 0}  # v_calificacion_publicacion provisional
    assert d["anfitrion_nombre"] == "Laura Gómez"


def test_detalle_de_publicacion_no_buscable_responde_404(demo, cliente):
    Publicacion = apps.get_model("catalogo", "Publicacion")
    for titulo in ("Cabaña El Roble", "Apartamento El Poblado"):  # PAUSADA y de anfitrión restringido
        assert cliente.get(f"{BUSCAR}/{Publicacion.objects.get(titulo=titulo).id}").status_code == 404


def test_la_busqueda_es_publica_y_no_audita(publicar, cliente):
    from apps.auditoria import services as auditoria

    publicar("Pública")
    antes = auditoria.consultar_eventos().count()
    assert cliente.get(BUSCAR).status_code == 200
    assert auditoria.consultar_eventos().count() == antes
