"""Interfaz pública de SRV-02 Catálogo.

Es el único módulo que otros servicios pueden importar de esta app.
Nadie fuera de apps.catalogo debe importar apps.catalogo.models (regla verificada
con import-linter en el pipeline, ADR-001).
"""

from __future__ import annotations

import unicodedata
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, OuterRef, ProtectedError, Subquery

from apps.auditoria import services as auditoria
from apps.comun.errores import Conflicto, ErrorNegocio, NoEncontrado, SinPermiso
from apps.comun.eventos import EVENTOS_DE_DOMINIO, publicar_evento

from .models import (
    AccionModeracion,
    Ciudad,
    ImagenPublicacion,
    PoliticaCancelacion,
    Publicacion,
    PublicacionBuscable,
    PublicacionServicio,
    ReglaAlojamiento,
    RevisionPublicacion,
    Servicio,
    ServicioAdicional,
    TipoAlojamiento,
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

# ================================================================ consultas para otros servicios

def es_ciudad_registrada(ciudad_id: int) -> bool:
    return Ciudad.objects.filter(pk=ciudad_id).exists()


def calcular_clave_alfabetica(texto: str) -> str:
    """Clave para ordenar en español: sin tildes y sin mayúsculas ("Popayán" va entre "Pereira" y "Salento")."""
    return "".join(c for c in unicodedata.normalize("NFD", texto.casefold()) if unicodedata.category(c) != "Mn")


def listar_catalogos() -> dict:
    return {
        # En orden alfabético en español (sin importar tildes ni la intercalación de la base): San Andrés, San Gil,
        # Santa Fe de Antioquia, Santa Marta
        "ciudades": sorted(Ciudad.objects.values("id", "nombre", "departamento"), key=lambda c: calcular_clave_alfabetica(c["nombre"])),
        "tipos": list(TipoAlojamiento.objects.values("id", "nombre")),
        "servicios": list(Servicio.objects.values("id", "nombre")),
        "politicas": [_serializar_politica(p) for p in PoliticaCancelacion.objects.filter(activa=True).prefetch_related("tramos").order_by("id")],
    }


def _serializar_politica(p: PoliticaCancelacion) -> dict:
    return {"id": p.id, "nombre": p.nombre, "descripcion": p.descripcion,
            "tramos": [{"dias_minimos": t.dias_minimos, "dias_maximos": t.dias_maximos,
                        "porcentaje_devolucion": f"{t.porcentaje_devolucion:.2f}"}
                       for t in sorted(p.tramos.all(), key=lambda t: -t.dias_minimos)]}


def obtener_politica_con_tramos(politica_id: int) -> dict | None:
    """La política de cancelación con sus tramos, de mayor a menor anticipación (detalle de la reserva)."""
    p = PoliticaCancelacion.objects.prefetch_related("tramos").filter(pk=politica_id).first()
    return _serializar_politica(p) if p else None


def obtener_bloqueos_de_publicaciones(ids) -> dict[int, dict]:
    """{id: {"motivo", "fecha"}} del último bloqueo de cada publicación (historial de revisiones, acción BLOQUEAR), en
    una sola consulta (DISTINCT ON). Las publicaciones que nunca se bloquearon no aparecen."""
    filas = (RevisionPublicacion.objects.filter(publicacion_id__in=list(ids), accion=AccionModeracion.BLOQUEAR)
             .order_by("publicacion_id", "-fecha", "-id").distinct("publicacion_id")
             .values("publicacion_id", "observacion", "fecha"))
    return {f["publicacion_id"]: {"motivo": f["observacion"], "fecha": f["fecha"]} for f in filas}


def obtener_portadas_y_ciudades(ids) -> dict[int, dict]:
    """{id: {"portada", "ciudad"}} de varias publicaciones en una sola consulta (listado de Mis reservas).
    La portada es la imagen de menor orden (la 1); None si la publicación no tiene imágenes o ciudad."""
    portada = ImagenPublicacion.objects.filter(publicacion_id=OuterRef("pk")).order_by("orden", "id").values("ruta")[:1]
    filas = (Publicacion.objects.filter(pk__in=list(ids)).annotate(portada=Subquery(portada))
             .values("id", "portada", "ciudad__nombre"))
    return {f["id"]: {"portada": f["portada"], "ciudad": f["ciudad__nombre"]} for f in filas}


def listar_ids_publicaciones_de(anfitrion_id: int) -> list[int]:
    return list(Publicacion.objects.filter(anfitrion_id=anfitrion_id).values_list("id", flat=True))


def obtener_resumen_publicacion(publicacion_id: int) -> dict | None:
    p = Publicacion.objects.select_related("ciudad", "tipo_alojamiento").filter(pk=publicacion_id).first()
    return _resumir_publicacion(p) if p else None


def listar_publicaciones_para_reporte(desde=None, hasta=None, estado=None, ciudad_id=None, tipo_id=None) -> list[dict]:
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
    return [_resumir_publicacion(p) for p in qs]


def contar_publicaciones_por_estado() -> dict[str, int]:
    base = {e: 0 for e in E.values}
    base.update(dict(Publicacion.objects.values_list("estado").annotate(n=Count("id"))))
    return base


def listar_publicaciones_buscables():
    """Vista v_publicacion_buscable (solo lectura): ACTIVAS de anfitriones con cuenta activa y sin
    restricción vigente (CA-04.3, CA-21.2). Búsqueda la combina con otras vistas."""
    return PublicacionBuscable.objects.all()


def es_buscable(publicacion_id: int) -> bool:
    return PublicacionBuscable.objects.filter(pk=publicacion_id).exists()


def obtener_datos_para_cotizar(publicacion_id: int, bloquear: bool = False) -> dict | None:
    """Precios y reglas que usa Reservas para cotizar y reservar (RF-D-RES-02.1).
    Con bloquear=True toma la fila con SELECT ... FOR UPDATE (debe ir dentro de transaction.atomic):
    así dos reservas de la misma publicación se procesan una después de la otra (CA-13.2)."""
    qs = Publicacion.objects.select_for_update() if bloquear else Publicacion.objects
    p = qs.filter(pk=publicacion_id).first()
    if not p:
        return None
    return {
        "id": p.id, "titulo": p.titulo, "anfitrion": p.anfitrion_id, "estado": p.estado, "politica": p.politica_id,
        "capacidad": p.capacidad, "precio_noche": p.precio_noche, "tarifa_limpieza": p.tarifa_limpieza,
        "descuento_porcentaje": p.descuento_porcentaje, "descuento_min_noches": p.descuento_min_noches,
        "buscable": es_buscable(p.id),
        "adicionales": {a.id: {"nombre": a.nombre, "precio": a.precio} for a in p.servicios_adicionales.filter(activo=True)},
    }


def obtener_detalle_publico(publicacion_id: int) -> dict | None:
    """Datos completos para el detalle público (HU-11): servicios, adicionales con precio, reglas en
    orden, imágenes y la política de cancelación con sus tramos (CA-11.3)."""
    p = (Publicacion.objects.select_related("ciudad", "tipo_alojamiento", "politica")
         .filter(pk=publicacion_id).first())
    if not p:
        return None
    politica = p.politica
    return {
        "id": p.id, "titulo": p.titulo, "descripcion": p.descripcion, "anfitrion": p.anfitrion_id,
        "ciudad": p.ciudad.nombre if p.ciudad else None, "ciudad_id": p.ciudad_id, "ubicacion_textual": p.ubicacion_textual,
        "tipo": p.tipo_alojamiento.nombre if p.tipo_alojamiento else None, "tipo_alojamiento_id": p.tipo_alojamiento_id,
        "capacidad": p.capacidad, "precio_noche": p.precio_noche, "tarifa_limpieza": p.tarifa_limpieza,
        "descuento_porcentaje": p.descuento_porcentaje, "descuento_min_noches": p.descuento_min_noches,
        "servicios": list(p.servicios.order_by("nombre").values("id", "nombre")),
        "servicios_adicionales": [{"id": a.id, "nombre": a.nombre, "precio": a.precio}
                                  for a in p.servicios_adicionales.filter(activo=True).order_by("id")],
        "reglas": [{"descripcion": r.descripcion, "orden": r.orden} for r in p.reglas.order_by("orden")],
        "imagenes": [{"ruta": i.ruta, "orden": i.orden} for i in p.imagenes.order_by("orden")],
        "politica": {
            "id": politica.id, "nombre": politica.nombre, "descripcion": politica.descripcion,
            "tramos": [{"dias_minimos": t.dias_minimos, "dias_maximos": t.dias_maximos,
                        "porcentaje_devolucion": t.porcentaje_devolucion} for t in politica.tramos.order_by("-dias_minimos")],
        } if politica else None,
    }


def calcular_porcentaje_devolucion(politica_id: int, dias: int) -> Decimal:
    """PoliticaCancelacion.calcular_porcentaje_devolucion(dias) para Reservas (RF-D-RES-03.1)."""
    politica = PoliticaCancelacion.objects.filter(pk=politica_id).first()
    return politica.calcular_porcentaje_devolucion(dias) if politica else Decimal("0")


def obtener_titulos_y_anfitriones(ids) -> dict[int, dict]:
    """{id: {"titulo", "anfitrion"}} para los listados de reservas y los avisos."""
    return {p["id"]: {"titulo": p["titulo"], "anfitrion": p["anfitrion_id"]}
            for p in Publicacion.objects.filter(pk__in=list(ids)).values("id", "titulo", "anfitrion_id")}


def obtener_nombres_adicionales(ids) -> dict[int, str]:
    return dict(ServicioAdicional.objects.filter(pk__in=list(ids)).values_list("id", "nombre"))


def obtener_nombres_ciudades() -> dict[int, str]:
    return dict(Ciudad.objects.values_list("id", "nombre"))


def _resumir_publicacion(p: Publicacion) -> dict:
    return {
        "id": p.id, "titulo": p.titulo, "anfitrion": p.anfitrion_id, "estado": p.estado,
        "ciudad": p.ciudad_id, "ciudad_nombre": p.ciudad.nombre if p.ciudad else None,
        "tipo": p.tipo_alojamiento_id, "tipo_nombre": p.tipo_alojamiento.nombre if p.tipo_alojamiento else None,
        "politica": p.politica_id, "precio_noche": p.precio_noche, "tarifa_limpieza": p.tarifa_limpieza,
        "descuento_porcentaje": p.descuento_porcentaje, "descuento_min_noches": p.descuento_min_noches,
        "capacidad": p.capacidad, "creada": p.creada,
    }


# ================================================================ reglas de la publicación

def calcular_faltantes(p: Publicacion) -> list[str]:
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


def es_visible_para(usuario, p: Publicacion) -> bool:
    return usuario.rol == "ADMINISTRADOR" or (usuario.rol == "ANFITRION" and p.anfitrion_id == usuario.id)


def obtener_publicacion(usuario, publicacion_id: int) -> Publicacion:
    p = Publicacion.objects.filter(pk=publicacion_id).first()
    if not p:
        raise NoEncontrado("La publicación no existe.")
    if not es_visible_para(usuario, p):
        _negar_acceso(usuario, p, "Ver o modificar una publicación ajena")
        raise SinPermiso("Solo el anfitrión dueño o un administrador pueden modificarla.")
    return p


def _negar_acceso(usuario, p: Publicacion, motivo: str) -> None:
    """Acceso negado (CA-05.2): se registra fuera de transaction.atomic para que quede aunque la petición falle."""
    auditoria.registrar_evento(usuario.id, "AccesoDenegado", entidad="Publicacion", entidad_id=p.id, exitoso=False, detalle={"motivo": motivo})


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


def _aplicar_datos(p: Publicacion, d: dict) -> None:
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

def crear_publicacion(anfitrion, d: dict) -> Publicacion:
    if not (d.get("titulo") or "").strip():
        raise ErrorNegocio("Escribe un título.", campo="titulo")
    _validar_datos(d)
    with transaction.atomic():
        p = Publicacion(anfitrion=anfitrion, estado=E.BORRADOR)
        _aplicar_datos(p, d)
        auditoria.registrar_evento(anfitrion.id, "PublicacionCreada", entidad="Publicacion", entidad_id=p.id)
    return p


def actualizar_publicacion(usuario, publicacion_id: int, d: dict) -> Publicacion:
    p = obtener_publicacion(usuario, publicacion_id)
    if usuario.rol == "ANFITRION" and p.estado not in EDITABLE_POR_ANFITRION:
        raise ErrorNegocio(f"No puedes editar una publicación {E(p.estado).label.lower()}.", codigo=409)
    if "titulo" in d and not (d["titulo"] or "").strip():
        raise ErrorNegocio("Escribe un título.", campo="titulo")
    _validar_datos({**{c: getattr(p, c) for c in ("descuento_porcentaje", "descuento_min_noches")}, **d})
    with transaction.atomic():
        _aplicar_datos(p, d)
        # La publicación conserva su estado (sigue ACTIVA sin volver a revisión). Fuera de BORRADOR debe seguir completa.
        if p.estado != E.BORRADOR and (f := calcular_faltantes(p)):
            raise ErrorNegocio("Falta: " + ", ".join(f) + ".", extra={"faltantes": f})
        auditoria.registrar_evento(usuario.id, "PublicacionEditada", entidad="Publicacion", entidad_id=p.id)
    return p


# ================================================================ cambios de estado

def cambiar_estado(usuario, publicacion_id: int, nuevo: str, observacion: str | None = None) -> Publicacion:
    p = obtener_publicacion(usuario, publicacion_id)
    anterior = p.estado
    if (anterior, nuevo) not in TRANSICIONES.get(usuario.rol, set()):
        _negar_acceso(usuario, p, f"{anterior} → {nuevo}")
        raise ErrorNegocio(f"No se puede pasar de «{E(anterior).label}» a «{E(nuevo).label}».", codigo=409)
    if nuevo == E.PENDIENTE_REVISION and (f := calcular_faltantes(p)):
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
        detalle = {"de": anterior, "a": nuevo, **({"observacion": observacion} if observacion else {})}
        auditoria.registrar_evento(usuario.id, nombre, entidad="Publicacion", entidad_id=p.id, detalle=detalle)
        if nombre in EVENTOS_DE_DOMINIO:  # los reciben Reservas y Notificaciones
            publicar_evento(nombre, usuario_id=usuario.id, entidad="Publicacion", entidad_id=p.id,
                     detalle={**detalle, "titulo": p.titulo, "anfitrion": p.anfitrion_id,
                              "por_administrador": usuario.rol == "ADMINISTRADOR"})
    return p


def eliminar_borrador(anfitrion, publicacion_id: int) -> None:
    """El anfitrión elimina su publicación en BORRADOR (pedido del PO el 2026-11-18; no está en el SRS v3.5).

    Solo BORRADOR: nunca estuvo activa, así que no tiene cotizaciones ni reservas. Sus imágenes, reglas, servicios,
    calendario e historial de revisiones se borran con ella; la auditoría conserva la eliminación."""
    p = obtener_publicacion(anfitrion, publicacion_id)
    no_se_puede = "Solo puedes eliminar una publicación en borrador. Si ya está publicada, puedes pausarla."
    if p.estado != E.BORRADOR:
        raise Conflicto(no_se_puede)
    with transaction.atomic():
        p = Publicacion.objects.select_for_update().get(pk=p.pk)
        if p.estado != E.BORRADOR:  # cambió mientras tanto (por ejemplo, se envió a revisión)
            raise Conflicto(no_se_puede)
        titulo = p.titulo
        try:
            p.delete()
        except ProtectedError as e:  # defensa: una cotización o reserva la protege (on_delete=PROTECT)
            raise Conflicto("Esta publicación tiene cotizaciones o reservas y no se puede eliminar.") from e
        auditoria.registrar_evento(anfitrion.id, "PublicacionEliminada", entidad="Publicacion", entidad_id=publicacion_id,
                            detalle={"titulo": titulo})


def revisar_publicacion(admin, publicacion_id: int, accion: str, observacion: str | None) -> Publicacion:
    destino = {AccionModeracion.APROBAR: E.ACTIVA, AccionModeracion.DEVOLVER: E.BORRADOR}.get(accion)
    if not destino:
        raise ErrorNegocio("La acción debe ser APROBAR o DEVOLVER.", campo="accion")
    p = obtener_publicacion(admin, publicacion_id)
    if p.estado != E.PENDIENTE_REVISION:
        raise Conflicto("Esta publicación ya no está pendiente de revisión.")
    return cambiar_estado(admin, publicacion_id, destino, observacion)


def bloquear_publicacion(admin, publicacion_id: int, motivo: str) -> Publicacion:
    return cambiar_estado(admin, publicacion_id, E.BLOQUEADA, motivo)


def desbloquear_publicacion(admin, publicacion_id: int) -> Publicacion:
    return cambiar_estado(admin, publicacion_id, E.PAUSADA)


def listar_publicaciones_admin(estado: str | None = None):
    qs = Publicacion.objects.exclude(estado=E.BORRADOR).select_related("ciudad", "tipo_alojamiento")
    return qs.filter(estado=estado) if estado else qs


def listar_mis_publicaciones(anfitrion, estado=None):
    qs = Publicacion.objects.filter(anfitrion=anfitrion).select_related("ciudad", "tipo_alojamiento")
    return qs.filter(estado=estado) if estado else qs
