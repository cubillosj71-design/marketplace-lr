"""Autenticación de cada petición con el token de acceso (ADR-005).

SimpleJWT ya valida la firma y el vencimiento del token. Esta clase agrega lo
que pide ADR-005: revisar el estado de la cuenta en CADA petición. Así, si el
Administrador restringe una cuenta, esa persona pierde el acceso de inmediato,
aunque su token de acceso todavía no haya vencido.

Cuesta una consulta por petición (buscar al usuario por su llave primaria), que
SimpleJWT ya hacía de todas formas.
"""

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.settings import api_settings

from .models import EstadoCuenta, Usuario

MENSAJES_POR_ESTADO = {
    EstadoCuenta.RESTRINGIDA: ("Tu cuenta está restringida por la administración de la plataforma.", "cuenta_restringida"),
    EstadoCuenta.DESACTIVADA: ("Tu cuenta está desactivada. Inicia sesión de nuevo para reactivarla.", "cuenta_desactivada"),
}


class JWTConEstadoDeCuenta(JWTAuthentication):
    def get_user(self, validated_token):
        try:
            usuario_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError:
            raise AuthenticationFailed("El token no identifica a ningún usuario.", code="token_invalido") from None

        usuario = Usuario.objects.filter(pk=usuario_id).first()
        if usuario is None:
            raise AuthenticationFailed("El usuario del token no existe.", code="usuario_no_existe")

        if usuario.estado != EstadoCuenta.ACTIVA:
            mensaje, codigo = MENSAJES_POR_ESTADO[usuario.estado]
            raise AuthenticationFailed(mensaje, code=codigo)
        return usuario
