"""Interfaz pública de SRV-05 Pagos.

Es el único módulo que otros servicios pueden importar de esta app.
Nadie fuera de apps.pagos debe importar apps.pagos.models (regla verificada
con import-linter en el pipeline, ADR-001).
"""
