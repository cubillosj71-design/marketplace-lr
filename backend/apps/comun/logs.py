"""Formato JSON para los logs (RNF-O-OPE-01). No importa nada de Django para cargarse antes que las apps."""

import json
import logging


class FormatoJSON(logging.Formatter):
    def format(self, registro: logging.LogRecord) -> str:
        datos = {
            "fecha": self.formatTime(registro), "nivel": registro.levelname, "mensaje": registro.getMessage(),
            "modulo": registro.name,
        }
        for k in ("vista", "evento"):
            if hasattr(registro, k):
                datos[k] = getattr(registro, k)
        if registro.exc_info:
            datos["excepcion"] = self.formatException(registro.exc_info)
        return json.dumps(datos, ensure_ascii=False)
