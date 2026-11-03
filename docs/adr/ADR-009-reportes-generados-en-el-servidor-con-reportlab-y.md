# ADR-009. Reportes generados en el servidor con ReportLab y openpyxl

**Estado:** Aceptada · 3 de noviembre de 2026

## Contexto

RF-D-ADM-05.2 pide reportes en PDF o Excel, y RN-20 que correspondan con la información del sistema.

## Decisión

SRV-09 genera los archivos en el servidor a partir de las mismas consultas que alimentan el tablero, y cada descarga publica el evento ReporteDescargado.

## Alternativas

Generar los archivos en el navegador (las cifras podrían diferir del servidor y no quedaría registro confiable de la descarga).

## Consecuencias

A favor: el tablero y los reportes muestran las mismas cifras y toda descarga queda auditada. En contra: los reportes grandes consumen memoria del servidor; se limita el periodo máximo a 12 meses.
