"""Interfaz pública de SRV-04 Reservas (MOD-04).

Es el único módulo que otros servicios pueden importar de esta app. Nadie fuera de apps.reservas debe
importar apps.reservas.models (import-linter, ADR-001). Reservas sí consulta a Catálogo y a Pagos por
sus services (sección 3.3).
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

from apps.auditoria import services as auditoria
from apps.catalogo import services as catalogo
from apps.comun.errores import Conflicto, ErrorNegocio, NoEncontrado, SinPermiso
from apps.comun.eventos import publicar
from apps.comun.fechas import validar_estancia
from apps.pagos import services as pagos

from .models import (
    Cotizacion,
    CotizacionServicioAdicional,
    EstadoReserva,
    NocheNoDisponible,
    PeriodoCalendario,
    Reserva,
    TarifaServicio,
)

OCUPAN = (EstadoReserva.CONFIRMADA, EstadoReserva.EN_REVISION)
CENT = Decimal("1")
MINUTOS_COTIZACION = 30
FECHAS_OCUPADAS = "Las fechas ya no están disponibles."


# ---------------------------------------------------------------- consultas para otros servicios

def noches_no_disponibles():
    """Vista v_noche_no_disponible (solo lectura): noches de reservas CONFIRMADAS o EN_REVISION y de
    periodos cerrados del calendario. Búsqueda la combina con v_publicacion_buscable."""
    return NocheNoDisponible.objects.all()


def noches_no_disponibles_de(publicacion_id: int, desde: date, hasta: date) -> list[date]:
    return list(NocheNoDisponible.objects.filter(publicacion_id=publicacion_id, fecha__gte=desde, fecha__lt=hasta)
                .order_by("fecha").values_list("fecha", flat=True))


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
    alojamientos del anfitrión (RF-D-USU-01.4, CA-04.2, CA-04.5). Impiden desactivar la cuenta."""
    publicaciones_ids = catalogo.ids_publicaciones_de(usuario_id) if es_anfitrion else []
    hoy = timezone.localdate()
    qs = Reserva.objects.filter(estado__in=OCUPAN, fecha_salida__gte=hoy)
    qs = qs.filter(huesped_id=usuario_id) | qs.filter(publicacion_id__in=list(publicaciones_ids))
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

def _tarifa_vigente(momento=None) -> TarifaServicio | None:
    momento = momento or timezone.now()
    return (TarifaServicio.objects.filter(vigente_desde__lte=momento).order_by("-vigente_desde").first()
            or TarifaServicio.objects.order_by("vigente_desde").first())


def tarifa_vigente(momento=None) -> Decimal:
    t = _tarifa_vigente(momento)
    return t.porcentaje if t else Decimal("0")


def asegurar_tarifa_inicial(admin) -> None:
    """Tarifa inicial del 10 % desde el 1 de enero (ejemplos del SRS). La usa cargar_demo cuando la
    base no tenía administrador al migrar (tarifa_servicio.administrador_id es NOT NULL)."""
    if not TarifaServicio.objects.exists():
        inicio = timezone.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        TarifaServicio.objects.create(administrador=admin, porcentaje=Decimal("10"), vigente_desde=inicio)


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
    """precio_base = noches x precio_noche; descuento = % sobre el precio base si noches >= descuento_min_noches;
    tarifa_servicio = % vigente sobre (precio_base - descuento); cada adicional se cobra una vez por estancia."""
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


# ---------------------------------------------------------------- CU-ALO-06 Calendario (PeriodoCalendario)

def _dias(inicio: date, fin: date):
    d = inicio
    while d < fin:
        yield d
        d += timedelta(days=1)


def _rangos(dias: set[date]) -> list[tuple[date, date]]:
    out: list[tuple[date, date]] = []
    for d in sorted(dias):
        if out and out[-1][1] == d:
            out[-1] = (out[-1][0], d + timedelta(days=1))
        else:
            out.append((d, d + timedelta(days=1)))
    return out


