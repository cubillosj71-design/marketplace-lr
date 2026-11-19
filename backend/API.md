# API de los módulos Usuarios, Alojamientos, Búsqueda, Reservas, Pagos y Reportes

Backend en Django 5.2 LTS + Django REST Framework sobre PostgreSQL 16, según el documento de diseño v1.1
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
   lista negra. Solo renueva si la cuenta está activa y sin restricción vigente. Al cargar la página, el front la llama
   para recuperar la sesión.
4. `POST /identidad/salir` pone la cookie en la lista negra y la borra. No exige un `access` vigente.
5. La cuenta se revisa en cada petición: `is_active` = `activa` y sin restricción vigente, así que una cuenta
   desactivada o restringida pierde el acceso en la siguiente petición y lo recupera sola al levantarse o vencer la
   restricción (ADR-005).
6. Clientes sin navegador (Postman, pruebas) pueden mandar `{"refresh"}` en el cuerpo de `renovar` y `salir`.
7. Límite de intentos por IP: 10/min en inicio de sesión y registro, 5/min al pedir enlaces de recuperación y
   30/min al abrirlos o usarlos. Al superarlo, la API responde 429.

Errores de negocio: `{"detalle": "...", "campo": "..."}` con 400, 401, 403, 404, 409 o 410.

## Usuario (MOD-01)

Tabla `usuario`: `id`, `correo` VARCHAR(254) único, `nombre_completo` VARCHAR(120), `telefono` VARCHAR(20),
`ciudad` VARCHAR(80) NULL, `password`, `last_login` NULL, `rol` VARCHAR(15) con
`CHECK rol IN ('HUESPED','ANFITRION','ADMINISTRADOR')`, `activa` BOOLEAN, `autorizacion_datos` TIMESTAMPTZ y
`fecha_registro` TIMESTAMPTZ.

Registro, sesión (`usuario`) y perfil devuelven:

```json
{"id": 2, "correo": "huesped@correo.com", "nombre_completo": "Carlos Ruiz", "telefono": "315 222 4410",
 "ciudad": "Medellín", "rol": "HUESPED", "activa": true, "restringida": false,
 "autorizacion_datos": "2026-05-02T15:00:00+00:00", "fecha_registro": "2026-05-02T15:00:00+00:00"}
```

- `activa` es `false` solo cuando el usuario desactivó su cuenta; se vuelve `true` al iniciar sesión (CA-04.4).
- `restringida` **no es una columna**: se deriva de una `restriccion_usuario` vigente (`esta_vigente`). Restringir no
  modifica la cuenta ni sus reservas (RF-D-ADM-02.1); levantar la restricción pone `fecha_fin = ahora`.
- `ciudad` es texto opcional. En `POST /identidad/registro` y `PATCH /identidad/perfil` se envía como texto
  (`"ciudad": "Cartagena"`); `null` o `""` la quitan.
- No se puede desactivar la cuenta con reservas CONFIRMADAS o EN_REVISION cuya fecha de salida no haya pasado, como
  huésped o en sus alojamientos (RF-D-USU-01.4, CA-04.2, CA-04.5). La respuesta 409 trae `reservas` con su `estado`.
- `token_recuperacion` tiene `CHECK vence > creado`.

## Rutas

