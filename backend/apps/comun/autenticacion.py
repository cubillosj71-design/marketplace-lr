"""Autenticación JWT que revisa el estado de la cuenta en cada petición (ADR-005).

SimpleJWT ya rechaza usuarios con is_active = False (cuenta DESACTIVADA o RESTRINGIDA). Además,
antes de esa revisión se sincroniza el estado con las restricciones: si una restricción venció,
la cuenta vuelve a ACTIVA; si empezó una nueva, pasa a RESTRINGIDA.
"""

from rest_framework_simplejwt.authentication import JWTAuthentication


class JWTConEstadoDeCuenta(JWTAuthentication):
    def get_user(self, validated_token):
        from apps.identidad import services as identidad  # import tardío: evita ciclos al cargar apps

        usuario_id = validated_token.get("user_id")
        if usuario_id is not None:
            identidad.sincronizar_estado(int(usuario_id))
        return super().get_user(validated_token)
