"""Interfaz pública de SRV-08 Auditoría.

Es el único módulo que otros servicios pueden importar de esta app.
Nadie fuera de apps.auditoria debe importar apps.auditoria.models (regla verificada
con import-linter en el pipeline, ADR-001).

Uso desde cualquier servicio:

    from apps.auditoria import services as auditoria

    auditoria.registrar("INICIO_SESION", exitoso=False, actor_id=None,
                        detalle={"correo": "ana@correo.com"}, ip="10.0.0.1")

Transacción: registrar() escribe en la conexión actual. Si se llama dentro de un
transaction.atomic(), el evento queda en esa misma transacción (si la operación
se deshace, el evento también). Si se llama fuera de un bloque atómico, Django
trabaja en autocommit y el evento queda guardado de inmediato aunque la
operación falle después: eso es lo que necesitan los intentos fallidos, que
deben quedar registrados justamente porque fallaron (vista b del C4 nivel 3).
"""

from __future__ import annotations

from typing import Any

from .models import EventoAuditoria


class Accion:
    """Nombres de las acciones registradas (columna evento_auditoria.accion).

    Centralizarlos evita que cada servicio escriba la misma acción con otro
    nombre, lo que rompería los filtros de la consulta del registro (HU-23).
    """

    REGISTRO = "REGISTRO"
    INICIO_SESION = "INICIO_SESION"
    CIERRE_SESION = "CIERRE_SESION"
    SOLICITUD_RECUPERACION = "SOLICITUD_RECUPERACION"
    CAMBIO_CONTRASENA = "CAMBIO_CONTRASENA"
    ACTUALIZACION_PERFIL = "ACTUALIZACION_PERFIL"
    DESACTIVACION = "DESACTIVACION"
    REACTIVACION = "REACTIVACION"
    RESTRICCION = "RESTRICCION"
    LEVANTAR_RESTRICCION = "LEVANTAR_RESTRICCION"
    ACCESO_DENEGADO = "ACCESO_DENEGADO"


def registrar(
    accion: str,
    *,
    exitoso: bool,
    actor_id: int | None = None,
    entidad: str | None = None,
    entidad_id: int | None = None,
    detalle: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    """Agrega un evento al registro de acciones (RF-D-ADM-04.1).

    Nunca se debe pasar una contraseña ni un token en ``detalle``: el registro
    se conserva 10 años (RNF-E-CON-01) y lo lee el administrador.
    """
    EventoAuditoria.objects.create(
        accion=accion,
        exitoso=exitoso,
        actor_id=actor_id,
        entidad=entidad,
        entidad_id=entidad_id,
        detalle=detalle,
        ip=ip,
    )


def ip_de_la_peticion(request) -> str | None:
    """IP del cliente.

    En Render la petición pasa por un proxy que AGREGA la IP real al final de
    X-Forwarded-For. Se toma el último valor y no el primero porque el primero
    lo puede escribir el propio cliente para hacerse pasar por otra IP.
    """
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR")
    if reenviada:
        return reenviada.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR")


def consultar(
    *,
    actor_id: int | None = None,
    accion: str | None = None,
    exitoso: bool | None = None,
    desde=None,
    hasta=None,
) -> list[dict[str, Any]]:
    """Eventos del registro, del más reciente al más antiguo, filtrados por
    usuario, tipo de acción y fechas (base de HU-23, RF-D-ADM-04.1)."""
    eventos = EventoAuditoria.objects.all()
    if actor_id is not None:
        eventos = eventos.filter(actor_id=actor_id)
    if accion is not None:
        eventos = eventos.filter(accion=accion)
    if exitoso is not None:
        eventos = eventos.filter(exitoso=exitoso)
    if desde is not None:
        eventos = eventos.filter(fecha__gte=desde)
    if hasta is not None:
        eventos = eventos.filter(fecha__lte=hasta)
    return list(
        eventos.order_by("-fecha", "-id").values("id", "actor_id", "accion", "entidad", "entidad_id", "exitoso", "detalle", "ip", "fecha")
    )
