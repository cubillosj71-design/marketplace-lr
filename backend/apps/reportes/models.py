"""Modelos de SRV-09 Reportes (MOD-09, C4 nivel 3).

Reportes no tiene tablas propias ni importa otras apps de negocio: solo lee cuatro vistas que publican otros
módulos, con modelos managed = False.
- v_usuario_reporte (Identidad, identidad/migrations/0004)
- v_publicacion_reporte (Catálogo, catalogo/migrations/0005)
- v_reserva_reporte y v_demanda (Reservas, reservas/migrations/0007)
"""

from django.db import models


class UsuarioReporte(models.Model):
    nombre_completo = models.CharField(max_length=120)
    correo = models.CharField(max_length=254)
    telefono = models.CharField(max_length=20)
    ciudad = models.CharField(max_length=80, null=True)
    rol = models.CharField(max_length=15)
    activa = models.BooleanField()
    restringida = models.BooleanField()
    motivo_restriccion = models.TextField(null=True)
    autorizacion_datos = models.DateTimeField()
    fecha_registro = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "v_usuario_reporte"

    @property
    def estado_cuenta(self) -> str:
        """Solo para mostrar: no es una columna (MOD-01)."""
        return "RESTRINGIDA" if self.restringida else ("ACTIVA" if self.activa else "DESACTIVADA")


class PublicacionReporte(models.Model):
    titulo = models.CharField(max_length=120)
    anfitrion_id = models.BigIntegerField()
    anfitrion = models.CharField(max_length=120)
    ciudad = models.CharField(max_length=80, null=True)
    tipo = models.CharField(max_length=40, null=True)
    precio_noche = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    estado = models.CharField(max_length=20)
    creada = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "v_publicacion_reporte"


class ReservaReporte(models.Model):
    publicacion_id = models.BigIntegerField()
    titulo = models.CharField(max_length=120)
    ciudad = models.CharField(max_length=80)
    tipo = models.CharField(max_length=40)
    huesped_id = models.BigIntegerField()
    huesped = models.CharField(max_length=120)
    creada = models.DateTimeField()
    fecha_llegada = models.DateField()
    fecha_salida = models.DateField()
    noches = models.SmallIntegerField()
    estado = models.CharField(max_length=12)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    tarifa_servicio = models.DecimalField(max_digits=12, decimal_places=2)
    valor_devolucion = models.DecimalField(max_digits=12, decimal_places=2)
    monto_bruto = models.DecimalField(max_digits=12, decimal_places=2)
    ingreso_plataforma = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        managed = False
        db_table = "v_reserva_reporte"


class Demanda(models.Model):
    """v_demanda: reservas agrupadas por ciudad, tipo y día de creación (hora de Colombia)."""

    pk = models.CompositePrimaryKey("ciudad", "tipo", "fecha")
    ciudad = models.CharField(max_length=80)
    tipo = models.CharField(max_length=40)
    fecha = models.DateField()
    reservas = models.IntegerField()
    monto_bruto = models.DecimalField(max_digits=14, decimal_places=2)
    ingreso_plataforma = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        managed = False
        db_table = "v_demanda"
