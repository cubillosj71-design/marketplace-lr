"""Serializadores de SRV-01 Identidad.

Solo validan la FORMA de los datos (tipos, longitudes, formato). Las reglas de
negocio (correo repetido, autorización de datos, estado de la cuenta) están en
services.py, para que valgan igual sin importar desde dónde se llamen.
"""

from django.core.validators import RegexValidator
from rest_framework import serializers

from .models import Usuario
from .services import ROLES_DE_REGISTRO

validar_telefono = RegexValidator(
    regex=r"^\+?[0-9][0-9 \-]{6,18}$",
    message="Escribe un teléfono válido: solo números, espacios o guiones, entre 7 y 20 caracteres.",
)


class UsuarioSerializer(serializers.ModelSerializer):
    """Lo que la API muestra de una cuenta. Nunca incluye la contraseña."""

    class Meta:
        model = Usuario
        fields = ["id", "nombre_completo", "correo", "telefono", "rol", "estado", "fecha_registro"]
        read_only_fields = fields


class RegistroSerializer(serializers.Serializer):
    nombre_completo = serializers.CharField(max_length=120, min_length=3)
    correo = serializers.EmailField(max_length=254)
    telefono = serializers.CharField(max_length=20, validators=[validar_telefono])
    # trim_whitespace=False: los espacios al inicio o al final son parte de la contraseña.
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    rol = serializers.ChoiceField(choices=[(r.value, r.label) for r in ROLES_DE_REGISTRO])
    acepta_datos = serializers.BooleanField()


class InicioSesionSerializer(serializers.Serializer):
    correo = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)


class SolicitudRecuperacionSerializer(serializers.Serializer):
    correo = serializers.EmailField(max_length=254)


class NuevaContrasenaSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)


class PerfilSerializer(serializers.Serializer):
    """Datos que el usuario puede cambiar de su perfil (RF-D-USU-01.4, v3.6)."""

    nombre_completo = serializers.CharField(max_length=120, min_length=3, required=False)
    telefono = serializers.CharField(max_length=20, validators=[validar_telefono], required=False)


class RestriccionSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=1000)
