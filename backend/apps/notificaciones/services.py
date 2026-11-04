"""Interfaz pública de SRV-07 Notificaciones.

Es el único módulo que otros servicios pueden importar de esta app.
Nadie fuera de apps.notificaciones debe importar apps.notificaciones.models (regla verificada
con import-linter en el pipeline, ADR-001).
"""
