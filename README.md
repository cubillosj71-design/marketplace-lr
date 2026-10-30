# Marketplace de alojamientos de Inversiones LR

Marketplace web de alojamientos temporales que conecta a anfitriones que publican alojamientos con huéspedes que los buscan, cotizan y reservan. Es el proyecto del curso Ingeniería de Software I (2026-2) de la Universidad El Bosque.

El MVP cubre registro e inicio de sesión por roles (Huésped, Anfitrión y Administrador), publicaciones, disponibilidad, búsqueda con filtros, cotización, reserva inmediata sin reservas superpuestas, pago simulado con Stripe en modo prueba, cancelación con política, notificaciones, reseñas, administración con auditoría, dashboard y reportes en PDF o Excel.

## Equipo 2 · Software GT

| Integrante | Rol |
|---|---|
| Cubillos Guzmán José Santiago | Scrum Master y gerente del proyecto |
| Monroy Sánchez Nicolás | Product Owner |
| Moreno Ariza Sergio Andrés | Arquitecto y responsable de calidad |

Docente: Ing. Wilson Rojas Reales. Revisión y aprobación: grupo de Ingeniería de Software II.

## Stack

| Capa | Tecnología |
|---|---|
| Back-end | Python, Django y Django REST Framework (servicios REST) |
| Base de datos | PostgreSQL |
| Front-end | Aplicación web aparte que consume los servicios REST (el framework se fija en un ADR) |
| Pagos | Stripe en modo prueba |
| Integración continua | GitHub Actions |
| Análisis estático | SonarCloud |

## Estructura inicial

```
marketplace-lr/
├── backend/          # proyecto Django y servicios REST
├── frontend/         # aplicación web
├── docs/
│   ├── adr/          # registros de decisiones de arquitectura
│   ├── api/          # contratos OpenAPI
│   └── diagramas/    # BPMN, UML y C4
├── .github/          # plantilla de Pull Request y workflows
├── CONTRIBUTING.md   # estrategia de ramas, commits y Pull Requests
└── README.md
```

## Cómo ejecutarlo

Las instrucciones para correr el back-end, el front-end y las pruebas se agregan en el Sprint 0, cuando el proyecto Django y el pipeline queden configurados.

## Forma de trabajo

- Toda tarea nace en Jira con la clave `LR` (por ejemplo, `LR-12`).
- Cada historia se desarrolla en su propia rama y llega a `main` por Pull Request revisado por otro integrante.
- `main` está protegida: no acepta pushes directos.

El detalle está en [CONTRIBUTING.md](CONTRIBUTING.md).

## Enlaces

- Jira: _pendiente_
- Confluence: _pendiente_