| Servicio | Método y ruta | Quién | Requerimiento |
|---|---|---|---|
| Identidad | `POST /identidad/registro` | Visitante | RF-D-USU-01.1 |
| Identidad | `POST /identidad/token` · `POST /identidad/token/renovar` · `POST /identidad/salir` | Usuario | RF-D-USU-01.2 |
| Identidad | `POST /identidad/recuperacion` · `GET y POST /identidad/recuperacion/{token}` | Visitante | RF-D-USU-01.3 |
| Identidad | `GET y PATCH /identidad/perfil` | Huésped, Anfitrión, Administrador | RF-D-USU-01.4 |
| Identidad | `POST /identidad/perfil/desactivar` | Huésped, Anfitrión | RF-D-USU-01.4 |
| Identidad | `GET /identidad/permisos` | Todos (sin sesión, los del Visitante) | RF-D-USU-02.1 |
| Identidad | `GET /identidad/roles` (la matriz completa) | Todos (pública) | RF-D-USU-02.1 |
| Identidad | `POST y DELETE /admin/usuarios/{id}/restriccion` | Administrador | RF-D-ADM-02.1 |
| Catálogo | `POST /catalogo/publicaciones` · `GET /catalogo/mis-publicaciones` | Anfitrión | RF-D-ALO-01.1, 02.1 |
| Catálogo | `GET y PATCH /catalogo/publicaciones/{id}` · `POST .../pausar` · `POST .../reactivar` | Anfitrión dueño, Administrador | RF-D-ALO-02.1, ADM-01.1 |
| Catálogo | `POST /catalogo/publicaciones/{id}/enviar-revision` | Anfitrión | RF-D-ALO-01.2 |
| Reservas | `GET y POST /catalogo/publicaciones/{id}/calendario` (la ruta se conserva; la atiende Reservas) | Anfitrión dueño | RF-D-ALO-02.2 |
| Catálogo | `GET /catalogo/ciudades` · `/tipos-alojamiento` · `/servicios` · `/politicas` (con sus tramos) | Todos | RF-D-RES-01.1, ALO-01.1, ADM-05.2 |
| Catálogo | `GET /admin/publicaciones?estado=` | Administrador | Apoya RF-D-ADM-01.1 |
| Catálogo | `POST /admin/publicaciones/{id}/revision` (`APROBAR` o `DEVOLVER`) | Administrador | RF-D-ADM-01.1 |
| Catálogo | `POST y DELETE /admin/publicaciones/{id}/bloqueo` | Administrador | RF-D-ADM-01.2 |
| Búsqueda | `GET /busqueda/publicaciones?ciudad&llegada&salida&huespedes&tipo&precio_min&precio_max&servicios` | Visitante, Huésped | RF-D-RES-01.1 |
| Búsqueda | `GET /busqueda/publicaciones/{id}?desde&hasta` | Visitante, Huésped | RF-D-RES-01.2 |
| Reservas | `POST /reservas/cotizaciones` · `GET /reservas/cotizaciones/{id}` | Huésped | RF-D-RES-02.1 |
| Reservas | `POST /reservas` | Huésped | RF-D-RES-02.2 |
| Reservas | `GET /reservas/mias` | Huésped | RF-D-RES-02.3, HU-14 |
| Reservas | `GET /reservas/de-mis-alojamientos` | Anfitrión | HU-26 |
| Reservas | `GET /reservas/{id}` | Huésped dueño, anfitrión de la publicación, Administrador | HU-14, HU-26 |
| Reservas | `GET /reservas/{id}/cancelar` (simula la devolución) · `POST /reservas/{id}/cancelar` | Huésped dueño | RF-D-RES-03.1 |
| Reservas | `GET /admin/reservas?estado=EN_REVISION` · `POST /admin/reservas/{id}/resolver` | Administrador | RF-D-ADM-01.2 |
| Reservas | `GET y PUT /admin/tarifa-servicio` | Administrador | RF-D-ADM-03.1 |
| Notificaciones | `GET /notificaciones` · `POST /notificaciones/{id}/leida` · `POST /notificaciones/leidas` | Huésped, Anfitrión, Administrador | RF-D-RES-04.1 |
| Interno | `POST /interno/tareas/diarias` (encabezado `X-Token-Tareas`) | Tarea programada | RF-D-RES-02.3, CA-20.5 |
| Identidad | `GET /admin/usuarios?rol&q` | Administrador | RF-D-ADM-02.1, HU-21 |
| Auditoría | `GET /admin/auditoria?usuario&tipo&accion&desde&hasta` (opcional `exitoso`) | Administrador | RF-D-ADM-04.1, CA-23.1, CA-23.3 |
| Reportes | `GET /admin/tablero?desde&hasta` | Administrador | RF-D-ADM-05.1 |
| Reportes | `GET /admin/reportes/{tipo}?formato=pdf\|xlsx&desde&hasta` | Administrador | RF-D-ADM-05.2 |

Tipos de reporte: `usuarios` (filtros `rol` y `estado` = ACTIVA, DESACTIVADA o RESTRINGIDA, derivado de `activa` y de
la restricción vigente), `publicaciones` (filtros `estado`, y `ciudad` y `tipo` por nombre), `reservas`, `ingresos` y
`demanda`. El periodo máximo es de 12 meses (ADR-009) y, si `desde > hasta`, responde 400. Sin fechas se usa el año
en curso. Ver la sección "Tablero y reportes".

Fuera de la tabla 3.4, el backend agrega rutas que el frontend necesita: `GET /catalogo/publicaciones/{id}`,
`GET /admin/publicaciones`, `GET /identidad/recuperacion/{token}` (estado del enlace), `GET /catalogo/politicas` y
`GET /identidad/roles`. `GET /catalogo/mis-publicaciones` y `GET /admin/publicaciones` traen `imagen` (portada) y
`ultima_revision`; el detalle trae `administrador_nombre` en cada revisión. El cambio de contraseña
con sesión iniciada va en `PATCH /identidad/perfil` con `password_actual` y `password_nueva`.

## Permisos por rol (RF-D-USU-02.1)

Cada cuenta tiene un único rol (`usuario.rol`) y quien no inició sesión es **Visitante**. La matriz vive en
`apps/comun/rbac.py` (`PERMISOS`: rol -> permisos `modulo.accion`), sin tablas: el esquema de la base no cambia. Cada
vista declara `permission_classes = [RequierePermiso("modulo.accion")]` (`apps/comun/permisos.py`); con varios
permisos basta tener uno.

- **Sin sesión** en una ruta cuyo permiso no tiene el Visitante: **401** (CA-05.1).
- **Con sesión sin el permiso: 403**, y queda en la auditoría `AccesoDenegado` con `exitoso=false` y `detalle` =
  `ruta`, `metodo`, `permiso` que faltó y `rol` (CA-05.2).
