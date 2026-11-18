# API de los módulos Usuarios, Alojamientos y Reportes

Backend en Django 5.1 + Django REST Framework sobre PostgreSQL 16, según el documento de diseño v1.1
(`docs/diseno`), sección 3.4, y los ADR de `docs/adr`. Todas las rutas van bajo `/api/v1` y responden JSON.

## Cómo correrlo

```
docker compose up -d db                 # PostgreSQL 16 en el puerto 5432
cd backend
python -m venv .venv && source .venv/bin/activate   # en Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
python manage.py migrate                # crea las tablas, los catálogos y la tarifa inicial del 10 %
python manage.py cargar_demo            # cuentas y publicaciones de ejemplo (contraseña: Clave1234)
python manage.py runserver              # http://localhost:8000/api/v1/salud
pytest -q                               # pruebas automáticas
lint-imports                            # fronteras entre servicios (ADR-001)
```

`python manage.py cargar_demo --reiniciar` vacía la base y vuelve a cargar los datos. Solo para desarrollo.

Cuentas de ejemplo: `admin@inversioneslr.com`, `anfitrion@correo.com`, `huesped@correo.com`,
`pedro@correo.com`, `sofia@correo.com` y `restringido@correo.com` (restringida hasta el 31/12/2026).

## Autenticación (ADR-005)

1. `POST /identidad/token` con `{"correo", "password"}` devuelve `access` (30 min) y `usuario` en el cuerpo.
   El `refresh` (24 h) llega en la cookie httpOnly `renovacion` (Path `/api/v1/identidad/`, SameSite=Strict),
   que JavaScript no puede leer (C4 nivel 2). La aplicación web guarda el `access` solo en memoria.
2. Cada petición lleva `Authorization: Bearer <access>`.
3. `POST /identidad/token/renovar` lee la cookie, entrega un `access` nuevo y rota la cookie; la anterior queda en la
   lista negra. Solo renueva si la cuenta sigue ACTIVA. Al cargar la página, el front la llama para recuperar la sesión.
4. `POST /identidad/salir` pone la cookie en la lista negra y la borra. No exige un `access` vigente.
5. El estado de la cuenta se revisa en cada petición: una cuenta desactivada o restringida pierde el acceso de inmediato.
6. Clientes sin navegador (Postman, pruebas) pueden mandar `{"refresh"}` en el cuerpo de `renovar` y `salir`.
7. Límite de intentos por IP: 10/min en inicio de sesión y registro, 5/min al pedir enlaces de recuperación y
   30/min al abrirlos o usarlos. Al superarlo, la API responde 429.

Errores de negocio: `{"detalle": "...", "campo": "..."}` con 400, 401, 403, 404, 409 o 410.

## Rutas

| Servicio | Método y ruta | Quién | Requerimiento |
|---|---|---|---|
| Identidad | `POST /identidad/registro` | Visitante | RF-D-USU-01.1 |
| Identidad | `POST /identidad/token` · `POST /identidad/token/renovar` · `POST /identidad/salir` | Usuario | RF-D-USU-01.2 |
| Identidad | `POST /identidad/recuperacion` · `GET y POST /identidad/recuperacion/{token}` | Visitante | RF-D-USU-01.3 |
| Identidad | `GET y PATCH /identidad/perfil` · `POST /identidad/perfil/desactivar` | Con sesión | RF-D-USU-01.4 |
| Identidad | `POST y DELETE /admin/usuarios/{id}/restriccion` | Administrador | RF-D-ADM-02.1 |
| Catálogo | `POST /catalogo/publicaciones` · `GET /catalogo/mis-publicaciones` | Anfitrión | RF-D-ALO-01.1, 02.1 |
| Catálogo | `GET y PATCH /catalogo/publicaciones/{id}` · `POST .../pausar` · `POST .../reactivar` | Anfitrión dueño, Administrador | RF-D-ALO-02.1, ADM-01.1 |
| Catálogo | `POST /catalogo/publicaciones/{id}/enviar-revision` | Anfitrión | RF-D-ALO-01.2 |
| Catálogo | `GET y POST /catalogo/publicaciones/{id}/calendario` | Anfitrión dueño | RF-D-ALO-02.2 |
| Catálogo | `GET /catalogo/ciudades` · `/tipos-alojamiento` · `/servicios` | Todos | Catálogos |
| Catálogo | `GET /admin/publicaciones?estado=` | Administrador | Apoya RF-D-ADM-01.1 |
| Catálogo | `POST /admin/publicaciones/{id}/revision` (`APROBAR` o `DEVOLVER`) | Administrador | RF-D-ADM-01.1 |
| Catálogo | `POST y DELETE /admin/publicaciones/{id}/bloqueo` | Administrador | RF-D-ADM-01.2 |
| Reservas | `GET y PUT /admin/tarifa-servicio` | Administrador | RF-D-ADM-03.1 |
| Auditoría | `GET /admin/auditoria?usuario&accion&resultado&desde&hasta` | Administrador | RF-D-ADM-04.1 |
| Reportes | `GET /admin/tablero?desde&hasta` | Administrador | RF-D-ADM-05.1 |
| Reportes | `GET /admin/reportes/{tipo}?formato=pdf\|xlsx&desde&hasta` | Administrador | RF-D-ADM-05.2 |

