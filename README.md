# Marketplace de alojamientos de Inversiones LR

Marketplace web de alojamientos temporales que conecta a anfitriones que publican alojamientos con huéspedes que los buscan, cotizan y reservan. Es el proyecto del curso Ingeniería de Software I (2026-2) de la Universidad El Bosque.

El MVP cubre registro e inicio de sesión por roles (Huésped, Anfitrión y Administrador), publicaciones, disponibilidad, búsqueda con filtros, cotización, reserva inmediata sin reservas superpuestas, pago simulado con Stripe en modo prueba, cancelación con política, notificaciones, reseñas, administración con auditoría, tablero y reportes en PDF o Excel.

## Equipo 2 · Software GT

| Integrante | Rol |
|---|---|
| Cubillos Guzmán José Santiago | Scrum Master y gerente del proyecto |
| Monroy Sánchez Nicolás | Product Owner |
| Moreno Ariza Sergio Andrés | Arquitecto y responsable de calidad |

Docente: Ing. Wilson Rojas Reales. Revisión y aprobación: grupo de Ingeniería de Software II.

## Arquitectura

Monolito modular orientado a servicios ([ADR-001](docs/adr/ADR-001-monolito-modular-orientado-a-servicios.md)): un solo proyecto Django con una app por servicio. Cada app es dueña de sus tablas y expone su interfaz pública en `services.py`; ninguna app importa los modelos de otra, y el pipeline lo verifica con import-linter.

| ID | Servicio | App | Tablas |
|---|---|---|---|
| SRV-01 | Identidad | `apps.identidad` | 3 |
| SRV-02 | Catálogo | `apps.catalogo` | 12 |
| SRV-03 | Búsqueda | `apps.busqueda` | solo lectura |
| SRV-04 | Reservas | `apps.reservas` | 5 |
| SRV-05 | Pagos (adaptador de Stripe) | `apps.pagos` | 1 |
| SRV-06 | Reseñas | `apps.resenas` | 1 |
| SRV-07 | Notificaciones | `apps.notificaciones` | 1 |
| SRV-08 | Auditoría | `apps.auditoria` | 1 |
| SRV-09 | Reportes | `apps.reportes` | solo lectura |

El diseño completo (C4, despliegue, clases, modelo relacional de 24 tablas y ADR) está en [docs/diseno](docs/diseno).

## Stack

| Capa | Tecnología |
|---|---|
| Back-end | Python 3.12, Django 5, Django REST Framework, SimpleJWT |
| Base de datos | PostgreSQL 16 |
| Front-end | React 18, Vite y TypeScript |
| Pagos | Stripe en modo prueba |
| Ejecución y hosting | Docker, Gunicorn y Render |
| Integración continua | GitHub Actions y SonarCloud |

## Estructura inicial

```
marketplace-lr/
├── backend/
│   ├── config/            # settings, rutas y WSGI del proyecto Django
│   ├── apps/              # una app por servicio (SRV-01 a SRV-09)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .importlinter      # fronteras entre servicios
├── frontend/              # aplicación web en React + Vite + TypeScript
├── docs/
│   ├── analisis/          # documento de requerimientos (SRS)
│   ├── diseno/            # documento de diseño (SDD)
│   ├── adr/               # registros de decisiones de arquitectura
│   ├── diagramas/         # BPMN, casos de uso, C4, UML, clases y modelo relacional
│   └── api/               # contrato OpenAPI (entrega D3)
├── .github/               # plantilla de Pull Request y pipeline de CI
├── docker-compose.yml     # entorno local con PostgreSQL
├── CONTRIBUTING.md
└── README.md
```

## Cómo ejecutarlo

### Con Docker (lo más rápido)

```
docker compose up --build
```

La API queda en http://localhost:8000 y la ruta de salud en http://localhost:8000/api/v1/salud.

### Back-end sin Docker