- El permiso dice **qué** puede hacer el rol. **Sobre qué** recurso (la regla de dueño, CA-05.3) lo revisa el service:
  un anfitrión con `publicaciones.gestionar_propias` recibe 403 sobre una publicación ajena.
- `GET /identidad/permisos` devuelve `{"rol", "permisos"}` de quien llama; sin sesión, los del Visitante.
- `GET /identidad/roles` devuelve la matriz completa `{"roles": [{"rol", "permisos"}]}` (Visitante, Huésped,
  Anfitrión, Administrador). La pantalla "Roles y permisos" se arma con ella.
- Rutas sin `RequierePermiso` (lista blanca, verificada por `apps/comun/tests/test_rbac.py`): `salud`, `token`,
  `token/renovar`, `salir`, `recuperacion`, `recuperacion/{token}`, `permisos`, `roles` y `interno/tareas/diarias` (su propio
  token). El sitio `/admin/` de Django queda fuera de la API.

| Permiso | Roles | Rutas | RF |
|---|---|---|---|
| `busqueda.ver` | Visitante, Huésped | `GET /busqueda/publicaciones` · `GET /busqueda/publicaciones/{id}` | RF-D-RES-01.1, 01.2 |
| `cuenta.registrar` | Visitante | `POST /identidad/registro` | RF-D-USU-01.1 |
| `catalogo.ver` | Visitante, Huésped, Anfitrión, Administrador | `GET /catalogo/ciudades` · `/tipos-alojamiento` · `/servicios` · `/politicas` | RF-D-RES-01.1, ALO-01.1, ADM-05.2 |
| `reservas.cotizar` | Huésped | `POST /reservas/cotizaciones` · `GET /reservas/cotizaciones/{id}` | RF-D-RES-02.1 |
| `reservas.crear` | Huésped | `POST /reservas` | RF-D-RES-02.2 |
| `reservas.ver_propias` | Huésped | `GET /reservas/mias` · `GET /reservas/{id}` | RF-D-RES-02.3, HU-14 |
| `reservas.cancelar_propia` | Huésped | `GET y POST /reservas/{id}/cancelar` | RF-D-RES-03.1 |
| `perfil.gestionar` | Huésped, Anfitrión, Administrador | `GET y PATCH /identidad/perfil` | RF-D-USU-01.4 |
| `cuenta.desactivar` | Huésped, Anfitrión | `POST /identidad/perfil/desactivar` | RF-D-USU-01.4 |
| `notificaciones.ver` | Huésped, Anfitrión, Administrador | `GET /notificaciones` · `POST /notificaciones/{id}/leida` · `POST /notificaciones/leidas` | RF-D-RES-04.1 |
| `publicaciones.gestionar_propias` | Anfitrión | `POST /catalogo/publicaciones` · `GET /catalogo/mis-publicaciones` · `GET y PATCH /catalogo/publicaciones/{id}` · `POST .../pausar` · `POST .../reactivar` · `POST .../enviar-revision` | RF-D-ALO-01.1, 01.2, 02.1 |
| `calendario.gestionar` | Anfitrión | `GET y POST /catalogo/publicaciones/{id}/calendario` | RF-D-ALO-02.2 |
| `reservas.ver_de_mis_alojamientos` | Anfitrión | `GET /reservas/de-mis-alojamientos` · `GET /reservas/{id}` | RF-D-RES-02.3, HU-26 |
| `publicaciones.moderar` | Administrador | `GET /admin/publicaciones` · `POST /admin/publicaciones/{id}/revision` · `POST y DELETE /admin/publicaciones/{id}/bloqueo` · `GET y PATCH /catalogo/publicaciones/{id}` · `POST .../pausar` · `POST .../reactivar` | RF-D-ADM-01.1, 01.2, ALO-02.1 |
| `reservas.resolver` | Administrador | `GET /admin/reservas` · `POST /admin/reservas/{id}/resolver` · `GET /reservas/{id}` | RF-D-ADM-01.2 |
| `usuarios.ver` | Administrador | `GET /admin/usuarios` | RF-D-ADM-02.1, HU-21 |
| `usuarios.restringir` | Administrador | `POST y DELETE /admin/usuarios/{id}/restriccion` | RF-D-ADM-02.1 |
| `tarifa.configurar` | Administrador | `GET y PUT /admin/tarifa-servicio` | RF-D-ADM-03.1 |
| `auditoria.consultar` | Administrador | `GET /admin/auditoria` | RF-D-ADM-04.1 |
| `tablero.ver` | Administrador | `GET /admin/tablero` | RF-D-ADM-05.1 |
| `reportes.descargar` | Administrador | `GET /admin/reportes/{tipo}` | RF-D-ADM-05.2 |

Las rutas que aparecen con dos o tres permisos aceptan cualquiera de ellos: `GET /reservas/{id}` (huésped dueño,
anfitrión de la publicación o administrador) y las de una publicación (anfitrión dueño o administrador).

## Decisiones de implementación

