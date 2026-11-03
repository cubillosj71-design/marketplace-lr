# ADR-008. Despliegue en Render con Docker e integración continua en GitHub Actions

**Estado:** Aceptada · 3 de noviembre de 2026

## Contexto

Se necesita un entorno accesible para la demostración, con HTTPS y PostgreSQL, sin costo y desplegable desde el pipeline.

## Decisión

Front en un sitio estático de Render, API en un servicio web con una imagen Docker y PostgreSQL gestionado. GitHub Actions ejecuta las pruebas y SonarCloud en cada PR y Render despliega al integrar en main.

## Alternativas

Railway y Fly.io (similares, con límites gratuitos distintos) y un servidor virtual propio (más administración).

## Consecuencias

A favor: HTTPS y respaldos incluidos, la misma imagen en local y en la nube. En contra: los planes gratuitos tienen límites, como la suspensión por inactividad; el respaldo es Docker Compose local (riesgo R7).
