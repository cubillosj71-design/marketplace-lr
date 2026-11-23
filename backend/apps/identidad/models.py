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

from apps.comun.errores import ErrorNegocio

TELEFONO_MIN, TELEFONO_MAX = 7, 15  # un fijo de 7 dígitos hasta un número internacional (E.164)


def validar_telefono(valor) -> str:
    """El teléfono solo lleva números; se aceptan espacios para separarlos (300 123 4567). Devuelve el valor sin
    espacios sobrantes o lanza ErrorNegocio con campo "telefono"."""
    valor = " ".join(str(valor or "").split())
    digitos = valor.replace(" ", "")
    if not digitos:
        raise ErrorNegocio("Escribe tu teléfono.", campo="telefono")
    if not digitos.isdigit() or not digitos.isascii():
        raise ErrorNegocio("El teléfono solo puede tener números.", campo="telefono")
    if not TELEFONO_MIN <= len(digitos) <= TELEFONO_MAX:
        raise ErrorNegocio(f"El teléfono debe tener entre {TELEFONO_MIN} y {TELEFONO_MAX} números.", campo="telefono")
    return valor


class RolUsuario(models.TextChoices):
    HUESPED = "HUESPED", "Huésped"
    ANFITRION = "ANFITRION", "Anfitrión"
    ADMINISTRADOR = "ADMINISTRADOR", "Administrador"


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
    ciudad = models.CharField(max_length=80, null=True, blank=True)  # texto opcional (MOD-01)
    rol = models.CharField(max_length=15, choices=RolUsuario.choices)
    # Falsa solo cuando el usuario desactivó su cuenta. "Restringida" NO es una columna:
    # se deriva de una RestriccionUsuario vigente (esta_vigente).
    activa = models.BooleanField(default=True)
    autorizacion_datos = models.DateTimeField(help_text="Autorización de tratamiento de datos (Ley 1581)")
    fecha_registro = models.DateTimeField(auto_now_add=True)

    objects = UsuarioManager()

    USERNAME_FIELD = "correo"
    REQUIRED_FIELDS = ["nombre_completo", "telefono", "rol", "autorizacion_datos"]

    class Meta:
        db_table = "usuario"
        constraints = [
            # CHECK rol IN ('HUESPED','ANFITRION','ADMINISTRADOR')
            models.CheckConstraint(condition=models.Q(rol__in=RolUsuario.values), name="usuario_rol_valido"),
        ]

    def __str__(self) -> str:
        return self.correo

    # Acceso al panel de administración de Django (carga inicial, ADR-002).
    @property
    def is_staff(self) -> bool:
        return self.rol == RolUsuario.ADMINISTRADOR

    @property
    def esta_restringida(self) -> bool:
        """Derivada: hay una RestriccionUsuario vigente."""
        return any(r.esta_vigente() for r in RestriccionUsuario.objects.filter(usuario_id=self.pk))

    @property
    def is_active(self) -> bool:  # type: ignore[override]
        """SimpleJWT la revisa en cada petición: una cuenta desactivada o restringida pierde el
        acceso en la siguiente petición (ADR-005)."""
        return self.activa and not self.esta_restringida

    # ---- operaciones del diagrama de clases (MOD-01). Cambian el estado de la cuenta; los permisos, los
    # mensajes, la auditoría y los tokens los orquesta identidad.services en la misma transacción.
    @classmethod
    def registrar(cls, correo: str, clave: str, rol: str, **datos) -> "Usuario":
        """registrar(correo, clave, rol) del diagrama: crea la cuenta con la contraseña cifrada y la fecha de la
        autorización de tratamiento de datos (Ley 1581). Las validaciones previas las hace identidad.services."""
        return cls.objects.create_user(correo=correo, password=clave, rol=rol, autorizacion_datos=timezone.now(), **datos)

    def iniciar_sesion(self, correo: str, clave: str) -> bool:
        """iniciarSesion(correo, clave) del diagrama: True si el correo y la contraseña son de esta cuenta."""
        return (correo or "").strip().lower() == self.correo.lower() and self.check_password(clave or "")

    _SIN_CAMBIO = object()

    def actualizar_perfil(self, nombre=_SIN_CAMBIO, telefono=_SIN_CAMBIO) -> list[str]:
        """actualizarPerfil(nombre, telefono) del diagrama: cambia los datos que llegan (ninguno puede quedar vacío,
        CA-04.1) y devuelve los campos cambiados para guardarlos. El correo y el rol no se cambian aquí."""
        cambiados = []
        if nombre is not self._SIN_CAMBIO:
            nombre = (nombre or "").strip()
            if not nombre:
                raise ErrorNegocio("Este dato no puede quedar vacío.", campo="nombre_completo")
            self.nombre_completo = nombre
            cambiados.append("nombre_completo")
        if telefono is not self._SIN_CAMBIO:
            self.telefono = validar_telefono(telefono)
            cambiados.append("telefono")
        return cambiados

    def desactivar_cuenta(self) -> None:
        """desactivar() del diagrama: la cuenta queda inactiva (CA-04.2). Las reglas previas (no ser administrador,
        no tener reservas pendientes) las revisa identidad.services.desactivar_cuenta."""
        self.activa = False
        self.save(update_fields=["activa"])

    def reactivar_cuenta(self) -> None:
        """reactivar() del diagrama: la cuenta desactivada vuelve a estar activa al ingresar de nuevo (CA-04.4)."""
        self.activa = True
        self.save(update_fields=["activa"])

    def has_perm(self, perm, obj=None) -> bool:
        return self.is_staff

    def has_module_perms(self, app_label) -> bool:
        return self.is_staff


class RestriccionUsuario(models.Model):
    """Restricción impuesta por un administrador (RF-D-ADM-02.1). La cuenta está restringida mientras
    haya una vigente (esta_vigente). Restringir no modifica la cuenta ni sus reservas."""

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
        constraints = [models.CheckConstraint(condition=Q(vence__gt=models.F("creado")), name="token_vence_despues_de_creado")]

    def es_valido(self, ahora=None) -> bool:
        ahora = ahora or timezone.now()
        return self.usado_en is None and ahora < self.vence
