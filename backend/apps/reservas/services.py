"""Interfaz pública de SRV-04 Reservas.

Es el único módulo que otros servicios pueden importar de esta app.
Nadie fuera de apps.reservas debe importar apps.reservas.models (regla verificada
con import-linter en el pipeline, ADR-001).
"""
