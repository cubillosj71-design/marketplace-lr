"""Modelos de SRV-01 Identidad.

Tablas de este servicio: usuario, restriccion_usuario, token_recuperacion.
Ver la sección 9 del documento de diseño (docs/diseno).

Usuario se define desde el Sprint 0 porque Django exige fijar AUTH_USER_MODEL
antes de la primera migración. Hereda de AbstractBaseUser, que aporta los
campos password y last_login. No usa PermissionsMixin para no crear tablas
extra de grupos y permisos: el acceso se decide por el rol.
"""

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models import Q
from django.utils import timezone


class RolUsuario(models.TextChoices):
    HUESPED = "HUESPED", "Huésped"
    ANFITRION = "ANFITRION", "Anfitrión"
    ADMINISTRADOR = "ADMINISTRADOR", "Administrador"


class EstadoCuenta(models.TextChoices):
    ACTIVA = "ACTIVA", "Activa"
    DESACTIVADA = "DESACTIVADA", "Desactivada"
    RESTRINGIDA = "RESTRINGIDA", "Restringida"


class UsuarioManager(BaseUserManager):
    def create_user(self, correo, password=None, **campos):
        if not correo:
            raise ValueError("El correo es obligatorio")
        usuario = self.model(correo=self.normalize_email(correo), **campos)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, correo, password=None, **campos):
        campos.setdefault("rol", RolUsuario.ADMINISTRADOR)
        return self.create_user(correo, password, **campos)


class Usuario(AbstractBaseUser):
    correo = models.EmailField(max_length=254, unique=True)
    nombre_completo = models.CharField(max_length=120)
    telefono = models.CharField(max_length=20)
    # Asociación opcional con el catálogo de ciudades (usuario.ciudad_id en el modelo relacional)
    ciudad = models.ForeignKey("catalogo.Ciudad", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    rol = models.CharField(max_length=15, choices=RolUsuario.choices)
    estado = models.CharField(max_length=12, choices=EstadoCuenta.choices, default=EstadoCuenta.ACTIVA)
    acepta_datos_en = models.DateTimeField(help_text="Autorización de tratamiento de datos (Ley 1581)")
    fecha_registro = models.DateTimeField(auto_now_add=True)

    objects = UsuarioManager()

    USERNAME_FIELD = "correo"
    REQUIRED_FIELDS = ["nombre_completo", "telefono", "rol", "acepta_datos_en"]

    class Meta:
        db_table = "usuario"
        constraints = [
            models.CheckConstraint(condition=models.Q(rol__in=RolUsuario.values), name="usuario_rol_valido"),
            models.CheckConstraint(condition=models.Q(estado__in=EstadoCuenta.values), name="usuario_estado_valido"),
        ]

    def __str__(self) -> str:
        return self.correo

    # Acceso al panel de administración de Django (carga inicial, ADR-002).
    @property
    def is_staff(self) -> bool:
        return self.rol == RolUsuario.ADMINISTRADOR

    @property
    def is_active(self) -> bool:  # type: ignore[override]
        return self.estado == EstadoCuenta.ACTIVA

    def has_perm(self, perm, obj=None) -> bool:
        return self.is_staff

    def has_module_perms(self, app_label) -> bool:
        return self.is_staff


class RestriccionUsuario(models.Model):
    """Restricción impuesta por un administrador (RF-D-ADM-02.1). El estado RESTRINGIDA de la cuenta
    se deriva de la restricción vigente y se escribe en la misma transacción (DA-04)."""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="restricciones")
    administrador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    motivo = models.TextField()
    fecha_inicio = models.DateTimeField(default=timezone.now)
    fecha_fin = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "restriccion_usuario"
        ordering = ["-fecha_inicio"]
        constraints = [
            models.CheckConstraint(
                condition=Q(fecha_fin__isnull=True) | Q(fecha_fin__gt=models.F("fecha_inicio")), name="restriccion_rango_valido"
            ),
        ]

    def esta_vigente(self, ahora=None) -> bool:
        ahora = ahora or timezone.now()
        return self.fecha_inicio <= ahora and (self.fecha_fin is None or self.fecha_fin > ahora)


class TokenRecuperacion(models.Model):
    """Enlace de recuperación (RNF-P-SEG-03): se guarda solo el hash SHA-256, vence a los 20 minutos
    y se usa una sola vez."""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    token_hash = models.CharField(max_length=64, unique=True)
    creado = models.DateTimeField(auto_now_add=True)
    vence = models.DateTimeField()
    usado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "token_recuperacion"

    def es_valido(self, ahora=None) -> bool:
        ahora = ahora or timezone.now()
        return self.usado_en is None and ahora < self.vence