def _publicacion_del_anfitrion(usuario, publicacion_id: int) -> dict:
    p = catalogo.resumen_publicacion(publicacion_id)
    if not p:
        raise NoEncontrado("La publicación no existe.")
    if p["anfitrion"] != usuario.id:
        # Acceso negado (CA-05.3): fuera de transaction.atomic, queda aunque la petición falle
        auditoria.registrar(usuario.id, "AccesoDenegado", entidad="Publicacion", entidad_id=publicacion_id, exitoso=False,
                            detalle={"motivo": "Calendario de una publicación ajena"})
        raise SinPermiso("Solo el anfitrión dueño administra el calendario.")
    return p


def calendario(usuario, publicacion_id: int, desde: date, hasta: date) -> dict:
    _publicacion_del_anfitrion(usuario, publicacion_id)
    periodos = PeriodoCalendario.objects.filter(publicacion_id=publicacion_id, fecha_fin__gt=desde, fecha_inicio__lt=hasta)
    return {
        "publicacion": publicacion_id,
        "periodos": [{"fecha_inicio": x.fecha_inicio, "fecha_fin": x.fecha_fin, "disponible": x.disponible,
                      "tipo": "DISPONIBLE" if x.disponible else "NO_DISPONIBLE"} for x in periodos],
        "noches_reservadas": sorted(noches_ocupadas(publicacion_id, desde, hasta)),
    }


def modificar_calendario(usuario, publicacion_id: int, inicio: date, fin: date, tipo: str) -> dict:
    """NO_DISPONIBLE cierra [inicio, fin); DISPONIBLE lo vuelve a abrir. Los periodos se guardan
    unificados en rangos con disponible = false (RF-D-ALO-02.2). No se bloquean noches con reserva (CA-09.2)."""
    validar_estancia(inicio, fin, permitir_pasado=True, campo_llegada="fecha_inicio", campo_salida="fecha_fin")
    _publicacion_del_anfitrion(usuario, publicacion_id)
    nuevas = set(_dias(inicio, fin))
    cerrar = tipo == "NO_DISPONIBLE"
    with transaction.atomic():
        catalogo.datos_para_cotizar(publicacion_id, bloquear=True)  # serializa con las reservas de la publicación
        if cerrar:
            choque = nuevas & noches_ocupadas(publicacion_id, inicio, fin)
            if choque:  # CA-09.2
                raise Conflicto("No se pueden bloquear fechas con una reserva CONFIRMADA.", extra={"fechas": sorted(choque)})
        periodos = PeriodoCalendario.objects.filter(publicacion_id=publicacion_id)
        actuales = {d for x in periodos.filter(disponible=False) for d in _dias(x.fecha_inicio, x.fecha_fin)}
        resultado = actuales | nuevas if cerrar else actuales - nuevas
        periodos.delete()
        PeriodoCalendario.objects.bulk_create(
            [PeriodoCalendario(publicacion_id=publicacion_id, fecha_inicio=a, fecha_fin=b, disponible=False) for a, b in _rangos(resultado)]
        )
        auditoria.registrar(usuario.id, "CalendarioActualizado", entidad="Publicacion", entidad_id=publicacion_id,
                            detalle={"tipo": tipo, "desde": inicio.isoformat(), "hasta": fin.isoformat()})
    return calendario(usuario, publicacion_id, inicio, fin)


# ---------------------------------------------------------------- HU-12 Cotizar (RF-D-RES-02.1)

def _verificar_libres(publicacion_id: int, llegada: date, salida: date, mensaje: str = FECHAS_OCUPADAS) -> None:
    ocupadas = noches_no_disponibles_de(publicacion_id, llegada, salida)
    if ocupadas:
        raise Conflicto(mensaje, extra={"fechas": ocupadas})


def _validar_capacidad(pub: dict, num_huespedes: int) -> None:
    if num_huespedes < 1:
        raise ErrorNegocio("Debe haber al menos un huésped.", campo="num_huespedes")
    if num_huespedes > pub["capacidad"]:  # CA-12.3
        raise ErrorNegocio(f"La capacidad máxima de este alojamiento es de {pub['capacidad']} huéspedes.",
                           campo="num_huespedes", extra={"capacidad_maxima": pub["capacidad"]})