Requiere Python 3.12 y un PostgreSQL 16 corriendo (puede ser solo el servicio `db` de docker-compose: `docker compose up db`).

```
cd backend
python -m venv .venv
.venv\Scripts\activate          # en Windows
source .venv/bin/activate       # en macOS o Linux
pip install -r requirements-dev.txt
copy .env.example .env          # o cp en macOS/Linux, y ajusta los valores
python manage.py migrate
python manage.py cargar_demo     # solo la primera vez: agrega la demostración, nunca borra nada
python manage.py runserver
```

#### Qué base usa el backend

El backend usa **solo** la base de `DATABASE_URL` en `backend/.env` (o la variable de entorno del mismo nombre, que
tiene prioridad sobre el archivo). En este equipo hay dos servidores PostgreSQL posibles:

| Servidor | Puerto | Uso |
|---|---|---|
| Docker, contenedor `marketplace-db` (PostgreSQL 16) | **55432** | **El del proyecto.** `DATABASE_URL=postgres://marketplace:…@localhost:55432/marketplace_db` |
| PostgreSQL instalado en Windows | 5432 / 5433 | No lo usa el proyecto. No lo detengas ni lo borres. |

Antes de levantar el backend, comprueba a cuál apunta:

```
docker start marketplace-db
python manage.py mostrar_base
```

`mostrar_base` muestra el servidor, el puerto, el nombre de la base, cuántos usuarios, publicaciones y reservas tiene, y
la fecha del primer evento de auditoría. Si esa fecha es de hace un momento, la base se vació en ese momento. Si
`docker start` falla, el backend no tiene base: no levantes otro PostgreSQL en el puerto 55432, porque el backend se
conectaría a él sin avisar y lo que crees se guardaría en otra base.

**No vacíes la base al arrancar.** El arranque normal es `docker start marketplace-db`, `python manage.py migrate` (no
borra datos) y `python manage.py runserver`. `python manage.py cargar_demo --reiniciar` **borra todo** (también lo que
hayas creado): solo funciona con `DJANGO_DEBUG=1`, muestra antes cuántos usuarios, publicaciones y reservas que no son
de la demostración se van a perder y pide escribir `REINICIAR`. Para pruebas o capturas usa otra base, por ejemplo
`marketplace_capturas`, con `DATABASE_URL` en la terminal.

Pruebas y revisión de fronteras:

```
pytest
lint-imports
```

### Front-end

Requiere Node 20.

```
cd frontend
npm install
npm run dev
```

La aplicación queda en http://localhost:5173 y muestra si la API responde.

## Documentación del código fuente

- **Backend:** cada módulo, clase y función tiene su docstring en español con formato Google (`Args:`, `Returns:`,
  `Raises:` y el requisito del SRS que cumple). En VS Code se ve al pasar el mouse sobre cualquier función.
- **Frontend:** cada componente y función exportada tiene un comentario JSDoc (`/** ... */`).
- **Página web de la documentación** (clases, métodos, parámetros y buscador), generada con pdoc a partir de los
  docstrings:

```
cd backend
pip install -r requirements-dev.txt
python manage.py generar_documentacion
```

Queda en `docs/codigo/index.html` (se abre en el navegador). No se sube al repositorio porque se genera desde el código:
vuelve a correr el comando después de cambiarlo. `config/settings.py` no se incluye para no publicar valores de la
configuración.

## Forma de trabajo

- Toda tarea nace en Jira con la clave `MAL` (por ejemplo, `MAL-13`).
- Cada historia se desarrolla en su propia rama y llega a `main` por Pull Request revisado por otro integrante.
- `main` está protegida: no acepta pushes directos.
- Cada Pull Request corre el pipeline: `manage.py check`, migraciones, import-linter, pruebas y compilación del front.

El detalle está en [CONTRIBUTING.md](CONTRIBUTING.md).

## Enlaces

- Jira: _pendiente_
- Confluence: _pendiente_
