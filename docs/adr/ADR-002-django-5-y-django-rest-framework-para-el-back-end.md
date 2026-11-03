# ADR-002. Django 5 y Django REST Framework para el back-end

**Estado:** Aceptada · 3 de noviembre de 2026

## Contexto

Se necesitan servicios REST, persistencia en PostgreSQL, autenticación, permisos y migraciones, con poco tiempo de construcción.

## Decisión

Python 3.12 con Django 5 y Django REST Framework.

## Alternativas

FastAPI (más liviano, pero sin ORM, migraciones ni administración integrados) y Spring Boot (el equipo tiene menos experiencia en Java).

## Consecuencias

A favor: ORM con transacciones, migraciones versionadas, autenticación y panel de administración para la carga inicial. En contra: el rendimiento por proceso es menor que en otras opciones; se compensa con varios procesos de Gunicorn.