def _adicionales_elegidos(pub: dict, ids) -> list[tuple[int, Decimal]]:
    ids = list(dict.fromkeys(ids or []))  # cada adicional una vez por estancia
    faltan = [i for i in ids if i not in pub["adicionales"]]
    if faltan:
        raise ErrorNegocio("Algún servicio adicional no pertenece a este alojamiento.", campo="adicionales")
    return [(i, Decimal(pub["adicionales"][i]["precio"])) for i in ids]


def _crear_cotizacion(huesped_id: int, pub: dict, llegada: date, salida: date, num_huespedes: int,
                      elegidos: list[tuple[int, Decimal]], tarifa: TarifaServicio) -> Cotizacion:
    c = calcular(pub, (salida - llegada).days, [p for _, p in elegidos], tarifa.porcentaje)
    cot = Cotizacion.objects.create(
        huesped_id=huesped_id, publicacion_id=pub["id"], tarifa_servicio_ref=tarifa, fecha_llegada=llegada,
        fecha_salida=salida, num_huespedes=num_huespedes, vence=timezone.now() + timedelta(minutes=MINUTOS_COTIZACION), **c,
    )
    CotizacionServicioAdicional.objects.bulk_create(
        [CotizacionServicioAdicional(cotizacion=cot, servicio_adicional_id=i, precio_aplicado=p) for i, p in elegidos]
    )
    return cot


def _tarifa_o_error() -> TarifaServicio:
    t = _tarifa_vigente()
    if not t:
        raise ErrorNegocio("La plataforma todavía no tiene una tarifa de servicio configurada.", codigo=409)
    return t


def cotizar(huesped, publicacion_id: int, llegada: date, salida: date, num_huespedes: int, adicionales=(), ip=None) -> Cotizacion:
    validar_estancia(llegada, salida)
    pub = catalogo.datos_para_cotizar(publicacion_id)
    if not pub or not pub["buscable"]:
        raise NoEncontrado("Este alojamiento no está disponible.")
    _validar_capacidad(pub, num_huespedes)
    elegidos = _adicionales_elegidos(pub, adicionales)
    _verificar_libres(publicacion_id, llegada, salida, "Las fechas elegidas no están disponibles.")
    tarifa = _tarifa_o_error()
    with transaction.atomic():
        cot = _crear_cotizacion(huesped.id, pub, llegada, salida, num_huespedes, elegidos, tarifa)
        auditoria.registrar(huesped.id, "CotizacionCreada", entidad="Cotizacion", entidad_id=cot.id, ip=ip,
                            detalle={"publicacion": publicacion_id, "total": str(cot.total)})
    return cot


def obtener_cotizacion(huesped, cotizacion_id: int) -> Cotizacion:
    cot = Cotizacion.objects.select_related("tarifa_servicio_ref").filter(pk=cotizacion_id, huesped_id=huesped.id).first()
    if not cot:
        raise NoEncontrado("La cotización no existe.")
    return cot


def cotizacion_dict(c: Cotizacion) -> dict:
    adicionales = list(c.adicionales.all())
    nombres = catalogo.nombres_adicionales([a.servicio_adicional_id for a in adicionales])
    pub = catalogo.resumen_publicacion(c.publicacion_id) or {}
    dinero = lambda v: f"{v:.2f}"  # noqa: E731  montos como texto, igual que el resto de la API
    return {
        "id": c.id, "publicacion": c.publicacion_id, "publicacion_titulo": pub.get("titulo"),
        "fecha_llegada": c.fecha_llegada, "fecha_salida": c.fecha_salida, "num_huespedes": c.num_huespedes,
        "noches": c.noches, "precio_noche": dinero(c.precio_noche), "precio_base": dinero(c.precio_base),
        "descuento": dinero(c.descuento), "tarifa_limpieza": dinero(c.tarifa_limpieza),
        "porcentaje_servicio": dinero(c.tarifa_servicio_ref.porcentaje), "tarifa_servicio": dinero(c.tarifa_servicio),
        "adicionales": [{"id": a.servicio_adicional_id, "nombre": nombres.get(a.servicio_adicional_id),
                         "precio_aplicado": dinero(a.precio_aplicado)} for a in adicionales],
        "total_adicionales": dinero(c.total_adicionales), "total": dinero(c.total),
        "creada": c.creada, "vence": c.vence, "vencida": c.vence <= timezone.now(),
        "reserva": Reserva.objects.filter(cotizacion_id=c.id).values_list("id", flat=True).first(),
    }


