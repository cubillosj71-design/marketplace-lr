"""Autenticación JWT que revisa el estado de la cuenta en cada petición (ADR-005).

SimpleJWT carga el usuario en cada petición y lo rechaza si is_active es False. En Usuario,
is_active = activa y sin restricción vigente, así que una cuenta desactivada o restringida pierde
el acceso en la siguiente petición, y lo recupera sola cuando la restricción vence o se levanta.
No se escribe nada en la cuenta: "restringida" se deriva de RestriccionUsuario.
"""

from rest_framework_simplejwt.authentication import JWTAuthentication


class JWTConEstadoDeCuenta(JWTAuthentication):
    """Se mantiene como punto único de configuración (settings.REST_FRAMEWORK)."""
