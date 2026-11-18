"""Interfaz pública de SRV-02 Catálogo.

Es el único módulo que otros servicios pueden importar de esta app.
Nadie fuera de apps.catalogo debe importar apps.catalogo.models (regla verificada
con import-linter en el pipeline, ADR-001).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count

from apps.comun.errores import Conflicto, ErrorNegocio, NoEncontrado, SinPermiso
from apps.comun.eventos import publicar

from .models import (
    AccionModeracion,
    Ciudad,
    ImagenPublicacion,
    PeriodoCalendario,
    PoliticaCancelacion,
    Publicacion,
    PublicacionServicio,
    ReglaAlojamiento,
    RevisionPublicacion,
    Servicio,
    ServicioAdicional,
    TipoAlojamiento,
    TipoPeriodo,
)
from .models import (
    EstadoPublicacion as E,
)

# Cambios de estado que puede pedir cada rol (máquina de estados de la publicación)
TRANSICIONES = {
    "ANFITRION": {(E.ACTIVA, E.PAUSADA), (E.PAUSADA, E.ACTIVA), (E.BORRADOR, E.PENDIENTE_REVISION)},
    "ADMINISTRADOR": {
        (E.PENDIENTE_REVISION, E.ACTIVA), (E.PENDIENTE_REVISION, E.BORRADOR),
        (E.ACTIVA, E.PAUSADA), (E.PAUSADA, E.ACTIVA),
        (E.ACTIVA, E.BLOQUEADA), (E.PAUSADA, E.BLOQUEADA), (E.BLOQUEADA, E.PAUSADA),
    },
}
ACCION = {
    (E.PENDIENTE_REVISION, E.ACTIVA): AccionModeracion.APROBAR, (E.PENDIENTE_REVISION, E.BORRADOR): AccionModeracion.DEVOLVER,
    (E.ACTIVA, E.PAUSADA): AccionModeracion.PAUSAR, (E.PAUSADA, E.ACTIVA): AccionModeracion.REACTIVAR,
    (E.ACTIVA, E.BLOQUEADA): AccionModeracion.BLOQUEAR, (E.PAUSADA, E.BLOQUEADA): AccionModeracion.BLOQUEAR,
    (E.BLOQUEADA, E.PAUSADA): AccionModeracion.DESBLOQUEAR,
}
EVENTO = {
    AccionModeracion.APROBAR: "PublicacionAprobada", AccionModeracion.DEVOLVER: "PublicacionDevuelta",
    AccionModeracion.BLOQUEAR: "PublicacionBloqueada", AccionModeracion.DESBLOQUEAR: "PublicacionDesbloqueada",
    AccionModeracion.PAUSAR: "PublicacionPausada", AccionModeracion.REACTIVAR: "PublicacionReactivada",
}
EDITABLE_POR_ANFITRION = {E.BORRADOR, E.ACTIVA, E.PAUSADA}

# Catálogo no depende de Reservas (sección 3.3). Para mostrar las noches reservadas en el calendario
# y no bloquear fechas con reserva (CA-09.2), Reservas registra aquí su consulta al iniciar la app.
_noches_ocupadas = lambda publicacion_id, desde, hasta: set()  # noqa: E731


def registrar_consulta_ocupacion(funcion) -> None:
    global _noches_ocupadas
    _noches_ocupadas = funcion


# ================================================================ consultas para otros servicios

def existe_ciudad(ciudad_id: int) -> bool:
    return Ciudad.objects.filter(pk=ciudad_id).exists()


def catalogos() -> dict:
    return {
        "ciudades": list(Ciudad.objects.values("id", "nombre", "departamento")),
        "tipos": list(TipoAlojamiento.objects.values("id", "nombre")),
        "servicios": list(Servicio.objects.values("id", "nombre")),
    }


def ids_publicaciones_de(anfitrion_id: int) -> list[int]:
    return list(Publicacion.objects.filter(anfitrion_id=anfitrion_id).values_list("id", flat=True))


def resumen_publicacion(publicacion_id: int) -> dict | None:
    p = Publicacion.objects.select_related("ciudad", "tipo_alojamiento").filter(pk=publicacion_id).first()
    return _resumen(p) if p else None


def publicaciones_para_reporte(desde=None, hasta=None, estado=None, ciudad_id=None, tipo_id=None) -> list[dict]:
    """Publicaciones creadas en el periodo, sin borradores (solo los ve su dueño)."""
    qs = Publicacion.objects.select_related("ciudad", "tipo_alojamiento").exclude(estado=E.BORRADOR).order_by("id")
    if desde:
        qs = qs.filter(creada__date__gte=desde)
    if hasta:
        qs = qs.filter(creada__date__lte=hasta)
    if estado:
        qs = qs.filter(estado=estado)
    if ciudad_id:
        qs = qs.filter(ciudad_id=ciudad_id)
    if tipo_id:
        qs = qs.filter(tipo_alojamiento_id=tipo_id)
    return [_resumen(p) for p in qs]


def conteo_por_estado() -> dict[str, int]:
    base = {e: 0 for e in E.values}
    base.update(dict(Publicacion.objects.values_list("estado").annotate(n=Count("id"))))
    return base


def nombres_ciudades() -> dict[int, str]:
    return dict(Ciudad.objects.values_list("id", "nombre"))


def _resumen(p: Publicacion) -> dict:
    return {
        "id": p.id, "titulo": p.titulo, "anfitrion": p.anfitrion_id, "estado": p.estado,
        "ciudad": p.ciudad_id, "ciudad_nombre": p.ciudad.nombre if p.ciudad else None,
        "tipo": p.tipo_alojamiento_id, "tipo_nombre": p.tipo_alojamiento.nombre if p.tipo_alojamiento else None,
        "politica": p.politica_id, "precio_noche": p.precio_noche, "tarifa_limpieza": p.tarifa_limpieza,
        "descuento_porcentaje": p.descuento_porcentaje, "descuento_min_noches": p.descuento_min_noches,
        "capacidad": p.capacidad, "creada": p.creada,
    }


# ================================================================ reglas de la publicación

def faltantes(p: Publicacion) -> list[str]:
    """Datos obligatorios para enviar a revisión (RF-D-ALO-01.2)."""
    f = []
    if not p.titulo.strip():
        f.append("título")
    if not p.descripcion.strip():
        f.append("descripción")
    if not p.ciudad_id:
        f.append("ciudad")
    if not p.ubicacion_textual.strip():
        f.append("ubicación")
    if not p.tipo_alojamiento_id:
        f.append("tipo de alojamiento")
    if not p.capacidad or p.capacidad <= 0:
        f.append("capacidad mayor que 0")
    if not p.precio_noche or p.precio_noche <= 0:
        f.append("precio por noche")
    if p.tarifa_limpieza is None:
        f.append("tarifa de limpieza")
    if not p.reglas.exists():
        f.append("al menos una regla del alojamiento")
    if not p.politica_id:
        f.append("política de cancelación")
    if not p.imagenes.exists():
        f.append("al menos una imagen")
    return f


def puede_ver(usuario, p: Publicacion) -> bool:
    return usuario.rol == "ADMINISTRADOR" or (usuario.rol == "ANFITRION" and p.anfitrion_id == usuario.id)


def obtener(usuario, publicacion_id: int) -> Publicacion:
    p = Publicacion.objects.filter(pk=publicacion_id).first()
    if not p:
        raise NoEncontrado("La publicación no existe.")
    if not puede_ver(usuario, p):
        _negar(usuario, p, "Ver o modificar una publicación ajena")
        raise SinPermiso("Solo el anfitrión dueño o un administrador pueden modificarla (CA-05.3).")
    return p


def _negar(usuario, p: Publicacion, motivo: str) -> None:
    publicar("AccesoDenegado", usuario_id=usuario.id, entidad="Publicacion", entidad_id=p.id, resultado="FALLO", detalle={"motivo": motivo})


def _validar_datos(d: dict) -> None:
    if "capacidad" in d and d["capacidad"] is not None and d["capacidad"] <= 0:
        raise ErrorNegocio("La capacidad debe ser mayor que cero.", campo="capacidad")
    if "precio_noche" in d and d["precio_noche"] is not None and d["precio_noche"] <= 0:
        raise ErrorNegocio("El precio por noche debe ser mayor que cero.", campo="precio_noche")
    if "tarifa_limpieza" in d and d["tarifa_limpieza"] is not None and d["tarifa_limpieza"] < 0:
        raise ErrorNegocio("La tarifa de limpieza no puede ser negativa.", campo="tarifa_limpieza")
    pct, noches = d.get("descuento_porcentaje"), d.get("descuento_min_noches")
    if ("descuento_porcentaje" in d or "descuento_min_noches" in d) and ((pct is None) != (noches is None)):
        raise ErrorNegocio("Indica el porcentaje y desde cuántas noches, o deja ambos vacíos.", campo="descuento")
    if pct is not None and not (Decimal("0") < pct <= Decimal("100")):
        raise ErrorNegocio("El descuento debe estar entre 1 y 100 %.", campo="descuento")
    if noches is not None and noches < 2:
        raise ErrorNegocio("El descuento aplica desde 2 noches o más.", campo="descuento")
    for a in d.get("servicios_adicionales") or []:
        if not (a.get("nombre") or "").strip():
            raise ErrorNegocio("Cada servicio adicional necesita un nombre.", campo="servicios_adicionales")
        if a.get("precio") is None or a["precio"] < 0:
            raise ErrorNegocio("El precio de un servicio adicional no puede ser negativo.", campo="servicios_adicionales")
    for campo, modelo in (("ciudad", Ciudad), ("tipo_alojamiento", TipoAlojamiento), ("politica", PoliticaCancelacion)):
        if d.get(campo) is not None and not modelo.objects.filter(pk=d[campo]).exists():
            raise ErrorNegocio(f"El valor de {campo.replace('_', ' ')} no existe.", campo=campo)
    if d.get("servicios") and Servicio.objects.filter(pk__in=d["servicios"]).count() != len(set(d["servicios"])):
        raise ErrorNegocio("Algún servicio no existe.", campo="servicios")


SIMPLES = ("titulo", "descripcion", "ubicacion_textual", "capacidad", "precio_noche", "tarifa_limpieza",
           "descuento_porcentaje", "descuento_min_noches")


def _aplicar(p: Publicacion, d: dict) -> None:
    for c in SIMPLES:
        if c in d:
            setattr(p, c, d[c] if d[c] is not None or c not in ("descripcion", "ubicacion_textual") else "")
    for c in ("ciudad", "tipo_alojamiento", "politica"):
        if c in d:
            setattr(p, f"{c}_id", d[c])
    p.save()
    if "servicios" in d:
        PublicacionServicio.objects.filter(publicacion=p).delete()
        PublicacionServicio.objects.bulk_create([PublicacionServicio(publicacion=p, servicio_id=s) for s in set(d["servicios"])])
    if "servicios_adicionales" in d:
        p.servicios_adicionales.all().delete()
        ServicioAdicional.objects.bulk_create(
            [ServicioAdicional(publicacion=p, nombre=a["nombre"].strip(), precio=a["precio"]) for a in d["servicios_adicionales"]]
        )
    if "reglas" in d:  # ReglaAlojamiento: se guardan en el orden recibido, sin vacías
        p.reglas.all().delete()
        textos = [r.strip() for r in d["reglas"] if (r or "").strip()]
        ReglaAlojamiento.objects.bulk_create([ReglaAlojamiento(publicacion=p, descripcion=t, orden=i + 1) for i, t in enumerate(textos)])
    if "imagenes" in d:
        p.imagenes.all().delete()
        ImagenPublicacion.objects.bulk_create([ImagenPublicacion(publicacion=p, ruta=r, orden=i + 1) for i, r in enumerate(d["imagenes"])])


# ================================================================ CU-ALO-01 Crear · CU-ALO-04 Editar

def crear(anfitrion, d: dict) -> Publicacion:
    if not (d.get("titulo") or "").strip():
        raise ErrorNegocio("Escribe un título.", campo="titulo")
    _validar_datos(d)
    with transaction.atomic():
        p = Publicacion(anfitrion=anfitrion, estado=E.BORRADOR)
        _aplicar(p, d)
        publicar("PublicacionCreada", usuario_id=anfitrion.id, entidad="Publicacion", entidad_id=p.id)
    return p


def actualizar(usuario, publicacion_id: int, d: dict) -> Publicacion:
    p = obtener(usuario, publicacion_id)
    if usuario.rol == "ANFITRION" and p.estado not in EDITABLE_POR_ANFITRION:
        raise ErrorNegocio(f"No puedes editar una publicación {p.estado}.", codigo=409)
    if "titulo" in d and not (d["titulo"] or "").strip():
        raise ErrorNegocio("Escribe un título.", campo="titulo")
    _validar_datos({**{c: getattr(p, c) for c in ("descuento_porcentaje", "descuento_min_noches")}, **d})
    with transaction.atomic():
        _aplicar(p, d)
        # La publicación conserva su estado (sigue ACTIVA sin volver a revisión). Fuera de BORRADOR debe seguir completa.
        if p.estado != E.BORRADOR and (f := faltantes(p)):
            raise ErrorNegocio("Falta: " + ", ".join(f) + ".", extra={"faltantes": f})
        publicar("PublicacionEditada", usuario_id=usuario.id, entidad="Publicacion", entidad_id=p.id)
    return p


# ================================================================ cambios de estado

def cambiar_estado(usuario, publicacion_id: int, nuevo: str, observacion: str | None = None) -> Publicacion:
    p = obtener(usuario, publicacion_id)
    anterior = p.estado
    if (anterior, nuevo) not in TRANSICIONES.get(usuario.rol, set()):
        _negar(usuario, p, f"{anterior} → {nuevo}")
        raise ErrorNegocio(f"No se puede pasar de {anterior} a {nuevo}.", codigo=409)
    if nuevo == E.PENDIENTE_REVISION and (f := faltantes(p)):
        raise ErrorNegocio("No se puede enviar a revisión. Falta: " + ", ".join(f) + ".", extra={"faltantes": f})
    accion = ACCION.get((anterior, nuevo)) if usuario.rol == "ADMINISTRADOR" else None
    if accion in (AccionModeracion.DEVOLVER, AccionModeracion.BLOQUEAR) and not (observacion or "").strip():
        campo = "observacion" if accion == AccionModeracion.DEVOLVER else "motivo"
        raise ErrorNegocio("Escribe la observación para el anfitrión." if campo == "observacion" else "Escribe el motivo del bloqueo.", campo=campo)
    with transaction.atomic():
        p = Publicacion.objects.select_for_update().get(pk=p.pk)
        if p.estado != anterior:
            raise Conflicto("La publicación cambió mientras tanto. Vuelve a cargarla.")
        p.estado = nuevo
        p.save(update_fields=["estado", "actualizada"])
        if accion:
            RevisionPublicacion.objects.create(publicacion=p, administrador=usuario, accion=accion, observacion=(observacion or "").strip() or None)
        nombre = EVENTO[accion] if accion else {
            E.PENDIENTE_REVISION: "PublicacionEnviadaARevision", E.PAUSADA: "PublicacionPausada", E.ACTIVA: "PublicacionReactivada",
        }[nuevo]
        publicar(nombre, usuario_id=usuario.id, entidad="Publicacion", entidad_id=p.id,
                 detalle={"de": anterior, "a": nuevo, **({"observacion": observacion} if observacion else {})})
    return p


def revisar(admin, publicacion_id: int, accion: str, observacion: str | None) -> Publicacion:
    destino = {AccionModeracion.APROBAR: E.ACTIVA, AccionModeracion.DEVOLVER: E.BORRADOR}.get(accion)
    if not destino:
        raise ErrorNegocio("La acción debe ser APROBAR o DEVOLVER.", campo="accion")
    p = obtener(admin, publicacion_id)
    if p.estado != E.PENDIENTE_REVISION:
        raise Conflicto("Esta publicación ya no está pendiente de revisión.")
    return cambiar_estado(admin, publicacion_id, destino, observacion)


def bloquear(admin, publicacion_id: int, motivo: str) -> Publicacion:
    return cambiar_estado(admin, publicacion_id, E.BLOQUEADA, motivo)


def desbloquear(admin, publicacion_id: int) -> Publicacion:
    return cambiar_estado(admin, publicacion_id, E.PAUSADA)


def listar_admin(estado: str | None = None):
    qs = Publicacion.objects.exclude(estado=E.BORRADOR).select_related("ciudad", "tipo_alojamiento")
    return qs.filter(estado=estado) if estado else qs


def mis_publicaciones(anfitrion, estado=None):
    qs = Publicacion.objects.filter(anfitrion=anfitrion).select_related("ciudad", "tipo_alojamiento")
    return qs.filter(estado=estado) if estado else qs


# ================================================================ CU-ALO-06 Calendario (PeriodoCalendario)

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


def calendario(usuario, publicacion_id: int, desde: date, hasta: date) -> dict:
    p = _publicacion_del_anfitrion(usuario, publicacion_id)
    periodos = p.periodos.filter(fecha_fin__gt=desde, fecha_inicio__lt=hasta)
    return {
        "publicacion": p.id,
        "periodos": [{"fecha_inicio": x.fecha_inicio, "fecha_fin": x.fecha_fin, "tipo": x.tipo} for x in periodos],
        "noches_reservadas": sorted(_noches_ocupadas(p.id, desde, hasta)),
    }


def modificar_calendario(usuario, publicacion_id: int, inicio: date, fin: date, tipo: str) -> dict:
    """NO_DISPONIBLE cierra [inicio, fin); DISPONIBLE lo vuelve a abrir. Los periodos se guardan
    unificados en rangos de noches no disponibles (RF-D-ALO-02.2)."""
    if fin <= inicio:
        raise ErrorNegocio("La fecha final debe ser posterior a la inicial.", campo="fecha_fin")
    p = _publicacion_del_anfitrion(usuario, publicacion_id)
    nuevas = set(_dias(inicio, fin))
    with transaction.atomic():
        Publicacion.objects.select_for_update().filter(pk=p.pk).first()
        if tipo == TipoPeriodo.NO_DISPONIBLE:
            choque = nuevas & _noches_ocupadas(p.id, inicio, fin)
            if choque:  # CA-09.2
                raise Conflicto("No se pueden bloquear fechas con una reserva CONFIRMADA.", extra={"fechas": sorted(choque)})
        actuales = {d for x in p.periodos.filter(tipo=TipoPeriodo.NO_DISPONIBLE) for d in _dias(x.fecha_inicio, x.fecha_fin)}
        resultado = actuales | nuevas if tipo == TipoPeriodo.NO_DISPONIBLE else actuales - nuevas
        p.periodos.all().delete()
        PeriodoCalendario.objects.bulk_create(
            [PeriodoCalendario(publicacion=p, fecha_inicio=a, fecha_fin=b, tipo=TipoPeriodo.NO_DISPONIBLE) for a, b in _rangos(resultado)]
        )
        publicar("CalendarioActualizado", usuario_id=usuario.id, entidad="Publicacion", entidad_id=p.id,
                 detalle={"tipo": tipo, "desde": inicio.isoformat(), "hasta": fin.isoformat()})
    return calendario(usuario, publicacion_id, inicio, fin)


def _publicacion_del_anfitrion(usuario, publicacion_id: int) -> Publicacion:
    p = Publicacion.objects.filter(pk=publicacion_id).first()
    if not p:
        raise NoEncontrado("La publicación no existe.")
    if p.anfitrion_id != usuario.id:
        _negar(usuario, p, "Calendario de una publicación ajena")
        raise SinPermiso("Solo el anfitrión dueño administra el calendario.")
    return p
