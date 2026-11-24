"""Interfaz pública de SRV-03 Búsqueda (MOD-03).

Búsqueda no tiene tablas propias ni registra auditoría: solo lee tres vistas a través de los services
de quien las publica (import-linter verifica que no importe modelos de otras apps):
- v_publicacion_buscable (Catálogo): ACTIVAS de anfitriones con cuenta activa y sin restricción vigente.
- v_noche_no_disponible (Reservas): noches reservadas o cerradas en el calendario.
- v_calificacion_publicacion (Reseñas): promedio y total de reseñas.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.catalogo import services as catalogo
from apps.comun.errores import ErrorNegocio, NoEncontrado
from apps.comun.fechas import calcular_fecha_maxima, validar_estancia
from apps.identidad import services as identidad
from apps.resenas import services as resenas
from apps.reservas import services as reservas


def _formatear_dinero(v) -> str | None:
    """Convierte un valor a texto con dos decimales (formato de montos de la API) o deja None."""
    return None if v is None else f"{Decimal(v):.2f}"


def _obtener_calificacion(c: dict) -> dict:
    """Arma {promedio, total} de las reseñas de una publicación, con el promedio como texto o None si no hay reseñas."""
    return {"promedio": _formatear_dinero(c["promedio"]) if c["promedio"] is not None else None, "total": c["total"]}


def buscar_publicaciones(*, ciudad: int | None = None, llegada: date | None = None, salida: date | None = None, huespedes: int = 1,
           tipo: int | None = None, precio_min: Decimal | None = None, precio_max: Decimal | None = None,
           servicios: list[int] | None = None) -> list[dict]:
    """HU-10: publicaciones buscables con capacidad >= huéspedes y sin noches no disponibles en
    [llegada, salida). Los filtros de tipo, rango de precio por noche y servicios se combinan (CA-10.4)."""
    if (llegada is None) != (salida is None):
        raise ErrorNegocio("Indica la fecha de llegada y la de salida.", campo="salida" if llegada else "llegada")
    if llegada and salida:
        validar_estancia(llegada, salida, campo_llegada="llegada", campo_salida="salida")  # CA-10.3: no busca
    if huespedes < 1:
        raise ErrorNegocio("Debe haber al menos un huésped.", campo="huespedes")
    if precio_min is not None and precio_max is not None and precio_min > precio_max:
        raise ErrorNegocio("El precio mínimo no puede ser mayor que el máximo.", campo="precio_min")

    qs = catalogo.listar_publicaciones_buscables().filter(capacidad__gte=huespedes)
    if ciudad:
        qs = qs.filter(ciudad_id=ciudad)
    if tipo:
        qs = qs.filter(tipo_alojamiento_id=tipo)
    if precio_min is not None:
        qs = qs.filter(precio_noche__gte=precio_min)
    if precio_max is not None:
        qs = qs.filter(precio_noche__lte=precio_max)
    if servicios:
        qs = qs.filter(servicios__contains=sorted(set(servicios)))  # todos los elegidos
    if llegada and salida:
        ocupada = reservas.consultar_noches_no_disponibles().filter(publicacion_id=OuterRef("pk"), fecha__gte=llegada, fecha__lt=salida)
        qs = qs.exclude(Exists(ocupada))
    lista = list(qs.order_by("precio_noche", "id"))
    cal = {c.publicacion_id: {"promedio": c.promedio, "total": c.total}
           for c in resenas.consultar_calificaciones().filter(publicacion_id__in=[p.id for p in lista])}
    return [{
        "id": p.id, "titulo": p.titulo, "ciudad_id": p.ciudad_id, "ciudad": p.ciudad,
        "tipo_alojamiento_id": p.tipo_alojamiento_id, "tipo": p.tipo, "capacidad": p.capacidad,
        "precio_noche": _formatear_dinero(p.precio_noche), "tarifa_limpieza": _formatear_dinero(p.tarifa_limpieza),
        "descuento_porcentaje": _formatear_dinero(p.descuento_porcentaje), "descuento_min_noches": p.descuento_min_noches,
        "politica_id": p.politica_id, "servicios": p.servicios, "imagen_principal": p.imagen_principal,
        "calificacion": _obtener_calificacion(cal.get(p.id, {"promedio": None, "total": 0})),
    } for p in lista]


def consultar_detalle_publicacion(publicacion_id: int, desde: date | None = None, hasta: date | None = None) -> dict:
    """HU-11: todos los datos, política con sus tramos (CA-11.3), noches no disponibles del rango
    (CA-11.2) y calificación. Si la publicación no es buscable responde 404."""
    if not catalogo.es_buscable(publicacion_id):
        raise NoEncontrado("Este alojamiento no está disponible.")
    desde = desde or timezone.localdate()
    hasta = min(hasta or desde + timedelta(days=90), calcular_fecha_maxima())
    if hasta <= desde:
        raise ErrorNegocio("La fecha final debe ser posterior a la inicial.", campo="hasta")
    d = catalogo.obtener_detalle_publico(publicacion_id)
    for campo in ("precio_noche", "tarifa_limpieza", "descuento_porcentaje"):
        d[campo] = _formatear_dinero(d[campo])
    d["servicios_adicionales"] = [{**a, "precio": _formatear_dinero(a["precio"])} for a in d["servicios_adicionales"]]
    if d["politica"]:
        d["politica"]["tramos"] = [{**t, "porcentaje_devolucion": _formatear_dinero(t["porcentaje_devolucion"])} for t in d["politica"]["tramos"]]
    d["anfitrion_nombre"] = identidad.obtener_nombres_usuarios([d["anfitrion"]]).get(d["anfitrion"])
    d["calificacion"] = _obtener_calificacion(resenas.consultar_calificacion(publicacion_id))
    d["disponibilidad"] = {"desde": desde, "hasta": hasta,
                           "noches_no_disponibles": reservas.consultar_noches_no_disponibles_de(publicacion_id, desde, hasta)}
    return d
