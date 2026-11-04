# ADR-003. React 18 con Vite y TypeScript para el front-end

**Estado:** Aceptada · 3 de noviembre de 2026

## Contexto

El enunciado exige un front-end en un framework que consuma los servicios REST.

## Decisión

Aplicación de una sola página en React 18, construida con Vite y escrita en TypeScript; React Router para la navegación y Axios para llamar a la API.

## Alternativas

Angular (más estructurado, curva de aprendizaje mayor), Vue (más sencillo, pero el equipo lo conoce menos) y plantillas de Django (no cumple el enunciado).

## Consecuencias

A favor: amplia documentación y componentes listos, como Stripe Elements. En contra: dos proyectos (front y back) que se despliegan por separado y requieren configurar CORS.
