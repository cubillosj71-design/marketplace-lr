"""Lectura segura de la entrada de una petición.

Un dato que manda el cliente nunca debe producir un 500: el 500 dice "el servidor falló", y aquí el error está
en lo que llegó. Las vistas que leen el cuerpo sin serializer usan leer_texto(); las demás validan con serializers
de DRF, que ya responden 400.
"""


def leer_texto(request, campo: str) -> str:
    """El campo de texto del cuerpo, o "" si el cuerpo no es un objeto JSON (por ejemplo [] o "texto") o si el
    campo no es texto (número, lista, null). Con "" la regla de negocio responde su propio mensaje (400 o 401)."""
    datos = request.data
    valor = datos.get(campo) if hasattr(datos, "get") and not isinstance(datos, (str, bytes)) else None
    return valor if isinstance(valor, str) else ""
