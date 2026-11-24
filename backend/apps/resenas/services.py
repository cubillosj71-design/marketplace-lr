"""Interfaz pública de SRV-06 Reseñas.

Es el único módulo que otros servicios pueden importar de esta app.
Nadie fuera de apps.resenas debe importar apps.resenas.models (regla verificada
con import-linter en el pipeline, ADR-001).
"""

from .models import CalificacionPublicacion


def consultar_calificaciones():
    """Vista v_calificacion_publicacion (solo lectura) para Búsqueda (CA-11.1)."""
    return CalificacionPublicacion.objects.all()


def consultar_calificacion(publicacion_id: int) -> dict:
    """Promedio y total de reseñas visibles de una publicación (vista v_calificacion_publicacion).

    Args:
        publicacion_id: id de la publicación.

    Returns:
        {"promedio": Decimal | None, "total": int}; sin reseñas, promedio None y total 0.
    """
    c = CalificacionPublicacion.objects.filter(pk=publicacion_id).first()
    return {"promedio": c.promedio if c else None, "total": c.total if c else 0}