# ---------------------------------------------------------------- HU-13 Reservar y pagar (RF-D-RES-02.2)

class _PagoNoAprobado(Exception):
    def __init__(self, estado: str, motivo: str | None):
        super().__init__(motivo)
        self.estado, self.motivo = estado, motivo


class _CotizacionCambio(Exception):
    def __init__(self, pub: dict, elegidos, tarifa: TarifaServicio):
        super().__init__("La cotización cambió")
        self.pub, self.elegidos, self.tarifa = pub, elegidos, tarifa


def reserva_dict(r: Reserva) -> dict:
    return {
        "id": r.id, "estado": r.estado, "cotizacion": r.cotizacion_id, "publicacion": r.publicacion_id,
        "politica": r.politica_id, "fecha_llegada": r.fecha_llegada, "fecha_salida": r.fecha_salida,
        "num_huespedes": r.num_huespedes, "total": f"{r.total:.2f}", "clave_idempotencia": str(r.clave_idempotencia),
        "creada": r.creada, "pagos": pagos.pagos_de_reserva(r.id),
    }


def _misma_reserva(r: Reserva, huesped) -> tuple[dict, bool]:
    """CA-13.4 y RNF-P-FIA-02: la misma clave devuelve la misma reserva, sin cobrar otra vez."""
    if r.huesped_id != huesped.id:
        raise Conflicto("Esa clave de idempotencia ya se usó en otra solicitud.")
    return reserva_dict(r), False


