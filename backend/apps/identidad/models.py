"""Modelos de SRV-01 Identidad.

Tablas de este servicio: usuario, restriccion_usuario, token_recuperacion.
Ver la sección 9 del documento de diseño (docs/diseno).

Usuario se define desde el Sprint 0 porque Django exige fijar AUTH_USER_MODEL
antes de la primera migración. Hereda de AbstractBaseUser, que aporta los
campos password y last_login. No usa PermissionsMixin para no crear tablas
extra de grupos y permisos: el acceso se decide por el rol.
"""

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


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
