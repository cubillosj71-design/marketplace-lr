"""Interfaz pública de SRV-06 Reseñas.

Es el único módulo que otros servicios pueden importar de esta app.
Nadie fuera de apps.resenas debe importar apps.resenas.models (regla verificada
con import-linter en el pipeline, ADR-001).
"""
