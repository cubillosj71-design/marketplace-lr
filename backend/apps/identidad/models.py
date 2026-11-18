"""Modelos de SRV-01 Identidad.

Tablas de este servicio: usuario, restriccion_usuario, token_recuperacion.
Ver la sección 10 del documento de diseño (docs/diseno).

Usuario se define desde el Sprint 0 porque Django exige fijar AUTH_USER_MODEL
antes de la primera migración. Hereda de AbstractBaseUser, que aporta los
campos password y last_login. No usa PermissionsMixin para no crear tablas
extra de grupos y permisos: el acceso se decide por el rol.
"""

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone


class RolUsuario(models.TextChoices):
    HUESPED = "HUESPED", "Huésped"
    ANFITRION = "ANFITRION", "Anfitrión"
    ADMINISTRADOR = "ADMINISTRADOR", "Administrador"


class EstadoCuenta(models.TextChoices):
    ACTIVA = "ACTIVA", "Activa"
    DESACTIVADA = "DESACTIVADA", "Desactivada"
    RESTRINGIDA = "RESTRINGIDA", "Restringida"


def normalizar_correo(correo: str) -> str:
    """Correo en minúsculas y sin espacios.

    BaseUserManager.normalize_email solo pasa a minúsculas el dominio. Aquí se
    pasa todo, para que Ana@Correo.com y ana@correo.com sean la misma cuenta y
    la restricción UNIQUE de la columna correo cumpla RF-D-USU-01.1.
    """
    return correo.strip().lower()


class UsuarioManager(BaseUserManager):
    def create_user(self, correo, password=None, **campos):
        if not correo:
            raise ValueError("El correo es obligatorio")
        usuario = self.model(correo=normalizar_correo(correo), **campos)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, correo, password=None, **campos):
        # Única forma de crear un Administrador: la carga el equipo al poner en
        # marcha la plataforma (nota de RF-AN-USU-01), con
        # "python manage.py createsuperuser".
        campos.setdefault("rol", RolUsuario.ADMINISTRADOR)
        campos.setdefault("acepta_datos_en", timezone.now())
        return self.create_user(correo, password, **campos)


class Usuario(AbstractBaseUser):
    correo = models.EmailField(max_length=254, unique=True)
    nombre_completo = models.CharField(max_length=120)
    telefono = models.CharField(max_length=20)
    ciudad = models.CharField(max_length=80, blank=True, null=True)
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


class TokenRecuperacion(models.Model):
    """Enlace de recuperación de contraseña (RF-D-USU-01.3, RNF-P-SEG-03).

    Se guarda el hash SHA-256 del token, nunca el token: si alguien lee la
    tabla, no puede usar los enlaces. Sirve una sola vez (usado_en) y vence a
    los 20 minutos (vence).
    """

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tokens_recuperacion")
    token_hash = models.CharField(max_length=64, unique=True)
    creado = models.DateTimeField()
    vence = models.DateTimeField()
    usado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "token_recuperacion"
        constraints = [
            models.CheckConstraint(condition=models.Q(vence__gt=models.F("creado")), name="token_vence_despues_de_creado"),
        ]

    def es_valido(self, ahora=None) -> bool:
        ahora = ahora or timezone.now()
        return self.usado_en is None and ahora < self.vence


class RestriccionUsuario(models.Model):
    """Historial de restricciones que impone un Administrador (RF-D-ADM-02.1).

    La restricción vigente es la que no tiene fecha_fin. El estado RESTRINGIDA
    de Usuario se mantiene sincronizado con ella para que la revisión que se
    hace en cada petición (ADR-005) no tenga que consultar esta tabla.
    """

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="restricciones")
    administrador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="restricciones_impuestas")
    motivo = models.TextField()
    fecha_inicio = models.DateTimeField(default=timezone.now)
    fecha_fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "restriccion_usuario"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fecha_fin__isnull=True) | models.Q(fecha_fin__gt=models.F("fecha_inicio")),
                name="restriccion_fin_despues_de_inicio",
            ),
            # A lo sumo una restricción abierta por usuario.
            models.UniqueConstraint(
                fields=["usuario"], condition=models.Q(fecha_fin__isnull=True), name="una_restriccion_vigente_por_usuario"
            ),
        ]

    def esta_vigente(self) -> bool:
        return self.fecha_fin is None
