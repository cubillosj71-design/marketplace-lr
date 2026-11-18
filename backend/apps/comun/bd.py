"""Utilidades de base de datos transversales.

Las tablas evento_auditoria, reserva y pago tienen un trigger BEFORE TRUNCATE que impide vaciarlas
(RNF-E-CON-01). Django vacía la base con TRUNCATE en `flush`, que usan `cargar_demo --reiniciar`
(solo desarrollo) y la limpieza de las pruebas con transaction=True. Solo esos dos casos usan
`vaciado_permitido()`, que apaga esos triggers mientras corre y los vuelve a encender al salir.
"""

from contextlib import contextmanager

from django.db import connection

TRIGGERS_SIN_VACIAR = (
    ("evento_auditoria", "evento_auditoria_sin_vaciar"),
    ("reserva", "reserva_sin_vaciar"),
    ("pago", "pago_sin_vaciar"),
)


def _cambiar(accion: str) -> None:
    with connection.cursor() as c:
        for tabla, trigger in TRIGGERS_SIN_VACIAR:
            c.execute(f"ALTER TABLE {tabla} {accion} TRIGGER {trigger}")


@contextmanager
def vaciado_permitido():
    _cambiar("DISABLE")
    try:
        yield
    finally:
        _cambiar("ENABLE")
