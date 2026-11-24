"""Modelos de SRV-02 Catálogo.

Tablas de este servicio: ciudad, tipo_alojamiento, politica_cancelacion, tramo_politica, publicacion,
servicio, publicacion_servicio, servicio_adicional, regla_alojamiento, imagen_publicacion,
revision_publicacion. Ver las secciones 9 y 10 del documento de diseño. periodo_calendario es de
MOD-04 Reservas.
Vista de solo lectura que publica: v_publicacion_buscable (migración 0004).

Ajuste al modelo relacional: en publicacion, los datos que se piden para enviar a revisión pueden
quedar vacíos solo mientras la publicación es BORRADOR. Una restricción CHECK exige que estén
completos en cualquier otro estado, así la regla de RF-D-ALO-01.2 también se cumple en la base.
"""

from decimal import Decimal

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q


class EstadoPublicacion(models.TextChoices):
    """Estados de una publicación (sección 3.6 del SRS).

    BORRADOR → PENDIENTE_REVISION (el anfitrión la envía) → ACTIVA (el Administrador la aprueba) o
    vuelve a BORRADOR (la devuelve). ACTIVA ↔ PAUSADA. BLOQUEADA la pone el Administrador por
    información engañosa; al desbloquearla queda PAUSADA. Solo las ACTIVAS aparecen en las búsquedas.
    """
    BORRADOR = "BORRADOR", "Borrador"
    PENDIENTE_REVISION = "PENDIENTE_REVISION", "En revisión"
    ACTIVA = "ACTIVA", "Activa"
    PAUSADA = "PAUSADA", "Pausada"
    BLOQUEADA = "BLOQUEADA", "Bloqueada"


class AccionModeracion(models.TextChoices):
    """Acciones del Administrador sobre una publicación, que quedan en su historial de revisiones (RevisionPublicacion)."""
    APROBAR = "APROBAR", "Aprobar"
    DEVOLVER = "DEVOLVER", "Devolver"
    PAUSAR = "PAUSAR", "Pausar"
    REACTIVAR = "REACTIVAR", "Reactivar"
    BLOQUEAR = "BLOQUEAR", "Bloquear"
    DESBLOQUEAR = "DESBLOQUEAR", "Desbloquear"


class Ciudad(models.Model):
    """Ciudad donde puede estar un alojamiento (catálogo fijo, en orden alfabético). Nombre único por departamento."""
    nombre = models.CharField(max_length=80)
    departamento = models.CharField(max_length=80)

    class Meta:
        db_table = "ciudad"
        ordering = ["nombre"]
        constraints = [models.UniqueConstraint(fields=["nombre", "departamento"], name="ciudad_unica")]

    def __str__(self) -> str:
        return f"{self.nombre} ({self.departamento})"


class TipoAlojamiento(models.Model):
    """Tipo de alojamiento del catálogo fijo: apartamento, casa, cabaña, habitación..."""
    nombre = models.CharField(max_length=40, unique=True)

    class Meta:
        db_table = "tipo_alojamiento"
        ordering = ["nombre"]

    def __str__(self) -> str:
        return self.nombre


class PoliticaCancelacion(models.Model):
    """Política de cancelación que elige el anfitrión para su publicación (RF-D-RES-03.1).

    Sus tramos dicen qué porcentaje se devuelve según los días de anticipación con que se cancela.
    """
    nombre = models.CharField(max_length=40, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    activa = models.BooleanField(default=True)

    class Meta:
        db_table = "politica_cancelacion"

    def __str__(self) -> str:
        return self.nombre

    def calcular_porcentaje_devolucion(self, dias: int) -> Decimal:
        """Porcentaje que se devuelve al cancelar con esos días de anticipación: el del tramo que los contiene
        (Moderada: 7 o más 100 %, de 2 a 6 50 %, menos de 2 0 %). Sin tramo, 0 %."""
        for t in self.tramos.order_by("-dias_minimos"):
            if dias >= t.dias_minimos and (t.dias_maximos is None or dias <= t.dias_maximos):
                return t.porcentaje_devolucion
        return Decimal("0")


class TramoPolitica(models.Model):
    """Tramo de una política: de cuántos días de anticipación a cuántos, y qué porcentaje se devuelve.

    Ejemplo de la Moderada: 7 o más días, 100 %; de 2 a 6, 50 %; menos de 2, 0 %. Sin días máximos,
    el tramo no tiene tope.
    """
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
    """Servicio incluido (amenity) del catálogo fijo: wifi, cocina, parqueadero... Sin costo adicional."""
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
    """Alojamiento que ofrece un anfitrión (tabla publicacion, MOD-02, RF-D-ALO-01).

    Los datos obligatorios pueden faltar solo mientras está en BORRADOR: una restricción CHECK exige
    que estén completos en cualquier otro estado (RF-D-ALO-01.2).

    Attributes:
        anfitrion: dueño de la publicación.
        ciudad, tipo_alojamiento, politica: datos del catálogo fijo.
        titulo, descripcion, ubicacion_textual: textos que ve el huésped.
        capacidad: número máximo de huéspedes (mayor que 0).
        precio_noche, tarifa_limpieza: valores en pesos (precio mayor que 0).
        descuento_porcentaje, descuento_min_noches: descuento opcional por estancia larga (los dos o ninguno).
        estado: ver EstadoPublicacion.
        servicios: servicios incluidos.
        creada, actualizada: fechas de creación y de último cambio.
    """
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
    """Tabla intermedia entre publicación y servicio incluido (una vez cada servicio por publicación)."""
    publicacion = models.ForeignKey(Publicacion, on_delete=models.CASCADE)
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT)

    class Meta:
        db_table = "publicacion_servicio"
        constraints = [models.UniqueConstraint(fields=["publicacion", "servicio"], name="publicacion_servicio_pk")]


