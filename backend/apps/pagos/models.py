"""Modelos de SRV-05 Pagos (MOD-05).

Tablas de este servicio: pago. La migración 0002 crea los triggers: no se borra ni se vacía, y solo se
pueden cambiar estado y referencia_externa (RNF-E-CON-01).
Las llaves foráneas a cotizacion y reserva se declaran con texto: Pagos no importa código de Reservas.
"""

from django.db import models
from django.db.models import Q


class TipoPago(models.TextChoices):
    """Tipo de movimiento de dinero: COBRO al reservar o DEVOLUCION al cancelar."""
    COBRO = "COBRO", "Cobro"
    DEVOLUCION = "DEVOLUCION", "Devolución"


class EstadoPago(models.TextChoices):
    """Resultado de la pasarela: APROBADO, RECHAZADO o EN_VERIFICACION (pendiente de confirmar)."""
    APROBADO = "APROBADO", "Aprobado"
    RECHAZADO = "RECHAZADO", "Rechazado"
    EN_VERIFICACION = "EN_VERIFICACION", "En verificación"


class Pago(models.Model):
    """Movimiento de dinero de una reserva (tabla pago, MOD-05).

    Registro de solo inserción: un trigger solo deja cambiar estado y referencia_externa (la
    conciliación) y rechaza DELETE y TRUNCATE (RNF-E-CON-01).

    Attributes:
        cotizacion: cotización cobrada (de ella sale el monto).
        reserva: reserva a la que pertenece (nula solo si el cobro no llegó a crear la reserva).
        tipo: COBRO o DEVOLUCION.
        monto: valor en pesos, mayor que 0.
        estado: resultado de la pasarela.
        referencia_externa: id en la pasarela (pi_..., re_... o SIM-...).
        clave_idempotencia: evita registrar dos veces el mismo movimiento.
        fecha: momento del registro.
    """
    cotizacion = models.ForeignKey("reservas.Cotizacion", on_delete=models.PROTECT, related_name="+")
    reserva = models.ForeignKey("reservas.Reserva", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    tipo = models.CharField(max_length=10, choices=TipoPago.choices)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    estado = models.CharField(max_length=15, choices=EstadoPago.choices)
    referencia_externa = models.CharField(max_length=100, null=True, blank=True)
    clave_idempotencia = models.UUIDField(unique=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pago"
        ordering = ["-fecha", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(tipo__in=TipoPago.values), name="pago_tipo_valido"),
            models.CheckConstraint(condition=Q(monto__gt=0), name="pago_monto_mayor_0"),
            models.CheckConstraint(condition=Q(estado__in=EstadoPago.values), name="pago_estado_valido"),
        ]
