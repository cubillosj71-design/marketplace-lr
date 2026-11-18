"""Interfaz pública de SRV-09 Reportes (MOD-09, RF-D-ADM-05.1 y 05.2).

Es el único módulo que otros servicios pueden importar de esta app. Reportes solo lee cuatro vistas
(v_usuario_reporte, v_publicacion_reporte, v_reserva_reporte y v_demanda) con modelos managed = False y no importa
ninguna otra app de negocio (import-linter). Solo usa Auditoría, para registrar cada descarga (CA-25.2).

Reglas del SRS:
- Una reserva pertenece al periodo según su fecha de CREACIÓN (hora de Colombia), no la de llegada.
- Monto bruto e ingreso de la plataforma salen de las columnas calculadas de v_reserva_reporte (nota de RF-D-ADM-05).
- El tablero y los cinco reportes usan las MISMAS funciones de consulta, así sus totales coinciden (CA-25.1).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Sum
from django.utils import timezone

from apps.auditoria import services as auditoria
from apps.comun.errores import ErrorNegocio
from apps.comun.fechas import sumar_meses

from . import archivos
from .models import Demanda, PublicacionReporte, ReservaReporte, UsuarioReporte

TIPOS = ("usuarios", "publicaciones", "reservas", "ingresos", "demanda")
FORMATOS = ("pdf", "xlsx")
ESTADOS_RESERVA = ("CONFIRMADA", "EN_REVISION", "COMPLETADA", "CANCELADA")
ROL_TXT = {"HUESPED": "Huésped", "ANFITRION": "Anfitrión", "ADMINISTRADOR": "Administrador"}
ESTADO_CUENTA_TXT = {"ACTIVA": "Activa", "DESACTIVADA": "Desactivada", "RESTRINGIDA": "Restringida"}
FILTRO_ESTADO_CUENTA = {"ACTIVA": {"activa": True, "restringida": False}, "DESACTIVADA": {"activa": False}, "RESTRINGIDA": {"restringida": True}}
ESTADO_PUB_TXT = {"PENDIENTE_REVISION": "En revisión", "ACTIVA": "Activa", "PAUSADA": "Pausada", "BLOQUEADA": "Bloqueada"}
CERO = Decimal("0")


def validar_periodo(desde: date, hasta: date) -> None:
    """Periodo máximo de 12 meses (ADR-009); si desde > hasta, 400."""
    if desde > hasta:
        raise ErrorNegocio("La fecha inicial no puede ser posterior a la final.", campo="desde")
    meses = settings.MESES_MAXIMOS_REPORTE
    if hasta >= sumar_meses(desde, meses):
        raise ErrorNegocio(f"El periodo máximo es de {meses} meses.", campo="hasta")


# ================================================================ consultas compartidas (tablero y archivos)

def reservas_del_periodo(desde: date, hasta: date):
    """Reservas CREADAS en [desde, hasta] (fecha en hora de Colombia)."""
    return ReservaReporte.objects.filter(creada__date__gte=desde, creada__date__lte=hasta)


def conteo_por_estado(reservas) -> dict[str, int]:
    base = {e: 0 for e in ESTADOS_RESERVA}
    base.update(dict(reservas.order_by().values_list("estado").annotate(n=Count("id"))))
    return base


def ingresos(reservas) -> tuple[Decimal, Decimal]:
    """(monto bruto, ingreso de la plataforma) según la nota de RF-D-ADM-05."""
    s = reservas.aggregate(bruto=Sum("monto_bruto"), plataforma=Sum("ingreso_plataforma"))
    return s["bruto"] or CERO, s["plataforma"] or CERO


def demanda(desde: date, hasta: date, por: str) -> list[dict]:
    """Reservas y monto bruto por ciudad o por tipo (v_demanda), ordenadas por número de reservas."""
    filas = (Demanda.objects.filter(fecha__gte=desde, fecha__lte=hasta).values(por)
             .annotate(reservas=Sum("reservas"), monto_bruto=Sum("monto_bruto"), ingreso_plataforma=Sum("ingreso_plataforma"))
             .order_by("-reservas", por))
    return [{"valor": f[por], "reservas": f["reservas"], "monto_bruto": f["monto_bruto"] or CERO,
             "ingreso_plataforma": f["ingreso_plataforma"] or CERO} for f in filas]


def usuarios_por_rol(hasta: date) -> dict[str, int]:
    base = {r: 0 for r in ROL_TXT}
    base.update(dict(UsuarioReporte.objects.filter(fecha_registro__date__lte=hasta).order_by().values_list("rol").annotate(n=Count("id"))))
    return base


def publicaciones_activas() -> int:
    return PublicacionReporte.objects.filter(estado="ACTIVA").count()


def _dinero(v) -> str:
    return f"{Decimal(v):.2f}"


def tablero(desde: date, hasta: date) -> dict:
    """RF-D-ADM-05.1: usuarios por rol, publicaciones ACTIVAS, reservas por estado, monto bruto e ingreso de la
    plataforma del periodo y las 5 ciudades con más reservas."""
    validar_periodo(desde, hasta)
    rs = reservas_del_periodo(desde, hasta)
    bruto, plataforma = ingresos(rs)
    return {
        "desde": desde, "hasta": hasta,
        "usuarios_por_rol": usuarios_por_rol(hasta),
        "publicaciones_activas": publicaciones_activas(),
        "reservas_por_estado": conteo_por_estado(rs),
        "reservas_total": rs.count(),
        "ingresos": {"bruto": _dinero(bruto), "plataforma": _dinero(plataforma)},
        "top_ciudades": [{"ciudad": c["valor"], "reservas": c["reservas"], "monto_bruto": _dinero(c["monto_bruto"])}
                         for c in demanda(desde, hasta, "ciudad")[:5]],
    }


# ================================================================ contenido de cada reporte

def _reporte_usuarios(desde, hasta, f) -> archivos.Reporte:
    if f.get("estado") and f["estado"] not in FILTRO_ESTADO_CUENTA:
        raise ErrorNegocio("El estado de la cuenta debe ser ACTIVA, DESACTIVADA o RESTRINGIDA.", campo="estado")
    qs = UsuarioReporte.objects.filter(fecha_registro__date__gte=desde, fecha_registro__date__lte=hasta).order_by("-fecha_registro")
    if f.get("rol"):
        qs = qs.filter(rol=f["rol"])
    qs = qs.filter(**FILTRO_ESTADO_CUENTA.get(f.get("estado"), {}))
    lista = list(qs)
    cuenta = lambda pred: sum(1 for u in lista if pred(u))  # noqa: E731
    return archivos.Reporte(
        titulo="Reporte de usuarios",
        resumen=[("Usuarios registrados en el periodo", len(lista))]
        + [(plural, cuenta(lambda u, r=r: u.rol == r)) for r, plural in (("HUESPED", "Huéspedes"), ("ANFITRION", "Anfitriones"), ("ADMINISTRADOR", "Administradores"))]
        + [(f"Cuentas {t.lower()}s", cuenta(lambda u, e=e: u.estado_cuenta == e)) for e, t in ESTADO_CUENTA_TXT.items()],
        columnas=["Nombre", "Correo", "Rol", "Ciudad", "Teléfono", "Estado", "Motivo de restricción", "Fecha de registro", "Autorizó datos"],
        filas=[[u.nombre_completo, u.correo, ROL_TXT[u.rol], u.ciudad or "", u.telefono, ESTADO_CUENTA_TXT[u.estado_cuenta],
                u.motivo_restriccion or "", timezone.localtime(u.fecha_registro).date().isoformat(),
                timezone.localtime(u.autorizacion_datos).strftime("%Y-%m-%d %H:%M")] for u in lista],
    )


def _reporte_publicaciones(desde, hasta, f) -> archivos.Reporte:
    qs = PublicacionReporte.objects.filter(creada__date__gte=desde, creada__date__lte=hasta).order_by("id")
    for campo in ("estado", "ciudad", "tipo"):
        if f.get(campo):
            qs = qs.filter(**({campo: f[campo]} if campo == "estado" else {f"{campo}__iexact": f[campo]}))
    pubs = list(qs)
    por_pub = {r["publicacion_id"]: r for r in reservas_del_periodo(desde, hasta).order_by().values("publicacion_id")
               .annotate(n=Count("id"), bruto=Sum("monto_bruto"), plataforma=Sum("ingreso_plataforma"))}
    cuenta = lambda e: sum(1 for p in pubs if p.estado == e)  # noqa: E731
    vacio = {"n": 0, "bruto": CERO, "plataforma": CERO}
    return archivos.Reporte(
        titulo="Reporte de publicaciones",
        resumen=[("Publicaciones creadas en el periodo", len(pubs))] + [(t, cuenta(e)) for e, t in ESTADO_PUB_TXT.items()],
        columnas=["Código", "Título", "Anfitrión", "Ciudad", "Tipo", "Precio por noche", "Estado", "Reservas del periodo",
                  "Monto bruto", "Ingreso plataforma", "Creada"],
        filas=[[p.id, p.titulo, p.anfitrion, p.ciudad or "", p.tipo or "", p.precio_noche or CERO, ESTADO_PUB_TXT.get(p.estado, p.estado),
                por_pub.get(p.id, vacio)["n"], por_pub.get(p.id, vacio)["bruto"] or CERO, por_pub.get(p.id, vacio)["plataforma"] or CERO,
                timezone.localtime(p.creada).date().isoformat()] for p in pubs],
        moneda=[5, 8, 9],
    )


def _reporte_reservas(desde, hasta, f) -> archivos.Reporte:
    rs = reservas_del_periodo(desde, hasta)
    bruto, plataforma = ingresos(rs)
    conteo = conteo_por_estado(rs)
    return archivos.Reporte(
        titulo="Reporte de reservas",
        resumen=[("Reservas creadas en el periodo", rs.count())]
        + [(f"Reservas {e.replace('_', ' ').lower()}", conteo[e]) for e in ESTADOS_RESERVA]
        + [("Monto bruto (COP)", archivos.pesos(bruto)), ("Ingreso de la plataforma (COP)", archivos.pesos(plataforma))],
        columnas=["Código", "Alojamiento", "Ciudad", "Huésped", "Creada", "Llegada", "Salida", "Noches", "Estado", "Total",
                  "Devolución", "Monto bruto", "Tarifa de servicio", "Ingreso plataforma"],
        filas=[[r.id, r.titulo, r.ciudad, r.huesped, timezone.localtime(r.creada).date().isoformat(), r.fecha_llegada.isoformat(),
                r.fecha_salida.isoformat(), r.noches, r.estado, r.total, r.valor_devolucion, r.monto_bruto, r.tarifa_servicio,
                r.ingreso_plataforma] for r in rs.order_by("creada", "id")],
        moneda=[9, 10, 11, 12, 13],
    )


def _reporte_ingresos(desde, hasta, f) -> archivos.Reporte:
    rs = reservas_del_periodo(desde, hasta)
    bruto, plataforma = ingresos(rs)
    por_mes: dict[str, list] = defaultdict(lambda: [0, CERO, CERO])
    for r in rs:
        m = timezone.localtime(r.creada).strftime("%Y-%m")
        por_mes[m][0] += 1
        por_mes[m][1] += r.monto_bruto
        por_mes[m][2] += r.ingreso_plataforma
    return archivos.Reporte(
        titulo="Reporte de ingresos estimados",
        resumen=[("Reservas creadas en el periodo", rs.count()), ("Monto bruto (COP)", archivos.pesos(bruto)),
                 ("Ingreso de la plataforma, tarifa de servicio (COP)", archivos.pesos(plataforma)),
                 ("Para los anfitriones (COP)", archivos.pesos(bruto - plataforma))],
        columnas=["Mes", "Reservas", "Monto bruto", "Ingreso plataforma", "Para anfitriones"],
        filas=[[m, v[0], v[1], v[2], v[1] - v[2]] for m, v in sorted(por_mes.items())],
        moneda=[2, 3, 4],
    )


def _reporte_demanda(desde, hasta, f) -> archivos.Reporte:
    por_ciudad, por_tipo = demanda(desde, hasta, "ciudad"), demanda(desde, hasta, "tipo")
    filas = ([["Ciudad", c["valor"], c["reservas"], c["monto_bruto"]] for c in por_ciudad]
             + [["Tipo de alojamiento", t["valor"], t["reservas"], t["monto_bruto"]] for t in por_tipo])
    return archivos.Reporte(
        titulo="Reporte de demanda por ciudad y por tipo de alojamiento",
        resumen=[("Ciudades con reservas", len(por_ciudad)), ("Tipos con reservas", len(por_tipo))]
        + ([("Ciudad con más reservas", por_ciudad[0]["valor"])] if por_ciudad else []),
        columnas=["Agrupación", "Valor", "Reservas", "Monto bruto"],
        filas=filas,
        moneda=[3],
    )


GENERADORES = {
    "usuarios": _reporte_usuarios, "publicaciones": _reporte_publicaciones, "reservas": _reporte_reservas,
    "ingresos": _reporte_ingresos, "demanda": _reporte_demanda,
}


def generar(admin, tipo: str, formato: str, desde: date, hasta: date, filtros: dict | None = None, ip=None) -> tuple[bytes, str, str]:
    """Arma el archivo, registra ReporteDescargado en la auditoría y lo devuelve para entregarlo.

    C4 nivel 3: "Registra cada descarga, antes de entregar el archivo". El registro se hace fuera de cualquier
    transacción y antes de devolver el contenido; si no se puede registrar, el archivo no se entrega (CA-25.2)."""
    if tipo not in GENERADORES:
        raise ErrorNegocio(f"Tipo de reporte no válido. Usa: {', '.join(TIPOS)}.", codigo=404)
    if formato not in FORMATOS:
        raise ErrorNegocio("El formato debe ser pdf o xlsx.", campo="formato")
    validar_periodo(desde, hasta)
    r = GENERADORES[tipo](desde, hasta, filtros or {})
    r.periodo = f"{desde:%d/%m/%Y} al {hasta:%d/%m/%Y}"
    r.generado_por = f"{admin.nombre_completo} ({admin.correo})"
    contenido = archivos.pdf(r) if formato == "pdf" else archivos.xlsx(r)
    nombre = f"reporte-{tipo}_{desde.isoformat()}_{hasta.isoformat()}.{formato}"
    auditoria.registrar(admin.id, "ReporteDescargado", entidad="Reporte", ip=ip,
                        detalle={"tipo": tipo, "formato": formato, "desde": desde.isoformat(), "hasta": hasta.isoformat(),
                                 "registros": len(r.filas), "archivo": nombre, "administrador": admin.nombre_completo})
    mime = "application/pdf" if formato == "pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return contenido, nombre, mime