- **Fronteras entre servicios (ADR-001).** Cada servicio expone `services.py`; nadie importa los modelos de otro.
  `lint-imports` verifica 16 reglas, entre ellas que Catálogo no depende de Reservas, Identidad solo consulta a
  Reservas (sección 3.3), Auditoría no importa ninguna otra app salvo `apps.comun` (C4 nivel 3, vista b), Búsqueda
  solo lee vistas y `services` (MOD-03), Pagos no depende de Reservas, Notificaciones no importa ninguna otra app de
  negocio (MOD-07: todo le llega en los eventos) y Reportes solo lee vistas (MOD-09: ninguna otra app de negocio).
- **Eventos de dominio (ADR-007, C4 nivel 3).** `apps/comun/eventos.publicar()` se usa solo para los eventos de
  dominio del diagrama: `PublicacionAprobada`, `PublicacionDevuelta`, `PublicacionBloqueada`,
  `PublicacionDesbloqueada`, `PublicacionPausada`, `PublicacionReactivada`, `ReservaConfirmada`, `ReservaCancelada`,
  `ReservaEnRevision` y `ReservaResuelta`. Publicar otro nombre lanza error. Cada evento sale por dos señales:
  - `evento_dominio_en_transaccion`: síncrona, en la **misma transacción**. Reservas escucha `PublicacionBloqueada`
    y pasa las reservas futuras CONFIRMADAS a EN_REVISION (CA-20.1). Si falla, el bloqueo también se revierte.
  - `evento_dominio`: **después de confirmar** (`on_commit` y `send_robust`). Notificaciones crea los avisos.
- **Cómo se audita (MOD-08, C4 nivel 3 vista b).** Auditoría no escucha eventos. Cada módulo llama a
  `auditoria.services.registrar(actor_id, accion, *, entidad=None, entidad_id=None, exitoso=True, detalle=None, ip=None)`
  dentro de la misma transacción del cambio: si el cambio se revierte, el evento también. Los inicios de sesión
  fallidos, los accesos negados y las fallas no controladas (RNF-O-OPE-01) se registran con `exitoso=False` fuera de
  cualquier `transaction.atomic`, así quedan aunque la petición falle.
- **Tabla `evento_auditoria`.** `id`, `actor_id` BIGINT NULL (FK a `usuario`), `accion` VARCHAR(50), `entidad`
  VARCHAR(30) NULL, `entidad_id` BIGINT NULL, `exitoso` BOOLEAN, `detalle` JSONB NULL, `ip` INET NULL y `fecha`.
  La API la devuelve con esos mismos nombres.
- **Auditoría de solo inserción (RNF-E-CON-01, CA-23.2).** Un trigger por fila rechaza UPDATE y DELETE, y otro a
  nivel de sentencia (`BEFORE TRUNCATE ... FOR EACH STATEMENT`) rechaza TRUNCATE.
- **Tablas protegidas y `flush`.** `evento_auditoria`, `reserva`, `pago` y `cancelacion` rechazan TRUNCATE. Django
  vacía la base con TRUNCATE en `flush`, así que `apps/comun/bd.vaciado_permitido()` apaga esos triggers solo mientras corre:
  lo usan `cargar_demo --reiniciar` (exige `DJANGO_DEBUG=1`) y la limpieza de las pruebas con `transaction=True`
  (`conftest.py`). Ningún flujo de la aplicación los apaga.
- **Doble reserva (sección 10.1).** Restricción `EXCLUDE USING gist` en `reserva` con la extensión btree_gist.
- **Publicación en borrador.** El modelo relacional marca como obligatorios los datos de la publicación. Mientras es
  BORRADOR pueden faltar; una restricción CHECK exige que estén completos en cualquier otro estado.
- **Calendario (MOD-04).** `periodo_calendario` es de Reservas: `id`, `publicacion_id`, `fecha_inicio`, `fecha_fin`,
  `disponible` BOOLEAN y `CHECK fecha_fin > fecha_inicio`. Guarda rangos `[fecha_inicio, fecha_fin)` con
  `disponible = false`, unidos y sin traslapes. `POST` con `tipo: DISPONIBLE` vuelve a abrir un rango. No se cierran
  noches con reserva CONFIRMADA o EN_REVISION (CA-09.2). La respuesta conserva `tipo` y agrega `disponible`.
- **Límite de 12 meses (RF-D-ALO-02.2).** Calendario, búsqueda, cotización y reserva rechazan con 400 una fecha de
  salida posterior a hoy + 12 meses (`apps/comun/fechas.py`). Búsqueda, cotización y reserva tampoco aceptan llegadas
  en el pasado.
- **Recuperación de contraseña.** Se guarda solo el hash SHA-256 del enlace. Como la recuperación es simulada y el
  MVP no envía correos (AMB-08, AMB-12), la respuesta trae `enlace` para mostrarlo en pantalla, también en producción
  (CA-03.1). Con un correo no registrado la respuesta es igual, pero sin `enlace`. Pedir un enlace nuevo anula los
  anteriores sin usar.
- **Reportes (ADR-009).** ReportLab y openpyxl en el servidor, con las mismas consultas del tablero (CA-25.1). El
  frontend ya no genera PDF ni Excel: descarga el archivo del servidor.
