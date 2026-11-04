"""Interfaz pública de SRV-01 Identidad.

Es el único módulo que otros servicios pueden importar de esta app.
Nadie fuera de apps.identidad debe importar apps.identidad.models (regla verificada
con import-linter en el pipeline, ADR-001).
"""
