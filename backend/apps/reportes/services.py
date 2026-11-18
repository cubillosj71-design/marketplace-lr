"""Interfaz pública de SRV-09 Reportes.

Es el único módulo que otros servicios pueden importar de esta app.
Nadie fuera de apps.reportes debe importar apps.reportes.models (regla verificada
con import-linter en el pipeline, ADR-001).

Reportes solo lee: compone datos de Identidad, Catálogo y Reservas a través de sus interfaces.
El tablero y los archivos usan las mismas funciones, así sus totales coinciden (CA-25.1, ADR-009).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.conf import settings

from apps.auditoria import services as auditoria
from apps.catalogo import services as catalogo
from apps.comun.errores import ErrorNegocio
from apps.identidad import services as identidad
from apps.reservas import services as reservas

from . import archivos

TIPOS = ("usuarios", "publicaciones", "reservas", "ingresos", "demanda")
FORMATOS = ("pdf", "xlsx")
CUENTAN = ("CONFIRMADA", "COMPLETADA")  # reservas que generan ingreso
ROL_TXT = {"HUESPED": "Huésped", "ANFITRION": "Anfitrión", "ADMINISTRADOR": "Administrador"}
# Estado de la cuenta para mostrar en el reporte. No es una columna: se deriva de usuario.activa y de
# una restricción vigente (MOD-01).
ESTADO_CUENTA_TXT = {"ACTIVA": "Activa", "DESACTIVADA": "Desactivada", "RESTRINGIDA": "Restringida"}
FILTRO_ESTADO_CUENTA = {"ACTIVA": {"activa": True, "restringida": False}, "DESACTIVADA": {"activa": False}, "RESTRINGIDA": {"restringida": True}}
ESTADO_PUB_TXT = {"PENDIENTE_REVISION": "En revisión", "ACTIVA": "Activa", "PAUSADA": "Pausada", "BLOQUEADA": "Bloqueada", "BORRADOR": "Borrador"}


def validar_periodo(desde: date, hasta: date) -> None:
    if desde > hasta:
        raise ErrorNegocio("La fecha inicial no puede ser posterior a la final.", campo="desde")
    meses = settings.MESES_MAXIMOS_REPORTE
    limite = _sumar_meses(desde, meses)
    if hasta >= limite:
        raise ErrorNegocio(f"El periodo máximo es de {meses} meses.", campo="hasta")


def _sumar_meses(d: date, meses: int) -> date:
    m = d.month - 1 + meses
    anio, mes = d.year + m // 12, m % 12 + 1
    dias = [31, 29 if anio % 4 == 0 and (anio % 100 != 0 or anio % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mes - 1]
    return date(anio, mes, min(d.day, dias))


# ---------------------------------------------------------------- cálculos compartidos

def _ingresos(lista_reservas) -> tuple[Decimal, Decimal]:
    validas = [r for r in lista_reservas if r["estado"] in CUENTAN]
    return sum((r["total"] for r in validas), Decimal("0")), sum((r["tarifa_servicio"] for r in validas), Decimal("0"))


def _demanda(lista_reservas) -> tuple[list, list]:
    pubs = {p["id"]: p for p in catalogo.publicaciones_para_reporte()}
    por_ciudad: dict[str, dict] = defaultdict(lambda: {"reservas": 0, "ingreso": Decimal("0")})
    por_tipo: dict[str, dict] = defaultdict(lambda: {"reservas": 0, "ingreso": Decimal("0")})
    for r in lista_reservas:
        if r["estado"] not in CUENTAN or r["publicacion"] not in pubs:
            continue
        p = pubs[r["publicacion"]]
        for clave, destino in ((p["ciudad_nombre"] or "Sin ciudad", por_ciudad), (p["tipo_nombre"] or "Sin tipo", por_tipo)):
            destino[clave]["reservas"] += 1
            destino[clave]["ingreso"] += r["total"]
    orden = lambda d: sorted(d.items(), key=lambda kv: (-kv[1]["reservas"], kv[0]))  # noqa: E731
    return orden(por_ciudad), orden(por_tipo)


def tablero(desde: date, hasta: date) -> dict:
    """RF-D-ADM-05.1: usuarios por rol, publicaciones ACTIVAS, reservas por estado, ingresos y top-5 ciudades."""
    validar_periodo(desde, hasta)
    lista = reservas.reservas_para_reporte(desde, hasta)
    bruto, plataforma = _ingresos(lista)
    por_ciudad, _ = _demanda(lista)
    return {
        "desde": desde, "hasta": hasta,
        "usuarios_por_rol": identidad.conteo_por_rol(hasta),
        "publicaciones_activas": catalogo.conteo_por_estado()["ACTIVA"],
        "reservas_por_estado": reservas.conteo_por_estado(desde, hasta),
        "ingresos": {"bruto": f"{bruto:.2f}", "plataforma": f"{plataforma:.2f}"},  # montos como texto, igual que el resto de la API
        "top_ciudades": [{"ciudad": c, "reservas": v["reservas"], "ingreso": f"{v['ingreso']:.2f}"} for c, v in por_ciudad[:5]],
    }


# ---------------------------------------------------------------- contenido de cada reporte

def _estado_cuenta(u: dict) -> str:
    return "RESTRINGIDA" if u["restringida"] else ("ACTIVA" if u["activa"] else "DESACTIVADA")


def _reporte_usuarios(desde, hasta, f) -> archivos.Reporte:
    if f.get("estado") and f["estado"] not in FILTRO_ESTADO_CUENTA:
        raise ErrorNegocio("El estado de la cuenta debe ser ACTIVA, DESACTIVADA o RESTRINGIDA.", campo="estado")
    lista = identidad.usuarios_registrados(desde, hasta, f.get("rol"), **FILTRO_ESTADO_CUENTA.get(f.get("estado"), {}))
    for u in lista:
        u["estado"] = _estado_cuenta(u)
    cuenta = lambda clave, valor: sum(1 for u in lista if u[clave] == valor)  # noqa: E731
    return archivos.Reporte(
        titulo="Reporte de usuarios",
        resumen=[("Usuarios registrados en el periodo", len(lista))]
        + [(plural, cuenta("rol", r)) for r, plural in (("HUESPED", "Huéspedes"), ("ANFITRION", "Anfitriones"), ("ADMINISTRADOR", "Administradores"))]
        + [(f"Cuentas {ESTADO_CUENTA_TXT[e].lower()}s", cuenta("estado", e)) for e in ESTADO_CUENTA_TXT],
        columnas=["Nombre", "Correo", "Rol", "Ciudad", "Teléfono", "Estado", "Motivo de restricción", "Fecha de registro", "Autorizó datos"],
        filas=[[u["nombre_completo"], u["correo"], ROL_TXT[u["rol"]], u["ciudad"] or "", u["telefono"],
                ESTADO_CUENTA_TXT[u["estado"]], u["motivo_restriccion"] or "", u["fecha_registro"][:10], u["autorizacion_datos"][:16].replace("T", " ")]
               for u in lista],
    )


def _reporte_publicaciones(desde, hasta, f) -> archivos.Reporte:
    pubs = catalogo.publicaciones_para_reporte(desde, hasta, f.get("estado"), f.get("ciudad"), f.get("tipo"))
    nombres = identidad.nombres(p["anfitrion"] for p in pubs)
    rs = reservas.reservas_para_reporte(publicaciones_ids=[p["id"] for p in pubs])
    por_pub: dict[int, list] = defaultdict(list)
    for r in rs:
        if r["estado"] in CUENTAN:
            por_pub[r["publicacion"]].append(r)
    cuenta = lambda e: sum(1 for p in pubs if p["estado"] == e)  # noqa: E731
    return archivos.Reporte(
        titulo="Reporte de publicaciones",
        resumen=[("Publicaciones creadas en el periodo", len(pubs))]
        + [(ESTADO_PUB_TXT[e], cuenta(e)) for e in ("PENDIENTE_REVISION", "ACTIVA", "PAUSADA", "BLOQUEADA")],
        columnas=["Código", "Título", "Anfitrión", "Ciudad", "Tipo", "Precio por noche", "Estado", "Reservas", "Ingreso bruto", "Ingreso plataforma", "Creada"],
        filas=[[p["id"], p["titulo"], nombres.get(p["anfitrion"], ""), p["ciudad_nombre"] or "", p["tipo_nombre"] or "", p["precio_noche"],
                ESTADO_PUB_TXT[p["estado"]], len(por_pub[p["id"]]), sum((r["total"] for r in por_pub[p["id"]]), Decimal("0")),
                sum((r["tarifa_servicio"] for r in por_pub[p["id"]]), Decimal("0")), p["creada"].date().isoformat()] for p in pubs],
        moneda=[5, 8, 9],
    )


def _reporte_reservas(desde, hasta, f) -> archivos.Reporte:
    lista = reservas.reservas_para_reporte(desde, hasta)
    titulos = {p["id"]: p["titulo"] for p in catalogo.publicaciones_para_reporte()}
    nombres = identidad.nombres(r["huesped"] for r in lista)
    conteo = reservas.conteo_por_estado(desde, hasta)
    return archivos.Reporte(
        titulo="Reporte de reservas",
        resumen=[("Reservas con llegada en el periodo", len(lista))] + [(f"Reservas {e.replace('_', ' ').lower()}", n) for e, n in conteo.items()],
        columnas=["Código", "Alojamiento", "Huésped", "Llegada", "Salida", "Noches", "Estado", "Total", "Tarifa de servicio"],
        filas=[[r["id"], titulos.get(r["publicacion"], f"#{r['publicacion']}"), nombres.get(r["huesped"], ""), r["fecha_llegada"].isoformat(),
                r["fecha_salida"].isoformat(), r["noches"], r["estado"], r["total"], r["tarifa_servicio"]] for r in lista],
        moneda=[7, 8],
    )


def _reporte_ingresos(desde, hasta, f) -> archivos.Reporte:
    lista = [r for r in reservas.reservas_para_reporte(desde, hasta) if r["estado"] in CUENTAN]
    bruto, plataforma = _ingresos(lista)
    por_mes: dict[str, list] = defaultdict(lambda: [0, Decimal("0"), Decimal("0")])
    for r in lista:
        m = r["fecha_llegada"].strftime("%Y-%m")
        por_mes[m][0] += 1
        por_mes[m][1] += r["total"]
        por_mes[m][2] += r["tarifa_servicio"]
    return archivos.Reporte(
        titulo="Reporte de ingresos estimados",
        resumen=[("Reservas confirmadas o completadas", len(lista)), ("Ingreso bruto (COP)", archivos.pesos(bruto)),
                 ("Ingreso de la plataforma, tarifa de servicio (COP)", archivos.pesos(plataforma)),
                 ("Para los anfitriones (COP)", archivos.pesos(bruto - plataforma))],
        columnas=["Mes", "Reservas", "Ingreso bruto", "Ingreso plataforma", "Para anfitriones"],
        filas=[[m, v[0], v[1], v[2], v[1] - v[2]] for m, v in sorted(por_mes.items())],
        moneda=[2, 3, 4],
    )


def _reporte_demanda(desde, hasta, f) -> archivos.Reporte:
    por_ciudad, por_tipo = _demanda(reservas.reservas_para_reporte(desde, hasta))
    filas = [["Ciudad", c, v["reservas"], v["ingreso"]] for c, v in por_ciudad] + [["Tipo de alojamiento", t, v["reservas"], v["ingreso"]] for t, v in por_tipo]
    return archivos.Reporte(
        titulo="Reporte de demanda por ciudad y tipo",
        resumen=[("Ciudades con reservas", len(por_ciudad)), ("Tipos con reservas", len(por_tipo))]
        + ([("Ciudad con más reservas", por_ciudad[0][0])] if por_ciudad else []),
        columnas=["Agrupación", "Valor", "Reservas", "Ingreso bruto"],
        filas=filas,
        moneda=[3],
    )


GENERADORES = {
    "usuarios": _reporte_usuarios, "publicaciones": _reporte_publicaciones, "reservas": _reporte_reservas,
    "ingresos": _reporte_ingresos, "demanda": _reporte_demanda,
}


def generar(admin, tipo: str, formato: str, desde: date, hasta: date, filtros: dict | None = None, ip=None) -> tuple[bytes, str, str]:
    """Devuelve (contenido, nombre de archivo, tipo MIME) y registra ReporteDescargado en la auditoría (CA-25.2)."""
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
                                 "registros": len(r.filas), "archivo": nombre})
    mime = "application/pdf" if formato == "pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return contenido, nombre, mime