Tipos de reporte: `usuarios` (filtros `rol`, `estado`), `publicaciones` (filtros `estado`, `ciudad`, `tipo`),
`reservas`, `ingresos` y `demanda`. El periodo máximo es de 12 meses (ADR-009); sin fechas se usa el año en curso.

Fuera de la tabla 3.4, el backend agrega tres rutas que el frontend necesita: `GET /catalogo/publicaciones/{id}`,
`GET /admin/publicaciones` y `GET /identidad/recuperacion/{token}` (estado del enlace). El cambio de contraseña
con sesión iniciada va en `PATCH /identidad/perfil` con `password_actual` y `password_nueva`.

## Decisiones de implementación

- **Fronteras entre servicios (ADR-001).** Cada servicio expone `services.py`; nadie importa los modelos de otro.
  `lint-imports` verifica 11 reglas, entre ellas que Catálogo no depende de Reservas e Identidad solo consulta a
  Reservas (sección 3.3). El calendario muestra las noches reservadas porque Reservas le entrega a Catálogo su
  consulta al iniciar (inversión de dependencia).
- **Eventos de dominio (ADR-007).** `apps/comun/eventos.py` publica con `transaction.on_commit`. Auditoría registra
  todos; Reservas escucha `PublicacionBloqueada` y pasa las reservas futuras a EN_REVISION.
- **Auditoría de solo inserción (RNF-E-CON-01).** Un trigger de PostgreSQL rechaza UPDATE y DELETE en `evento_auditoria`.
- **Doble reserva (sección 10.1).** Restricción `EXCLUDE USING gist` en `reserva` con la extensión btree_gist.
- **Publicación en borrador.** El modelo relacional marca como obligatorios los datos de la publicación. Mientras es
  BORRADOR pueden faltar; una restricción CHECK exige que estén completos en cualquier otro estado.
- **Calendario.** `periodo_calendario` guarda rangos `[fecha_inicio, fecha_fin)` de noches NO_DISPONIBLE, unidos
  y sin traslapes. `POST` con `tipo: DISPONIBLE` vuelve a abrir un rango.
- **Recuperación de contraseña.** Se guarda solo el hash SHA-256 del enlace. Como la recuperación es simulada y el
  MVP no envía correos (AMB-08, AMB-12), la respuesta trae `enlace` para mostrarlo en pantalla, también en producción
  (CA-03.1). Con un correo no registrado la respuesta es igual, pero sin `enlace`. Pedir un enlace nuevo anula los
  anteriores sin usar.
- **Reportes (ADR-009).** ReportLab y openpyxl en el servidor, con las mismas funciones del tablero (CA-25.1).
  Cada descarga publica `ReporteDescargado` (CA-25.2).
- **Alcance de Reservas.** En este incremento existen la tarifa de servicio, la cotización y la reserva (para el
  calendario, la desactivación y los reportes). Cotizar, reservar con pago y cancelar llegan con el módulo de Reservas.
- **Imágenes.** Se guardan como rutas o URL (`imagen_publicacion.ruta`). La subida de archivos queda para el despliegue.