def reservar(huesped, cotizacion_id: int, clave: uuid.UUID, medio: str, ip=None) -> tuple[dict, bool]:
    """Devuelve (reserva, creada). creada es False cuando la clave ya tenía una reserva (respuesta 200)."""
    existente = Reserva.objects.filter(clave_idempotencia=clave).first()
    if existente:
        return _misma_reserva(existente, huesped)
    cot = obtener_cotizacion(huesped, cotizacion_id)
    if Reserva.objects.filter(cotizacion_id=cot.id).exists():
        raise Conflicto("Esta cotización ya se usó en una reserva. Cotiza de nuevo.")
    try:
        with transaction.atomic():
            # 1. La publicación se bloquea: dos reservas de la misma publicación van una después de la otra (CA-13.2)
            pub = catalogo.datos_para_cotizar(cot.publicacion_id, bloquear=True)
            existente = Reserva.objects.filter(clave_idempotencia=clave).first()  # llegó mientras esperaba el bloqueo
            if existente:
                return _misma_reserva(existente, huesped)
            if not pub or not pub["buscable"]:
                raise Conflicto("Este alojamiento ya no está disponible.")
            validar_estancia(cot.fecha_llegada, cot.fecha_salida)
            _validar_capacidad(pub, cot.num_huespedes)
            # 2. Se recalcula con los precios y la tarifa de hoy; si el total cambió no se reserva
            ids = [a.servicio_adicional_id for a in cot.adicionales.all()]
            if any(i not in pub["adicionales"] for i in ids):
                raise _CotizacionCambio(pub, [(i, Decimal(pub["adicionales"][i]["precio"])) for i in ids if i in pub["adicionales"]], _tarifa_o_error())
            elegidos = _adicionales_elegidos(pub, ids)
            tarifa = _tarifa_o_error()
            if calcular(pub, cot.noches, [p for _, p in elegidos], tarifa.porcentaje)["total"] != cot.total:
                raise _CotizacionCambio(pub, elegidos, tarifa)
            # 3. Las noches siguen libres
            _verificar_libres(cot.publicacion_id, cot.fecha_llegada, cot.fecha_salida)
            # 4. Reserva CONFIRMADA y cobro en la misma transacción. La reserva se inserta antes del pago para que
            #    el pago nazca con reserva_id (el trigger de pago no permite cambiar reserva_id después). Si el
            #    pago no se aprueba, la transacción se revierte y no queda ni reserva ni pago (RNF-P-FIA-03).
            r = Reserva.objects.create(
                cotizacion=cot, huesped_id=huesped.id, publicacion_id=cot.publicacion_id, politica_id=pub["politica"],
                fecha_llegada=cot.fecha_llegada, fecha_salida=cot.fecha_salida, num_huespedes=cot.num_huespedes,
                total=cot.total, estado=EstadoReserva.CONFIRMADA, clave_idempotencia=clave,
            )
            pago = pagos.ServicioPagos().cobrar(cot, clave, medio, reserva_id=r.id, actor_id=huesped.id, ip=ip)
            if pago.estado != "APROBADO":
                raise _PagoNoAprobado(pago.estado, pago.motivo)
            # 5. Auditoría y evento de dominio
            detalle = {"publicacion": r.publicacion_id, "llegada": r.fecha_llegada.isoformat(),
                       "salida": r.fecha_salida.isoformat(), "total": str(r.total), "pago": pago.id}
            auditoria.registrar(huesped.id, "ReservaConfirmada", entidad="Reserva", entidad_id=r.id, detalle=detalle, ip=ip)
            publicar("ReservaConfirmada", usuario_id=huesped.id, entidad="Reserva", entidad_id=r.id, detalle=detalle)
    except _PagoNoAprobado as e:
        # CA-13.3: no queda la reserva; el intento se registra fuera de la transacción que se revirtió
        auditoria.registrar(huesped.id, "ReservaRechazada", entidad="Cotizacion", entidad_id=cot.id, exitoso=False, ip=ip,
                            detalle={"estado_pago": e.estado, "motivo": e.motivo, "total": str(cot.total), "clave": str(clave)})
        mensaje = ("El pago quedó en verificación y no se pudo confirmar la reserva. Intenta con otro medio de pago."
                   if e.estado == "EN_VERIFICACION" else f"El pago fue rechazado: {e.motivo or 'sin motivo informado'}")
        raise ErrorNegocio(mensaje, codigo=402, extra={"estado_pago": e.estado, "motivo": e.motivo}) from e
    except _CotizacionCambio as e:
        with transaction.atomic():
            nueva = _crear_cotizacion(huesped.id, e.pub, cot.fecha_llegada, cot.fecha_salida, cot.num_huespedes, e.elegidos, e.tarifa)
        raise Conflicto("El precio cambió desde que cotizaste. Revisa la cotización nueva antes de reservar.",
                        extra={"cotizacion": cotizacion_dict(nueva)}) from e
    except IntegrityError as e:
        estado_sql = getattr(e.__cause__, "sqlstate", None)
        if estado_sql == "23P01":  # restricción EXCLUDE: última defensa contra la doble reserva
            raise Conflicto(FECHAS_OCUPADAS) from e
        existente = Reserva.objects.filter(clave_idempotencia=clave).first()
        if estado_sql == "23505" and existente:  # la misma clave entró por otra petición
            return _misma_reserva(existente, huesped)
        raise
    return reserva_dict(r), True


def crear_reserva_confirmada(huesped_id: int, publicacion: dict, llegada: date, salida: date, num_huespedes: int) -> int:
    """Crea cotización y reserva CONFIRMADA sin pasar por el pago. Solo para la carga de datos de demostración
    (cargar_demo), que usa fechas fijas; el flujo real es reservar()."""
    tarifa = _tarifa_o_error()
    c = calcular(publicacion, (salida - llegada).days, porcentaje=tarifa.porcentaje)
    with transaction.atomic():
        cot = Cotizacion.objects.create(
            huesped_id=huesped_id, publicacion_id=publicacion["id"], tarifa_servicio_ref=tarifa, fecha_llegada=llegada,
            fecha_salida=salida, num_huespedes=num_huespedes, vence=timezone.now() + timedelta(minutes=MINUTOS_COTIZACION), **c,
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