- **Reloj inyectable.** Las reglas que dependen del día (cancelación, COMPLETADA, EN_REVISION vencidas, límite de
  12 meses) leen la fecha en `apps/comun/reloj.py` (hora de Colombia). Las pruebas la fijan con `reloj.fijar()`.
- **Imágenes.** Se guardan como rutas o URL (`imagen_publicacion.ruta`). La subida de archivos queda para el despliegue.
  Las de `cargar_demo` son rutas locales (`/alojamientos/<nombre>.jpg`) a fotos con licencia libre que sirve el
  frontend desde `frontend/public/alojamientos/` (créditos en `CREDITOS.md` de esa carpeta).


## Vistas de solo lectura

Se crean con `RunSQL` (`CREATE OR REPLACE VIEW`) en la migración del módulo que las publica y se leen con modelos
`managed = False`. Búsqueda combina las suyas a través de los `services` de quien las publica. Reportes tiene sus
propios modelos `managed = False` de las cuatro vistas de reportes y no importa ninguna otra app de negocio.

| Vista | La publica | Columnas | Regla |
|---|---|---|---|
| `v_publicacion_buscable` | Catálogo | id, titulo, ciudad_id, ciudad, tipo_alojamiento_id, tipo, capacidad, precio_noche, tarifa_limpieza, descuento_porcentaje, descuento_min_noches, politica_id, servicios (arreglo de ids), imagen_principal | Publicaciones ACTIVAS cuyo anfitrión tiene `activa = true` y ninguna restricción vigente (CA-04.3, CA-21.2). La vigencia se compara con `statement_timestamp()`. |
| `v_noche_no_disponible` | Reservas | publicacion_id, fecha | Una fila por noche de reserva CONFIRMADA o EN_REVISION y por noche de `periodo_calendario` con `disponible = false` (`generate_series`). La noche de salida queda libre (CA-09.3). |
| `v_calificacion_publicacion` | Reseñas | publicacion_id, promedio, total | **Provisional:** devuelve `promedio NULL` y `total 0` hasta que llegue el módulo de Reseñas. |
| `v_usuario_reporte` | Identidad | id, nombre_completo, correo, telefono, ciudad, rol, activa, restringida, motivo_restriccion, autorizacion_datos, fecha_registro | `restringida` y `motivo_restriccion` salen de la restricción vigente. |
| `v_publicacion_reporte` | Catálogo | id, titulo, anfitrion_id, anfitrion, ciudad, tipo, precio_noche, estado, creada | Sin BORRADOR. |
| `v_reserva_reporte` | Reservas | id, publicacion_id, titulo, ciudad, tipo, huesped_id, huesped, creada, fecha_llegada, fecha_salida, noches, estado, total, tarifa_servicio, valor_devolucion, monto_bruto, ingreso_plataforma | `valor_devolucion` es 0 si no hay cancelación. `monto_bruto` e `ingreso_plataforma` siguen la nota de RF-D-ADM-05 (ver abajo). |
| `v_demanda` | Reservas | ciudad, tipo, fecha, reservas, monto_bruto, ingreso_plataforma | `v_reserva_reporte` agrupada por ciudad, tipo y **día** de creación (hora de Colombia). Una vista no recibe parámetros: Reportes filtra los días del periodo y suma. |

## Búsqueda (MOD-03)

Pública (Visitante y Huésped), sin tablas propias y sin auditoría.

- `GET /busqueda/publicaciones` devuelve las publicaciones buscables con `capacidad >= huespedes` (por defecto 1) y
  sin noches no disponibles en `[llegada, salida)`. `ciudad`, `tipo` y `servicios` son ids (`servicios=1,3` exige
  todos). `precio_min` y `precio_max` filtran el precio por noche. Todos los filtros se combinan (CA-10.4). Si
  `salida <= llegada` responde 400 y no busca (CA-10.3). Cada resultado trae `imagen_principal` y `calificacion`.
- `GET /busqueda/publicaciones/{id}?desde&hasta` devuelve todos los datos del alojamiento, `politica` con sus tramos
  (CA-11.3), `disponibilidad.noches_no_disponibles` del rango (por defecto hoy + 90 días, CA-11.2), `calificacion`,
  servicios incluidos, servicios adicionales con precio, reglas en orden e imágenes. Si la publicación no está en
  `v_publicacion_buscable` responde 404.

## Cotización y reserva (MOD-04)

**`POST /reservas/cotizaciones`** (solo Huésped; un Visitante recibe 401, CA-05.1)

```json
{"publicacion": 7, "fecha_llegada": "2027-01-10", "fecha_salida": "2027-01-13", "num_huespedes": 2, "adicionales": [4]}
```

Valida que la publicación sea buscable (404), la capacidad (400 con `capacidad_maxima`, CA-12.3), que las noches
estén libres (409 con `fechas`) y el límite de 12 meses. Calcula: `precio_base = noches x precio_noche`;
`descuento = %` sobre el precio base si `noches >= descuento_min_noches`; `tarifa_servicio = %` vigente sobre
`(precio_base - descuento)`; `total = base - descuento + limpieza + servicio + adicionales` (cada adicional una vez por
estancia). Guarda `tarifa_servicio_id` (la tarifa usada) y cada adicional con su `precio_aplicado`. Vence a los 30
minutos. Los montos van como texto (`"740000.00"`).

