"""Interfaz pública de SRV-02 Catálogo.

Es el único módulo que otros servicios pueden importar de esta app.
Nadie fuera de apps.catalogo debe importar apps.catalogo.models (regla verificada
con import-linter en el pipeline, ADR-001).
"""
