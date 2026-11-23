"""Interfaz pública de SRV-08 Auditoría (MOD-08, C4 nivel 3 vista b).

Es el único módulo que otros servicios pueden importar de esta app. Auditoría no depende de
ningún otro componente: cada módulo llama a `registrar()` dentro de la misma transacción del
cambio que audita. Así, si la transacción se revierte, el evento también; y si el evento no se
puede guardar, el cambio tampoco queda (RNF-E-CON-01).

Los inicios de sesión fallidos, los accesos negados y las fallas no controladas se registran
fuera de cualquier transaction.atomic ("transacción propia"), para que queden aunque la
petición termine en error.

Nadie fuera de apps.auditoria debe importar apps.auditoria.models (import-linter, ADR-001).
"""

from __future__ import annotations

from typing import Any

from .models import EventoAuditoria


def registrar_evento(
    actor_id: int | None,
    accion: str,
    *,
    entidad: str | None = None,
    entidad_id: int | None = None,
    exitoso: bool = True,
    detalle: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    """Inserta un evento en evento_auditoria. Escribe directo, sin señales."""
    EventoAuditoria.objects.create(
        actor_id=actor_id, accion=accion[:50], entidad=entidad[:30] if entidad else None, entidad_id=entidad_id,
        exitoso=exitoso, detalle=detalle or None, ip=ip,
    )


# Tipos de acción del filtro del registro (CA-23.1, CA-23.3). Cada tipo agrupa las acciones que registran los
# módulos. "Acción del administrador" se define por el rol de quien la hizo (actor), no por el nombre de la acción.
# Las de reseñas (publicada u ocultada) llegan con su módulo.
TIPOS_ACCION: dict[str, dict] = {
    "inicio_sesion": {"nombre": "Inicio de sesión", "acciones": ["InicioSesion", "CierreSesion"]},
    "acceso_no_permitido": {"nombre": "Intento de usar una función no permitida", "acciones": ["AccesoDenegado"]},
    "estado_publicacion": {"nombre": "Cambio de estado de una publicación", "acciones": [
        "PublicacionEnviadaARevision", "PublicacionAprobada", "PublicacionDevuelta", "PublicacionBloqueada",
        "PublicacionDesbloqueada", "PublicacionPausada", "PublicacionReactivada", "PublicacionEliminada"]},
    "estado_reserva": {"nombre": "Cambio de estado de una reserva", "acciones": [
        "ReservaConfirmada", "ReservaEnRevision", "ReservaResuelta", "ReservaCompletada"]},
    "reserva_rechazada": {"nombre": "Intento de reserva rechazado", "acciones": ["ReservaRechazada"]},
    "cancelacion": {"nombre": "Cancelación de una reserva", "acciones": ["ReservaCancelada"]},
    "descarga_reporte": {"nombre": "Descarga de reporte", "acciones": ["ReporteDescargado"]},
    "accion_administrador": {"nombre": "Acción del administrador", "rol_actor": "ADMINISTRADOR"},
    "cuenta": {"nombre": "Cuenta de usuario", "acciones": [
        "UsuarioRegistrado", "PerfilActualizado", "CuentaDesactivada", "RecuperacionSolicitada", "ContrasenaRestablecida",
        "CuentaRestringida", "RestriccionLevantada"]},
    "pago": {"nombre": "Pagos y devoluciones", "acciones": ["PagoAprobado", "PagoNoAprobado", "DevolucionRegistrada", "PagoConciliado"]},
    "operacion": {"nombre": "Operación y fallas", "acciones": ["ErrorOperacion", "NotificacionFallida", "TareasDiarias"]},
}


def listar_tipos_accion() -> list[dict]:
    return [{"clave": k, "nombre": v["nombre"]} for k, v in TIPOS_ACCION.items()]


def listar_eventos_de_entidades(acciones, entidad: str, entidad_ids=None) -> list[dict]:
    """Eventos con esas acciones sobre una entidad (por ejemplo ReservaEnRevision y ReservaResuelta de Reserva), con el
    nombre del actor, en una sola consulta y del más antiguo al más reciente. Para pantallas que muestran el historial
    de una acción de negocio sin modelo propio (Reservas en revisión, RF-D-ADM-01.2)."""
    qs = EventoAuditoria.objects.select_related("actor").filter(accion__in=list(acciones), entidad=entidad).order_by("fecha", "id")
    if entidad_ids is not None:
        qs = qs.filter(entidad_id__in=list(entidad_ids))
    return [{"accion": e.accion, "entidad_id": e.entidad_id, "actor_id": e.actor_id,
             "actor_nombre": e.actor.nombre_completo if e.actor else None, "fecha": e.fecha, "detalle": e.detalle or {}}
            for e in qs]


def consultar_eventos(*, actor_id=None, accion=None, tipo=None, desde=None, hasta=None, exitoso=None):
    """Consulta para el administrador (RF-D-ADM-04.1, CA-23.1): filtra por usuario (actor), tipo de acción, acción
    y periodo. Trae el nombre del actor por la llave foránea de la propia tabla (sin importar Identidad)."""
    qs = EventoAuditoria.objects.select_related("actor")
    if actor_id:
        qs = qs.filter(actor_id=actor_id)
    if tipo:
        if tipo not in TIPOS_ACCION:
            raise ValueError(tipo)
        t = TIPOS_ACCION[tipo]
        qs = qs.filter(actor__rol=t["rol_actor"]) if "rol_actor" in t else qs.filter(accion__in=t["acciones"])
    if accion:
        qs = qs.filter(accion=accion)
    if exitoso is not None:
        qs = qs.filter(exitoso=exitoso)
    if desde:
        qs = qs.filter(fecha__date__gte=desde)
    if hasta:
        qs = qs.filter(fecha__date__lte=hasta)
    return qs