**`POST /reservas`** (solo Huésped)

```json
{"cotizacion": 12, "clave_idempotencia": "2f6c2f2e-6a43-4c8e-9a0b-1d5e3b7a9c10", "medio_pago": "pm_... o simulado"}
```

1. Si ya hay una reserva con esa clave devuelve la misma con **200**, sin cobrar otra vez (CA-13.4, RNF-P-FIA-02).
2. Dentro de `transaction.atomic` bloquea la publicación (`SELECT ... FOR UPDATE`) y recalcula. Si el total cambió
   responde **409** con `cotizacion` (la nueva) y no reserva.
3. Si alguna noche ya no está libre responde **409** "Las fechas ya no están disponibles." (CA-13.2).
4. Inserta la reserva CONFIRMADA (copia `politica_id` y los valores de la cotización), cobra con `ServicioPagos` e
   inserta el pago ya con `reserva_id`. La reserva va antes del pago porque el trigger de `pago` no permite cambiar
   `reserva_id` después. Si el pago no queda APROBADO, la transacción se revierte, no queda reserva ni pago
   (RNF-P-FIA-03) y la respuesta es **402** con `motivo`. El intento se registra como `ReservaRechazada` fuera de la
   transacción (CA-13.3).
5. Registra `ReservaConfirmada` en la auditoría y publica el evento de dominio `ReservaConfirmada`. Responde **201**.

La restricción `EXCLUDE` de `reserva` es la última defensa: si salta, también responde 409.

**Trigger de `reserva`:** sin DELETE ni TRUNCATE. UPDATE solo de `estado` (y `actualizada`), y solo con las
transiciones de la sección 3.6 del SRS: CONFIRMADA→CANCELADA, CONFIRMADA→COMPLETADA, CONFIRMADA→EN_REVISION,
EN_REVISION→CONFIRMADA y EN_REVISION→CANCELADA.

**Tablas:** `cotizacion.tarifa_servicio_id` NOT NULL. `cotizacion_servicio_adicional` tiene
`PRIMARY KEY (cotizacion_id, servicio_adicional_id)` y `precio_aplicado` (por eso Django 5.2, que trae
`CompositePrimaryKey`). `tarifa_servicio.administrador_id` es NOT NULL: si al migrar no hay administrador, la tarifa
inicial del 10 % la crea `cargar_demo`.

## Consultar, cancelar y revisar reservas (MOD-04)

**Consultas.** `GET /reservas/mias` (Huésped, solo las suyas, CA-14.3), `GET /reservas/de-mis-alojamientos`
(Anfitrión, solo sus publicaciones e incluidas las CANCELADAS, CA-26.1, CA-26.2) y `GET /reservas/{id}` (huésped
dueño, anfitrión de la publicación o Administrador; los demás reciben 403 y queda registrado). Cada reserva trae
`estado`, `alojamiento`, fechas, `noches`, `num_huespedes`, `total`, `cancelable` y, si está cancelada,
`cancelacion` con `fecha`, `motivo`, `porcentaje_devolucion` y `valor_devolucion`.

**COMPLETADA (RF-D-RES-02.3).** `reservas.services.completar_vencidas()` pasa a COMPLETADA las CONFIRMADAS cuya
fecha de salida ya pasó (`Reserva.completar()`). La corre la tarea diaria y también cada consulta, así la respuesta
nunca muestra CONFIRMADA una reserva vencida (CA-14.2).

**Cancelar (RF-D-RES-03.1).** `POST /reservas/{id}/cancelar` con `{"motivo": "..."}`, solo el huésped dueño.
`GET` con la misma ruta devuelve cuánto se devolvería hoy, para mostrarlo antes de confirmar.
- Solo CONFIRMADA y antes del día de llegada: desde ese día responde 409 y la reserva sigue CONFIRMADA (CA-15.5).
- `dias_anticipacion` = días calendario entre hoy (hora de Colombia) y la llegada. El porcentaje sale de
  `PoliticaCancelacion.porcentaje_devolucion(dias)` de la **política guardada en la reserva** (`politica_id`).
  Moderada: 7 o más días 100 %, de 2 a 6 días 50 %, menos de 2 días 0 % (CA-15.1 a CA-15.4).
- En una sola transacción: reserva CANCELADA, fila en `cancelacion`, pago `DEVOLUCION` simulado (si el valor es
  mayor que 0), auditoría `ReservaCancelada` (quién, cuándo, motivo y valor, CA-15.3) y evento `ReservaCancelada`.
  Las noches quedan libres.

Tabla `cancelacion`: `id`, `reserva_id` único, `cancelada_por_id` NULL (NULL = automática), `fecha`, `motivo`,
`dias_anticipacion`, `porcentaje_devolucion` (0 a 100) y `valor_devolucion`. Es de solo inserción: un trigger rechaza
UPDATE, DELETE y TRUNCATE.

