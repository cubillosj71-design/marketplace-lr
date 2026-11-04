"""Interfaz pública de SRV-03 Búsqueda.

Es el único módulo que otros servicios pueden importar de esta app.
Nadie fuera de apps.busqueda debe importar apps.busqueda.models (regla verificada
con import-linter en el pipeline, ADR-001).
"""
