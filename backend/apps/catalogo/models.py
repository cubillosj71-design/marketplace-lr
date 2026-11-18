"""Modelos de SRV-02 Catálogo.

Tablas de este servicio: ciudad, tipo_alojamiento, politica_cancelacion, tramo_politica, publicacion,
servicio, publicacion_servicio, servicio_adicional, regla_alojamiento, imagen_publicacion,
periodo_calendario, revision_publicacion. Ver las secciones 9 y 10 del documento de diseño.

Ajuste al modelo relacional: en publicacion, los datos que se piden para enviar a revisión pueden
quedar vacíos solo mientras la publicación es BORRADOR. Una restricción CHECK exige que estén
completos en cualquier otro estado, así la regla de RF-D-ALO-01.2 también se cumple en la base.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q


class EstadoPublicacion(models.TextChoices):
    BORRADOR = "BORRADOR", "Borrador"
    PENDIENTE_REVISION = "PENDIENTE_REVISION", "En revisión"
    ACTIVA = "ACTIVA", "Activa"
    PAUSADA = "PAUSADA", "Pausada"
    BLOQUEADA = "BLOQUEADA", "Bloqueada"


class TipoPeriodo(models.TextChoices):
    DISPONIBLE = "DISPONIBLE", "Disponible"
    NO_DISPONIBLE = "NO_DISPONIBLE", "No disponible"


class AccionModeracion(models.TextChoices):
    APROBAR = "APROBAR", "Aprobar"
    DEVOLVER = "DEVOLVER", "Devolver"
    PAUSAR = "PAUSAR", "Pausar"
    REACTIVAR = "REACTIVAR", "Reactivar"
    BLOQUEAR = "BLOQUEAR", "Bloquear"
    DESBLOQUEAR = "DESBLOQUEAR", "Desbloquear"


class Ciudad(models.Model):
    nombre = models.CharField(max_length=80)
    departamento = models.CharField(max_length=80)

    class Meta:
        db_table = "ciudad"
        ordering = ["nombre"]
        constraints = [models.UniqueConstraint(fields=["nombre", "departamento"], name="ciudad_unica")]

    def __str__(self) -> str:
        return f"{self.nombre} ({self.departamento})"


class TipoAlojamiento(models.Model):
    nombre = models.CharField(max_length=40, unique=True)

    class Meta:
        db_table = "tipo_alojamiento"
        ordering = ["nombre"]

    def __str__(self) -> str:
        return self.nombre


class PoliticaCancelacion(models.Model):
    nombre = models.CharField(max_length=40, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    activa = models.BooleanField(default=True)

    class Meta:
        db_table = "politica_cancelacion"

    def __str__(self) -> str:
        return self.nombre


class TramoPolitica(models.Model):
    politica = models.ForeignKey(PoliticaCancelacion, on_delete=models.CASCADE, related_name="tramos")
    dias_minimos = models.IntegerField()
    dias_maximos = models.IntegerField(blank=True, null=True)
    porcentaje_devolucion = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        db_table = "tramo_politica"
        ordering = ["-dias_minimos"]
        constraints = [
            models.CheckConstraint(
                condition=Q(porcentaje_devolucion__gte=0, porcentaje_devolucion__lte=100), name="tramo_porcentaje_0_100"
            ),
        ]


class Servicio(models.Model):
    nombre = models.CharField(max_length=60, unique=True)

    class Meta:
        db_table = "servicio"
        ordering = ["nombre"]

    def __str__(self) -> str:
        return self.nombre


# Datos que exige el envío a revisión (RF-D-ALO-01.2): solo pueden faltar en BORRADOR
_COMPLETA = (
    Q(ciudad__isnull=False) & Q(tipo_alojamiento__isnull=False) & Q(politica__isnull=False)
    & Q(capacidad__isnull=False) & Q(precio_noche__isnull=False) & Q(tarifa_limpieza__isnull=False)
    & ~Q(descripcion="") & ~Q(ubicacion_textual="")
)


class Publicacion(models.Model):
    anfitrion = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    ciudad = models.ForeignKey(Ciudad, on_delete=models.PROTECT, null=True, blank=True)
    tipo_alojamiento = models.ForeignKey(TipoAlojamiento, on_delete=models.PROTECT, null=True, blank=True)
    politica = models.ForeignKey(PoliticaCancelacion, on_delete=models.PROTECT, null=True, blank=True)
    titulo = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True, default="")
    ubicacion_textual = models.CharField(max_length=200, blank=True, default="")
    capacidad = models.SmallIntegerField(null=True, blank=True)
    precio_noche = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tarifa_limpieza = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    descuento_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    descuento_min_noches = models.SmallIntegerField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=EstadoPublicacion.choices, default=EstadoPublicacion.BORRADOR)
    servicios = models.ManyToManyField(Servicio, through="PublicacionServicio", blank=True)
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "publicacion"
        ordering = ["-actualizada"]
        indexes = [models.Index(fields=["ciudad", "estado"], name="publicacion_ciudad_estado")]
        constraints = [
            models.CheckConstraint(condition=Q(estado__in=EstadoPublicacion.values), name="publicacion_estado_valido"),
            models.CheckConstraint(condition=Q(capacidad__isnull=True) | Q(capacidad__gt=0), name="publicacion_capacidad_mayor_0"),
            models.CheckConstraint(condition=Q(precio_noche__isnull=True) | Q(precio_noche__gt=0), name="publicacion_precio_mayor_0"),
            models.CheckConstraint(condition=Q(tarifa_limpieza__isnull=True) | Q(tarifa_limpieza__gte=0), name="publicacion_limpieza_no_negativa"),
            models.CheckConstraint(
                condition=Q(descuento_porcentaje__isnull=True) | Q(descuento_porcentaje__gt=0, descuento_porcentaje__lte=100),
                name="publicacion_descuento_0_100",
            ),
            models.CheckConstraint(
                condition=Q(descuento_min_noches__isnull=True) | Q(descuento_min_noches__gt=0), name="publicacion_descuento_noches_mayor_0"
            ),
            models.CheckConstraint(
                condition=Q(descuento_porcentaje__isnull=True, descuento_min_noches__isnull=True)
                | Q(descuento_porcentaje__isnull=False, descuento_min_noches__isnull=False),
                name="publicacion_descuento_completo",
            ),
            models.CheckConstraint(condition=Q(estado=EstadoPublicacion.BORRADOR) | _COMPLETA, name="publicacion_completa_fuera_de_borrador"),
        ]

    def __str__(self) -> str:
        return self.titulo


class PublicacionServicio(models.Model):
    publicacion = models.ForeignKey(Publicacion, on_delete=models.CASCADE)
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT)

    class Meta:
        db_table = "publicacion_servicio"
        constraints = [models.UniqueConstraint(fields=["publicacion", "servicio"], name="publicacion_servicio_pk")]


class ServicioAdicional(models.Model):
    publicacion = models.ForeignKey(Publicacion, on_delete=models.CASCADE, related_name="servicios_adicionales")
    nombre = models.CharField(max_length=60)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "servicio_adicional"
        constraints = [models.CheckConstraint(condition=Q(precio__gte=0), name="adicional_precio_no_negativo")]


class ReglaAlojamiento(models.Model):
    publicacion = models.ForeignKey(Publicacion, on_delete=models.CASCADE, related_name="reglas")
    descripcion = models.CharField(max_length=200)
    orden = models.SmallIntegerField()

    class Meta:
        db_table = "regla_alojamiento"
        ordering = ["orden"]


class ImagenPublicacion(models.Model):
    publicacion = models.ForeignKey(Publicacion, on_delete=models.CASCADE, related_name="imagenes")
    ruta = models.CharField(max_length=500)
    orden = models.SmallIntegerField()

    class Meta:
        db_table = "imagen_publicacion"
        ordering = ["orden"]


class PeriodoCalendario(models.Model):
    """Rango [fecha_inicio, fecha_fin) que el anfitrión abre o cierra (RF-D-ALO-02.2)."""

    publicacion = models.ForeignKey(Publicacion, on_delete=models.CASCADE, related_name="periodos")
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    tipo = models.CharField(max_length=15, choices=TipoPeriodo.choices)

    class Meta:
        db_table = "periodo_calendario"
        ordering = ["fecha_inicio"]
        constraints = [
            models.CheckConstraint(condition=Q(fecha_fin__gt=models.F("fecha_inicio")), name="periodo_rango_valido"),
            models.CheckConstraint(condition=Q(tipo__in=TipoPeriodo.values), name="periodo_tipo_valido"),
        ]

    def contiene(self, fecha) -> bool:
        return self.fecha_inicio <= fecha < self.fecha_fin


class RevisionPublicacion(models.Model):
    publicacion = models.ForeignKey(Publicacion, on_delete=models.CASCADE, related_name="revisiones")
    administrador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    accion = models.CharField(max_length=15, choices=AccionModeracion.choices)
    observacion = models.TextField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "revision_publicacion"
        ordering = ["-fecha", "-id"]
        constraints = [models.CheckConstraint(condition=Q(accion__in=AccionModeracion.values), name="revision_accion_valida")]
