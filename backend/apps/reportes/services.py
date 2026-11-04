"""Interfaz pública de SRV-09 Reportes.

Es el único módulo que otros servicios pueden importar de esta app.
Nadie fuera de apps.reportes debe importar apps.reportes.models (regla verificada
con import-linter en el pipeline, ADR-001).
"""