**Reservas EN_REVISION (RF-D-ADM-01.2).**
- Al bloquear una publicación, sus reservas futuras CONFIRMADAS pasan a EN_REVISION en la misma transacción del
  bloqueo y se publica `ReservaEnRevision` por cada una (CA-20.1).
- `GET /admin/reservas?estado=EN_REVISION` las lista.
- `POST /admin/reservas/{id}/resolver` (`Reserva.resolver(mantener)`):
  - Con `{"mantener": true}` la reserva vuelve a CONFIRMADA (CA-20.2).
  - Con `{"mantener": false, "motivo": "..."}` queda CANCELADA con devolución del 100 % y `cancelada_por` = el
    administrador (CA-20.3).
  - En ambos casos publica `ReservaResuelta`, y también `ReservaCancelada` si se cancela.
- `reservas.services.cancelar_en_revision_vencidas()` (`Reserva.cancelar_sin_resolucion()`) cancela las EN_REVISION
  cuya fecha de llegada llegó: 100 %, motivo "Sin resolución antes de la llegada", `cancelada_por` NULL, y avisa al
  huésped y al anfitrión (CA-20.5).
- Restringir una cuenta no cambia el estado de sus reservas (RF-D-ADM-02.1).

## Notificaciones (MOD-07)

Tabla `notificacion`: `id`, `destinatario_id`, `tipo` VARCHAR(40), `mensaje` VARCHAR(300), `entidad` NULL,
`entidad_id` NULL, `leida` y `fecha`. `Notificacion.marcar_leida()`.

Notificaciones escucha los eventos de dominio **después de confirmar** la transacción. Los destinatarios y los
textos llegan en el detalle del evento, así no importa otras apps. Si crear un aviso falla, lo registra en la
auditoría (`NotificacionFallida`, en una transacción propia) y la operación sigue (CA-16.3, C4 nivel 3).

| Evento | Destinatarios |
|---|---|
| `ReservaConfirmada`, `ReservaCancelada`, `ReservaEnRevision` | Huésped y anfitrión |
| `ReservaResuelta` | Huésped |
| `PublicacionAprobada`, `PublicacionDevuelta`, `PublicacionBloqueada`, `PublicacionDesbloqueada` | Anfitrión |
| `PublicacionPausada`, `PublicacionReactivada` | Anfitrión, solo si lo hizo el Administrador |

`ResenaPublicada` llega con el módulo de Reseñas. `GET /notificaciones` devuelve `no_leidas` y la lista, primero las
no leídas y luego por fecha (CA-16.2). `POST /notificaciones/{id}/leida` marca una y `POST /notificaciones/leidas`
marca todas.

## Tareas programadas (operación interna)

`POST /interno/tareas/diarias` no usa JWT: compara el encabezado `X-Token-Tareas` con la variable `TOKEN_TAREAS`
(sin valor en el repositorio). Sin token o con uno incorrecto responde 403 y registra `AccesoDenegado`. Con el token
correcto ejecuta, en este orden:

1. `completar_vencidas()`
2. `cancelar_en_revision_vencidas()`
3. `conciliar_pagos()`

Registra `TareasDiarias` en la auditoría y responde
`{"reservas_completadas", "reservas_canceladas_sin_resolucion", "pagos_conciliados"}`. Para correrlo a mano:
`python manage.py tareas_diarias`. El workflow `.github/workflows/tareas-diarias.yml` lo llama a diario a las 05:10
UTC (00:10 en Colombia) con los secretos `API_URL` y `TOKEN_TAREAS`. `/api/v1/salud` sigue pública.

## Tablero y reportes (MOD-09)

**Periodo.** Una reserva pertenece al periodo según su fecha de **creación** (hora de Colombia), no la de llegada.
`reserva.creada` toma la hora de `apps/comun/reloj.py`, así que las pruebas y la demo pueden crear reservas "en
octubre" con los services reales. Máximo 12 meses; si `desde > hasta`, 400.

**Ingresos (nota de RF-D-ADM-05).**

| Estado | `monto_bruto` | `ingreso_plataforma` |
|---|---|---|
| CONFIRMADA, COMPLETADA, EN_REVISION | `total` | `tarifa_servicio` |
| CANCELADA | `total - valor_devolucion` | `tarifa_servicio * (1 - valor_devolucion / total)` |

Ejemplo (CA-24.4): una reserva de $740.000 con servicio de $60.000, cancelada con devolución de $370.000, suma $370.000
al bruto y $30.000 a la plataforma.

**`GET /admin/tablero?desde&hasta`** devuelve:
- `usuarios_por_rol`: cuentas registradas hasta `hasta`.
- `publicaciones_activas`.
- `reservas_por_estado` y `reservas_total` del periodo.
- `ingresos.bruto` e `ingresos.plataforma` del periodo.
- `top_ciudades`: las 5 ciudades con más reservas, de `v_demanda`.

**Reportes.** Los cinco (`usuarios`, `publicaciones`, `reservas`, `ingresos`, `demanda`), en PDF o Excel, usan las
mismas funciones de consulta del tablero (`reservas_del_periodo`, `conteo_por_estado`, `ingresos` y `demanda`), así
sus totales coinciden (CA-25.1). Cada descarga se registra como `ReporteDescargado`, con el administrador, el reporte,
el formato y el periodo, **antes** de entregar el archivo. Si no se puede registrar, el archivo no se entrega
(CA-25.2).

