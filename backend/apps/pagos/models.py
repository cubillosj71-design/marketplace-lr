"""Modelos de SRV-05 Pagos (MOD-05).

Tablas de este servicio: pago. La migración 0002 crea los triggers: no se borra ni se vacía, y solo se
pueden cambiar estado y referencia_externa (RNF-E-CON-01).
Las llaves foráneas a cotizacion y reserva se declaran con texto: Pagos no importa código de Reservas.
"""

from django.db import models
from django.db.models import Q


class TipoPago(models.TextChoices):
    COBRO = "COBRO", "Cobro"
    DEVOLUCION = "DEVOLUCION", "Devolución"


class EstadoPago(models.TextChoices):
    APROBADO = "APROBADO", "Aprobado"
    RECHAZADO = "RECHAZADO", "Rechazado"
    EN_VERIFICACION = "EN_VERIFICACION", "En verificación"


class Pago(models.Model):
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
