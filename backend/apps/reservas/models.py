"""Modelos de SRV-04 Reservas.

Tablas de este servicio (MOD-04): periodo_calendario, tarifa_servicio, cotizacion,
cotizacion_servicio_adicional, reserva y cancelacion.
Vista de solo lectura que publica: v_noche_no_disponible.
Ver las secciones 9 y 10 del documento de diseño y el diagrama de clases.
"""

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeOperators
from django.db import models
from django.db.models import F, Func, Q, Value

from apps.comun import reloj


class EstadoReserva(models.TextChoices):
    CONFIRMADA = "CONFIRMADA", "Confirmada"
    CANCELADA = "CANCELADA", "Cancelada"
    COMPLETADA = "COMPLETADA", "Completada"
    EN_REVISION = "EN_REVISION", "En revisión"


class PeriodoCalendario(models.Model):
    """Rango [fecha_inicio, fecha_fin) del calendario de una publicación (RF-D-ALO-02.2).
    Se guardan los rangos NO disponibles (disponible = false), unidos y sin traslapes."""

    publicacion = models.ForeignKey("catalogo.Publicacion", on_delete=models.CASCADE, related_name="+")
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    disponible = models.BooleanField()

    class Meta:
        db_table = "periodo_calendario"
        ordering = ["fecha_inicio"]
        constraints = [models.CheckConstraint(condition=Q(fecha_fin__gt=F("fecha_inicio")), name="periodo_rango_valido")]

    def contiene(self, fecha) -> bool:
        return self.fecha_inicio <= fecha < self.fecha_fin


class TarifaServicio(models.Model):
    """Historial del porcentaje que cobra la plataforma (0 % a 30 %)."""

    administrador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
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
    # Tarifa vigente que se usó para calcular tarifa_servicio (CA-22.1: los valores quedan fijos)
    tarifa_servicio_ref = models.ForeignKey(TarifaServicio, on_delete=models.PROTECT, related_name="+", db_column="tarifa_servicio_id")
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
    creada = models.DateTimeField(default=reloj.ahora)  # reloj inyectable: los reportes cuentan por fecha de creación
    vence = models.DateTimeField()

    class Meta:
        db_table = "cotizacion"
        constraints = [
            models.CheckConstraint(condition=Q(fecha_salida__gt=F("fecha_llegada")), name="cotizacion_rango_valido"),
            models.CheckConstraint(condition=Q(num_huespedes__gt=0), name="cotizacion_huespedes_mayor_0"),
            models.CheckConstraint(condition=Q(noches__gt=0), name="cotizacion_noches_mayor_0"),
        ]


class CotizacionServicioAdicional(models.Model):
    """Servicio adicional elegido en la cotización, con el precio que tenía en ese momento.
    Clave primaria compuesta (cotizacion_id, servicio_adicional_id), igual al modelo relacional."""

    pk = models.CompositePrimaryKey("cotizacion_id", "servicio_adicional_id")
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name="adicionales")
    servicio_adicional = models.ForeignKey("catalogo.ServicioAdicional", on_delete=models.PROTECT, related_name="+")
    precio_aplicado = models.DecimalField(max_digits=12, decimal_places=2)

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
    creada = models.DateTimeField(default=reloj.ahora)  # reloj inyectable: los reportes cuentan por fecha de creación
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

    # ---- métodos del diagrama de clases. Solo cambian el estado; el trigger de reserva acepta únicamente las
    # transiciones de la sección 3.6 del SRS. Lo demás (cancelación, devolución, auditoría, eventos) lo
    # orquesta reservas.services en la misma transacción.
    def _pasar_a(self, estado: str) -> None:
        self.estado = estado
        self.save(update_fields=["estado", "actualizada"])

    def confirmar(self) -> None:
        self._pasar_a(EstadoReserva.CONFIRMADA)

    def cancelar(self) -> None:
        self._pasar_a(EstadoReserva.CANCELADA)

    def completar(self) -> None:
        """RF-D-RES-02.3: CONFIRMADA cuya fecha de salida ya pasó."""
        self._pasar_a(EstadoReserva.COMPLETADA)

    def pasar_a_revision(self) -> None:
        self._pasar_a(EstadoReserva.EN_REVISION)

    def resolver(self, mantener: bool) -> None:
        """EN_REVISION -> CONFIRMADA si se mantiene, CANCELADA si no (CA-20.2, CA-20.3)."""
        self.confirmar() if mantener else self.cancelar()

    def cancelar_sin_resolucion(self) -> None:
        """EN_REVISION que llegó a su fecha de llegada sin resolverse (CA-20.5)."""
        self.cancelar()


class Cancelacion(models.Model):
    """Cancelación de una reserva (RF-D-RES-03.1). Registro de solo inserción: la migración 0006 crea los
    triggers que rechazan UPDATE, DELETE y TRUNCATE (RNF-E-CON-01). cancelada_por NULL = automática."""

    reserva = models.OneToOneField(Reserva, on_delete=models.PROTECT, related_name="cancelacion")
    cancelada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    fecha = models.DateTimeField()
    motivo = models.TextField()
    dias_anticipacion = models.IntegerField()
    porcentaje_devolucion = models.DecimalField(max_digits=5, decimal_places=2)
    valor_devolucion = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "cancelacion"
        constraints = [
            models.CheckConstraint(condition=Q(porcentaje_devolucion__gte=0, porcentaje_devolucion__lte=100), name="cancelacion_porcentaje_0_100"),
            models.CheckConstraint(condition=Q(valor_devolucion__gte=0), name="cancelacion_valor_no_negativo"),
        ]


class NocheNoDisponible(models.Model):
    """Vista v_noche_no_disponible (migración 0006): una fila por noche ocupada por una reserva CONFIRMADA o
    EN_REVISION o cerrada en periodo_calendario. Solo lectura; la usan Búsqueda y Reservas."""

    pk = models.CompositePrimaryKey("publicacion_id", "fecha")
    publicacion_id = models.BigIntegerField()
    fecha = models.DateField()

    class Meta:
        managed = False
        db_table = "v_noche_no_disponible"
