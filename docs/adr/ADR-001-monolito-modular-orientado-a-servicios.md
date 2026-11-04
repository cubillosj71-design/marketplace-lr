# ADR-001. Monolito modular orientado a servicios

**Estado:** Aceptada · 3 de noviembre de 2026

## Contexto

El enunciado exige una arquitectura orientada a servicios con responsabilidades delimitadas. El equipo tiene tres personas, dos sprints cortos y hosting gratuito, y RNF-O-DES-01 pide que cambiar una capacidad no obligue a tocar partes no relacionadas.

## Decisión

Un solo proyecto Django desplegado como un contenedor, con nueve apps, una por servicio. Cada app tiene sus modelos, su interfaz pública (services.py) y sus rutas. Ninguna app importa los modelos de otra; la regla se verifica en el pipeline con import-linter.

## Alternativas

Microservicios (nueve despliegues con su propia base): descartado por el costo de infraestructura y porque una reserva con pago necesitaría consistencia distribuida. Monolito sin fronteras: descartado porque no cumple la orientación a servicios ni RNF-O-DES-01.

## Consecuencias

A favor: transacciones locales para reservar y cancelar (RNF-P-FIA-03), un solo pipeline, un solo despliegue y fronteras ya definidas si en el futuro se separa un servicio. En contra: un error de despliegue afecta a todos los servicios.