## Administración de usuarios y registro de acciones

**`GET /admin/usuarios?rol&q`** (Identidad) busca por nombre o correo y devuelve cada cuenta con `activa`,
`restringida`, `motivo_restriccion` y `restriccion_hasta`. Para restringir y quitar la restricción se siguen usando
`POST` y `DELETE /admin/usuarios/{id}/restriccion`.

**`GET /admin/auditoria`** filtra por `usuario` (actor), `tipo` de acción, `accion`, `desde` y `hasta`. Cada fila trae
`actor_nombre`, `actor_correo` y `actor_rol` (quién), `entidad` y `entidad_id` o el `detalle` (sobre qué), `fecha`
(cuándo) y `exitoso` (resultado). La respuesta incluye `tipos`, la lista de tipos de acción para el filtro (CA-23.3):

| `tipo` | Acciones |
|---|---|
| `inicio_sesion` | InicioSesion, CierreSesion |
| `acceso_no_permitido` | AccesoDenegado |
| `estado_publicacion` | PublicacionEnviadaARevision, PublicacionAprobada, PublicacionDevuelta, PublicacionBloqueada, PublicacionDesbloqueada, PublicacionPausada, PublicacionReactivada |
| `estado_reserva` | ReservaConfirmada, ReservaEnRevision, ReservaResuelta, ReservaCompletada |
| `reserva_rechazada` | ReservaRechazada |
| `cancelacion` | ReservaCancelada |
| `descarga_reporte` | ReporteDescargado |
| `accion_administrador` | Cualquier acción cuyo actor tiene rol ADMINISTRADOR |
| `cuenta`, `pago`, `operacion` | Registro, perfil y restricciones; pagos y devoluciones; fallas y tareas |

Las acciones de reseñas llegan con su módulo.

## Pagos (MOD-05)

Tabla `pago`: `id`, `cotizacion_id`, `reserva_id` NULL, `tipo` (`COBRO`, `DEVOLUCION`), `monto > 0`, `estado`
(`APROBADO`, `RECHAZADO`, `EN_VERIFICACION`), `referencia_externa` NULL, `clave_idempotencia` UUID único y `fecha`.
Un trigger impide DELETE y TRUNCATE, y solo permite cambiar `estado` y `referencia_externa` (RNF-E-CON-01).

- `PasarelaPagos` (`apps/pagos/pasarela.py`) con `cobrar(monto, clave, medio)` y `consultar(clave)`.
  - `AdaptadorStripe`: Stripe en modo prueba. Crea y confirma un PaymentIntent con el `payment_method` que manda el
    frontend desde Stripe Elements e `idempotency_key = clave`. El monto va en centavos de COP.
    `succeeded` → APROBADO, `processing`/`requires_action` → EN_VERIFICACION, el resto → RECHAZADO.
  - `AdaptadorSimulado`: aprueba siempre, salvo que `medio_pago` sea `"rechazar"` (para probar CA-13.3).
  - Se elige por variable de entorno: con `STRIPE_SECRET_KEY` se usa Stripe; sin ella, el simulado. Las pruebas
    usan siempre el simulado.
- `ServicioPagos.cobrar(cotizacion, clave, medio, reserva_id=...)` guarda el pago y lo registra en la auditoría
  (`PagoAprobado` o `PagoNoAprobado`) en la misma transacción. `ServicioPagos.devolver(cotizacion_id=..., reserva_id=..., monto=...)` registra una devolución **simulada**
  (`DEVOLUCION`, APROBADO, referencia `SIM-DEV-...`). Si el valor es 0 no crea pago (`monto > 0`). `PasarelaPagos` no
  tiene reembolsos, así que la devolución es simulada también cuando el cobro se hizo con Stripe en modo prueba.
- `pagos.services.conciliar_pagos()` (tarea diaria) consulta en la pasarela los pagos EN_VERIFICACION y actualiza
  `estado` y `referencia_externa`.

## Variables de entorno

| Variable | Dónde | Uso |
|---|---|---|
| `STRIPE_SECRET_KEY` | `backend/.env` o Render | Llave secreta de Stripe en modo prueba (`sk_test_...`). Vacía = pago simulado. |
| `VITE_STRIPE_PUBLIC_KEY` | `frontend/.env` o Render | Llave publicable (`pk_test_...`) para Stripe Elements. Vacía = pago simulado con opción de forzar rechazo. |
| `TOKEN_TAREAS` | `backend/.env`, Render y secreto de GitHub | Token del encabezado `X-Token-Tareas` de `/interno/tareas/diarias`. Vacío = la ruta responde 403 a todos. |
| `API_URL` | Secreto de GitHub | URL base del backend que llama el workflow `tareas-diarias.yml`. |

Las llaves van **solo** en variables de entorno: nunca en el código, en los `.env.example` (solo el nombre vacío) ni
en commits. Tarjeta de prueba de Stripe: 4242 4242 4242 4242.
