"""Rutas de operación interna (/api/v1/interno/...). No usan JWT: se protegen con el encabezado
X-Token-Tareas, que se compara con la variable de entorno TOKEN_TAREAS (sin valor en el repositorio)."""

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .eventos import ip_de
from .tareas import ejecutar_tareas_diarias, token_valido


class TareasDiarias(APIView):
    """POST /interno/tareas/diarias. Sin token o con token incorrecto: 403 y el intento queda registrado."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        if not token_valido(request.headers.get("X-Token-Tareas")):
            from apps.auditoria import services as auditoria

            auditoria.registrar(None, "AccesoDenegado", exitoso=False, ip=ip_de(request),
                                detalle={"ruta": request.path, "metodo": request.method, "motivo": "Token de tareas ausente o incorrecto"})
            return Response({"detalle": "No autorizado."}, status=403)
        return Response(ejecutar_tareas_diarias("interno", ip=ip_de(request)))
