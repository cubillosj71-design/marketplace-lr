"""Interfaz pública de SRV-04 Reservas.

Es el único módulo que otros servicios pueden importar de esta app.
Nadie fuera de apps.reservas debe importar apps.reservas.models (regla verificada
con import-linter en el pipeline, ADR-001).
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from apps.auditoria import services as auditoria
from apps.comun.errores import ErrorNegocio
from apps.comun.eventos import publicar

from .models import Cotizacion, EstadoReserva, Reserva, TarifaServicio

OCUPAN = (EstadoReserva.CONFIRMADA, EstadoReserva.EN_REVISION)
CENT = Decimal("1")


# ---------------------------------------------------------------- consultas para otros servicios

def noches_ocupadas(publicacion_id: int, desde: date, hasta: date) -> set[date]:
    """Noches de reservas CONFIRMADAS o EN_REVISION entre [desde, hasta)."""
    noches: set[date] = set()
    for r in Reserva.objects.filter(publicacion_id=publicacion_id, estado__in=OCUPAN, fecha_salida__gt=desde, fecha_llegada__lt=hasta):
        d = max(r.fecha_llegada, desde)
        while d < min(r.fecha_salida, hasta):
            noches.add(d)
            d += timedelta(days=1)
    return noches


def reservas_pendientes(usuario_id: int, es_anfitrion: bool) -> list[dict]:
    """Reservas CONFIRMADAS o EN_REVISION cuya fecha de salida no ha pasado, como huésped o en los
    alojamientos del anfitrión (RF-D-USU-01.4, CA-04.2, CA-04.5). Impiden desactivar la cuenta.
    Reservas consulta a Catálogo (SRV-04 -> SRV-02), así Identidad no depende de Catálogo."""
    from apps.catalogo import services as catalogo

    publicaciones_ids = catalogo.ids_publicaciones_de(usuario_id) if es_anfitrion else []
    huesped_id = usuario_id
    hoy = timezone.localdate()
    qs = Reserva.objects.filter(estado__in=OCUPAN, fecha_salida__gte=hoy)
    qs = qs.filter(huesped_id=huesped_id) | qs.filter(publicacion_id__in=list(publicaciones_ids))
    return [{"id": r.id, "publicacion": r.publicacion_id, "estado": r.estado, "fecha_llegada": r.fecha_llegada,
             "fecha_salida": r.fecha_salida} for r in qs.distinct()]


def reservas_para_reporte(desde=None, hasta=None, publicaciones_ids=None) -> list[dict]:
    """Reservas con llegada en el periodo y sus valores fijados al confirmar (CA-22.1)."""
    qs = Reserva.objects.select_related("cotizacion").order_by("fecha_llegada")
    if desde:
        qs = qs.filter(fecha_llegada__gte=desde)
    if hasta:
        qs = qs.filter(fecha_llegada__lte=hasta)
    if publicaciones_ids is not None:
        qs = qs.filter(publicacion_id__in=list(publicaciones_ids))
    return [{
        "id": r.id, "publicacion": r.publicacion_id, "huesped": r.huesped_id, "estado": r.estado,
        "fecha_llegada": r.fecha_llegada, "fecha_salida": r.fecha_salida, "noches": r.cotizacion.noches,
        "total": r.total, "tarifa_servicio": r.cotizacion.tarifa_servicio,
    } for r in qs]


def conteo_por_estado(desde=None, hasta=None) -> dict[str, int]:
    qs = Reserva.objects.all()
    if desde:
        qs = qs.filter(fecha_llegada__gte=desde)
    if hasta:
        qs = qs.filter(fecha_llegada__lte=hasta)
    base = {e: 0 for e in EstadoReserva.values}
    base.update(dict(qs.values_list("estado").annotate(n=Count("id"))))
    return base


# ---------------------------------------------------------------- RF-D-ADM-03.1 Tarifa de servicio

def tarifa_vigente(momento=None) -> Decimal:
    momento = momento or timezone.now()
    t = TarifaServicio.objects.filter(vigente_desde__lte=momento).order_by("-vigente_desde").first() or TarifaServicio.objects.order_by("vigente_desde").first()
    return t.porcentaje if t else Decimal("0")


def historial_tarifa() -> list[dict]:
    return [{"porcentaje": f"{t.porcentaje:.2f}", "vigente_desde": t.vigente_desde, "administrador": t.administrador_id} for t in TarifaServicio.objects.all()]


def cambiar_tarifa(admin, porcentaje: Decimal, ip=None) -> dict:
    if porcentaje is None or not (Decimal("0") <= porcentaje <= Decimal("30")):
        raise ErrorNegocio("El porcentaje debe estar entre 0 % y 30 %.", campo="porcentaje")
    anterior = tarifa_vigente()
    if porcentaje == anterior:
        raise ErrorNegocio("Ese ya es el porcentaje vigente.", campo="porcentaje")
    with transaction.atomic():
        t = TarifaServicio.objects.create(administrador=admin, porcentaje=porcentaje, vigente_desde=timezone.now())
        auditoria.registrar(admin.id, "TarifaActualizada", entidad="TarifaServicio", entidad_id=t.id,
                            detalle={"anterior": str(anterior), "nuevo": str(porcentaje)}, ip=ip)
    return {"porcentaje": f"{t.porcentaje:.2f}", "vigente_desde": t.vigente_desde}


# ---------------------------------------------------------------- cálculo de la cotización (CA-12.1, CA-12.2)

def calcular(publicacion: dict, noches: int, adicionales: list[Decimal] | None = None, porcentaje: Decimal | None = None) -> dict:
    pct = tarifa_vigente() if porcentaje is None else porcentaje
    precio_noche = Decimal(publicacion["precio_noche"])
    base = precio_noche * noches
    aplica = publicacion.get("descuento_porcentaje") and publicacion.get("descuento_min_noches") and noches >= publicacion["descuento_min_noches"]
    descuento = (base * Decimal(publicacion["descuento_porcentaje"]) / 100).quantize(CENT, ROUND_HALF_UP) if aplica else Decimal("0")
    servicio = ((base - descuento) * pct / 100).quantize(CENT, ROUND_HALF_UP)
    limpieza = Decimal(publicacion.get("tarifa_limpieza") or 0)
    extra = sum(adicionales or [], Decimal("0"))
    return {
        "noches": noches, "precio_noche": precio_noche, "precio_base": base, "descuento": descuento,
        "tarifa_limpieza": limpieza, "tarifa_servicio": servicio, "total_adicionales": extra,
        "total": base - descuento + limpieza + servicio + extra,
    }


def crear_reserva_confirmada(huesped_id: int, publicacion: dict, llegada: date, salida: date, num_huespedes: int) -> int:
    """Crea cotización y reserva CONFIRMADA. Se usa para la carga de datos de demostración; el flujo
    completo de reservar con pago (RF-D-RES-02.2) llega con el módulo de Reservas."""
    c = calcular(publicacion, (salida - llegada).days)
    with transaction.atomic():
        cot = Cotizacion.objects.create(
            huesped_id=huesped_id, publicacion_id=publicacion["id"], fecha_llegada=llegada, fecha_salida=salida,
            num_huespedes=num_huespedes, vence=timezone.now() + timedelta(minutes=30), **c,
        )
        r = Reserva.objects.create(
            cotizacion=cot, huesped_id=huesped_id, publicacion_id=publicacion["id"], politica_id=publicacion["politica"],
            fecha_llegada=llegada, fecha_salida=salida, num_huespedes=num_huespedes, total=c["total"],
            clave_idempotencia=uuid.uuid4(),
        )
    return r.id


# ---------------------------------------------------------------- suscriptor de eventos

def al_bloquear_publicacion(sender, nombre, entidad_id=None, usuario_id=None, **_):
    """PublicacionBloqueada: las reservas futuras pasan a EN_REVISION (RF-D-ADM-01.2)."""
    if nombre != "PublicacionBloqueada" or not entidad_id:
        return
    hoy = timezone.localdate()
    with transaction.atomic():
        ids = list(Reserva.objects.filter(publicacion_id=entidad_id, estado=EstadoReserva.CONFIRMADA, fecha_llegada__gte=hoy).values_list("id", flat=True))
        Reserva.objects.filter(pk__in=ids).update(estado=EstadoReserva.EN_REVISION)
        for rid in ids:
            auditoria.registrar(usuario_id, "ReservaEnRevision", entidad="Reserva", entidad_id=rid, detalle={"publicacion": entidad_id})
            publicar("ReservaEnRevision", usuario_id=usuario_id, entidad="Reserva", entidad_id=rid, detalle={"publicacion": entidad_id})
