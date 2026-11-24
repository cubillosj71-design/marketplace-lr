"""Utilidades de base de datos transversales.

Las tablas evento_auditoria, reserva, pago y cancelacion tienen un trigger BEFORE TRUNCATE que impide vaciarlas
(RNF-E-CON-01). Django vacía la base con TRUNCATE en `flush`, que usan `cargar_demo --reiniciar`
(solo desarrollo) y la limpieza de las pruebas con transaction=True. Solo esos dos casos usan
`permitir_vaciado()`, que apaga esos triggers mientras corre y los vuelve a encender al salir.
"""

from contextlib import contextmanager

from django.db import connection

TRIGGERS_SIN_VACIAR = (
    ("evento_auditoria", "evento_auditoria_sin_vaciar"),
    ("reserva", "reserva_sin_vaciar"),
    ("pago", "pago_sin_vaciar"),
    ("cancelacion", "cancelacion_sin_vaciar"),
)


def _cambiar_triggers(accion: str) -> None:
    """Activa o desactiva los triggers que impiden vaciar las tablas de solo inserción.

    Args:
        accion: "ENABLE" o "DISABLE".
    """
    with connection.cursor() as c:
        for tabla, trigger in TRIGGERS_SIN_VACIAR:
            c.execute(f"ALTER TABLE {tabla} {accion} TRIGGER {trigger}")


@contextmanager
def permitir_vaciado():
    """Context manager que permite vaciar la base solo mientras corre el bloque.

    Apaga los triggers que rechazan TRUNCATE en evento_auditoria, reserva, pago y cancelación, y los
    vuelve a encender al salir, aunque haya un error. Lo usa cargar_demo --reiniciar, solo en desarrollo.
    """
    _cambiar_triggers("DISABLE")
    try:
        yield
    finally:
        _cambiar_triggers("ENABLE")
