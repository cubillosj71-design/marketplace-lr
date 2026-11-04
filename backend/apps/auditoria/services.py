"""Interfaz pública de SRV-08 Auditoría.

Es el único módulo que otros servicios pueden importar de esta app.
Nadie fuera de apps.auditoria debe importar apps.auditoria.models (regla verificada
con import-linter en el pipeline, ADR-001).
"""
