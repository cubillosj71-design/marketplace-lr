"""Modelos de SRV-04 Reservas.

Tablas de este servicio: tarifa_servicio, cotizacion, cotizacion_servicio_adicional, reserva, cancelacion.
Ver las secciones 9 y 10 del documento de diseño.

En este incremento se implementan las tablas que necesitan los módulos de Usuarios, Alojamientos y
Reportes: la tarifa de servicio (RF-D-ADM-03.1), la cotización y la reserva (para el calendario, la
desactivación de cuentas y los reportes). El flujo de cotizar, reservar y cancelar llega con el
módulo de Reservas, junto con la tabla cancelacion.
"""

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeOperators
from django.db import models
from django.db.models import F, Func, Q, Value


class EstadoReserva(models.TextChoices):
    CONFIRMADA = "CONFIRMADA", "Confirmada"
    CANCELADA = "CANCELADA", "Cancelada"
    COMPLETADA = "COMPLETADA", "Completada"
    EN_REVISION = "EN_REVISION", "En revisión"


class TarifaServicio(models.Model):
    """Historial del porcentaje que cobra la plataforma (0 % a 30 %)."""

    administrador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2)
    vigente_desde = models.DateTimeField()

    class Meta:
        db_table = "tarifa_servicio"
        ordering = ["-vigente_desde"]
        constraints = [
            models.CheckConstraint(condition=Q(porcentaje__gte=0, porcentaje__lte=30), name="tarifa_porcentaje_0_30"),
        ]


class Cotizacion(models.Model):
    """Desglose que ve el huésped antes de reservar. Los valores quedan fijos (CA-22.1)."""

    huesped = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    publicacion = models.ForeignKey("catalogo.Publicacion", on_delete=models.PROTECT, related_name="+")
    fecha_llegada = models.DateField()
    fecha_salida = models.DateField()
    num_huespedes = models.SmallIntegerField()
    noches = models.SmallIntegerField()
    precio_noche = models.DecimalField(max_digits=12, decimal_places=2)
    precio_base = models.DecimalField(max_digits=12, decimal_places=2)
    descuento = models.DecimalField(max_digits=12, decimal_places=2)
    tarifa_limpieza = models.DecimalField(max_digits=12, decimal_places=2)
    tarifa_servicio = models.DecimalField(max_digits=12, decimal_places=2)
    total_adicionales = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    creada = models.DateTimeField(auto_now_add=True)
    vence = models.DateTimeField()

    class Meta:
        db_table = "cotizacion"
        constraints = [
            models.CheckConstraint(condition=Q(fecha_salida__gt=F("fecha_llegada")), name="cotizacion_rango_valido"),
            models.CheckConstraint(condition=Q(num_huespedes__gt=0), name="cotizacion_huespedes_mayor_0"),
            models.CheckConstraint(condition=Q(noches__gt=0), name="cotizacion_noches_mayor_0"),
        ]


class CotizacionServicioAdicional(models.Model):
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name="adicionales")
    servicio_adicional = models.ForeignKey("catalogo.ServicioAdicional", on_delete=models.PROTECT, related_name="+")
    precio = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "cotizacion_servicio_adicional"


class Reserva(models.Model):
    cotizacion = models.OneToOneField(Cotizacion, on_delete=models.PROTECT, related_name="reserva")
    huesped = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    publicacion = models.ForeignKey("catalogo.Publicacion", on_delete=models.PROTECT, related_name="+")
    politica = models.ForeignKey("catalogo.PoliticaCancelacion", on_delete=models.PROTECT, related_name="+")
    fecha_llegada = models.DateField()
    fecha_salida = models.DateField()
    num_huespedes = models.SmallIntegerField()
    total = models.DecimalField(max_digits=12, decimal_places=2)
    estado = models.CharField(max_length=12, choices=EstadoReserva.choices, default=EstadoReserva.CONFIRMADA)
    clave_idempotencia = models.UUIDField(unique=True)
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reserva"
        indexes = [models.Index(fields=["publicacion", "fecha_llegada", "fecha_salida"], name="reserva_publicacion_rango")]
        constraints = [
            models.CheckConstraint(condition=Q(fecha_salida__gt=F("fecha_llegada")), name="reserva_rango_valido"),
            models.CheckConstraint(condition=Q(num_huespedes__gt=0), name="reserva_huespedes_mayor_0"),
            models.CheckConstraint(condition=Q(estado__in=EstadoReserva.values), name="reserva_estado_valido"),
            # Sección 10.1: dos reservas CONFIRMADAS o EN_REVISION no comparten noches (RF-D-RES-02.2)
            ExclusionConstraint(
                name="reserva_sin_superposicion",
                expressions=[
                    ("publicacion", RangeOperators.EQUAL),
                    (
                        Func(F("fecha_llegada"), F("fecha_salida"), Value("[)"), function="daterange", output_field=DateRangeField()),
                        RangeOperators.OVERLAPS,
                    ),
                ],
                condition=Q(estado__in=[EstadoReserva.CONFIRMADA, EstadoReserva.EN_REVISION]),
            ),
        ]