class ServicioAdicional(models.Model):
    """Servicio con costo que el huésped puede agregar a su reserva (desayuno, traslado...).

    Se cobra una vez por estancia; si se desactiva deja de ofrecerse, pero las cotizaciones guardan su precio.
    """
    publicacion = models.ForeignKey(Publicacion, on_delete=models.CASCADE, related_name="servicios_adicionales")
    nombre = models.CharField(max_length=60)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "servicio_adicional"
        constraints = [models.CheckConstraint(condition=Q(precio__gte=0), name="adicional_precio_no_negativo")]


class ReglaAlojamiento(models.Model):
    """Regla del alojamiento que el huésped debe aceptar (por ejemplo, no fumar), en el orden en que se muestra."""
    publicacion = models.ForeignKey(Publicacion, on_delete=models.CASCADE, related_name="reglas")
    descripcion = models.CharField(max_length=200)
    orden = models.SmallIntegerField()

    class Meta:
        db_table = "regla_alojamiento"
        ordering = ["orden"]


class ImagenPublicacion(models.Model):
    """Foto de una publicación: dirección (URL o ruta en /alojamientos/) y orden. La primera es la portada."""
    publicacion = models.ForeignKey(Publicacion, on_delete=models.CASCADE, related_name="imagenes")
    ruta = models.CharField(max_length=500)
    orden = models.SmallIntegerField()

    class Meta:
        db_table = "imagen_publicacion"
        ordering = ["orden"]


class RevisionPublicacion(models.Model):
    """Acción del Administrador sobre una publicación (aprobar, devolver, pausar, bloquear...).

    Forma el historial de revisiones que ve el anfitrión, con la observación o el motivo.
    """
    publicacion = models.ForeignKey(Publicacion, on_delete=models.CASCADE, related_name="revisiones")
    administrador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    accion = models.CharField(max_length=15, choices=AccionModeracion.choices)
    observacion = models.TextField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "revision_publicacion"
        ordering = ["-fecha", "-id"]
        constraints = [models.CheckConstraint(condition=Q(accion__in=AccionModeracion.values), name="revision_accion_valida")]


class PublicacionBuscable(models.Model):
    """Vista v_publicacion_buscable: publicaciones ACTIVAS cuyo anfitrión tiene la cuenta activa y ninguna
    restricción vigente (CA-04.3, CA-21.2). Solo lectura."""

    titulo = models.CharField(max_length=120)
    ciudad_id = models.BigIntegerField()
    ciudad = models.CharField(max_length=80)
    tipo_alojamiento_id = models.BigIntegerField()
    tipo = models.CharField(max_length=40)
    capacidad = models.SmallIntegerField()
    precio_noche = models.DecimalField(max_digits=12, decimal_places=2)
    tarifa_limpieza = models.DecimalField(max_digits=12, decimal_places=2)
    descuento_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    descuento_min_noches = models.SmallIntegerField(null=True)
    politica_id = models.BigIntegerField()
    servicios = ArrayField(models.BigIntegerField())
    imagen_principal = models.CharField(max_length=500, null=True)

    class Meta:
        managed = False
        db_table = "v_publicacion_buscable"
