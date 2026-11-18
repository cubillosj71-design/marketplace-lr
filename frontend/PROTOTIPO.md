# Prototipo funcional: Usuarios y Alojamientos

Frontend en React 18 + TypeScript + Vite.

- **Módulo Usuarios: conectado a la API real** (SRV-01 Identidad, `backend/API.md`). Registro, inicio de sesión,
  cierre de sesión, recuperación de contraseña, perfil, cambio de contraseña y desactivación van contra el backend.
  El token de acceso vive en memoria y el de renovación en una cookie httpOnly (ADR-005, C4 nivel 2): al recargar la
  página la sesión se recupera sin pedir la contraseña.
- **Módulo Alojamientos y administración: siguen con datos de ejemplo** guardados en el `localStorage` del navegador,
  hasta que se conecten a sus servicios. La cuenta de la API se relaciona con estos datos por el correo.

## Cómo correrlo

Necesita el backend corriendo con los datos de ejemplo (ver `backend/API.md`):

```bash
cd backend && python manage.py migrate && python manage.py cargar_demo && python manage.py runserver
cd frontend
npm install
npm run dev        # http://localhost:5173 ; Vite reenvía /api/* a http://localhost:8000
```

Para generar la versión estática: `npm run build` (queda en `dist/`).

## Cuentas de prueba

Todas usan la contraseña `Clave1234`. En la pantalla de ingreso hay botones para entrar con un clic.

| Rol | Correo |
|---|---|
| Anfitrión | anfitrion@correo.com |
| Huésped | huesped@correo.com |
| Administrador | admin@inversioneslr.com |
| Cuenta restringida | restringido@correo.com |

## Pantallas

| Módulo | Pantalla | Ruta | Trazabilidad |
|---|---|---|---|
| USU | Iniciar sesión | `/ingresar` | CU-USU-02, RF-D-USU-01.2 |
| USU | Registro | `/registro` | CU-USU-01, RF-D-USU-01.1 |
| USU | Recuperar contraseña (enlace en pantalla, 20 min, un solo uso) | `/recuperar`, `/restablecer/:token` | CU-USU-03, RF-D-USU-01.3 |
| USU | Mi perfil y desactivar cuenta | `/perfil` | CU-USU-04, CU-USU-05, RF-D-USU-01.4 |
| USU | Cambiar contraseña | `/perfil/contrasena` | RF-D-USU-01.4 |
| USU | Roles y permisos | `/roles` | RF-D-USU-02.1 |
| USU | Reporte de usuarios (solo Administrador): periodo, rol, estado, descarga PDF o Excel | `/admin/reportes?tipo=usuarios` | RF-D-ADM-05.2, HU-25, CA-25.2, CA-25.3 |
| ALO | Mis publicaciones | `/publicaciones` | CU-ALO-03, RF-D-ALO-02.1 |
| ALO | Detalle, pausar, reactivar, enviar a revisión | `/publicaciones/:id` | CU-ALO-02, CU-ALO-05 |
| ALO | Nueva y editar publicación (2 pasos) | `/publicaciones/nueva`, `/publicaciones/:id/editar` | CU-ALO-01, CU-ALO-04, RF-D-ALO-01.1 |
| ALO | Calendario de disponibilidad | `/calendario` | CU-ALO-06, RF-D-ALO-02.2 |
| ALO | Reporte de publicaciones (solo Administrador): periodo, estado, ciudad, tipo, reservas, ingresos estimados, demanda por ciudad y tipo, descarga PDF o Excel | `/admin/reportes?tipo=publicaciones` | RF-D-ADM-05.2, RF-D-ADM-05.1, HU-25, CA-25.1, CA-25.2 |
| (RES) | Explorar alojamientos, huésped y visitante | `/explorar`, `/explorar-publico` | Búsqueda básica; la completa es del módulo RES |
| (ADM) | Todas las publicaciones, revisar, bloquear | `/admin/...` | RF-D-ADM-01.1, para cerrar el ciclo de estados |
| (ADM) | Tarifa de servicio: porcentaje vigente (0 % a 30 %) e historial | `/admin/tarifa` | RF-D-ADM-03.1, HU-22, CA-22.1 |
| (ADM) | Registro de acciones (inicios de sesión, accesos negados, cambios de estado, descargas de reportes) | `/admin/registro` | HU-23, BPMN-07 |

## Roles y permisos

| Rol | Qué puede usar |
|---|---|
| Visitante | Iniciar sesión, registrarse, recuperar contraseña, explorar alojamientos activos |
| Huésped | Su perfil, cambiar contraseña, desactivar su cuenta, roles, explorar y ver detalle |
| Anfitrión | Lo anterior de su cuenta, más sus publicaciones (crear, editar, enviar a revisión, pausar, reactivar) y su calendario |
| Administrador | Su perfil, moderar y modificar cualquier publicación, reportes de usuarios y publicaciones, registro de acciones |

Si alguien entra a una ruta que no le corresponde, ve "No tienes permiso" y el intento queda en el registro de acciones.

## Reportes

- Formatos: PDF y Excel .xlsx. Los genera el servidor (ReportLab y openpyxl, ADR-009); el frontend solo descarga el archivo. En Excel los valores en pesos van como número para poder sumarlos.
- El periodo por defecto es el año en curso. Si la fecha inicial es posterior a la final, la descarga se bloquea.
- Cada descarga queda en el registro de acciones con quién, fecha, hora, formato, periodo y número de registros.
- Las activas del reporte de publicaciones coinciden con el tablero de "Todas las publicaciones" (CA-25.1).
- En la vista publicada como artefacto el navegador bloquea las descargas; corriendo el proyecto o el HTML independiente sí descargan.

## Correspondencia con el diagrama de clases y el modelo relacional

| Clase / tabla | En el prototipo |
|---|---|
| Usuario | correo, nombre, teléfono, rol, estado, `fechaRegistro` y `aceptaDatosEn` (fecha y hora en que autorizó la Ley 1581). Sin ciudad, igual que en el diagrama. |
| RestriccionUsuario | motivo, fecha de inicio y fecha de fin. Al ingresar, la cuenta restringida ve el motivo y hasta cuándo. |
| TokenRecuperacion | creado, vence a los 20 minutos, un solo uso. |
| Publicacion | mismos atributos y estados; operaciones enviar a revisión, aprobar, devolver, pausar, reactivar, bloquear y desbloquear. |
| RevisionPublicacion | historial de moderación (APROBAR, DEVOLVER, PAUSAR, REACTIVAR, BLOQUEAR, DESBLOQUEAR) con observación, fecha y administrador. La observación de una devolución y el motivo de un bloqueo salen de aquí. |
| ReglaAlojamiento | cada regla es un registro con `descripcion` y `orden`. |
| ImagenPublicacion, Servicio, ServicioAdicional, PoliticaCancelacion | imágenes en orden, servicios incluidos, adicionales con precio y política Moderada con sus tramos. |
| Reserva | fechas, número de huéspedes, estado, `total` y `tarifaServicio` fijados al confirmar. |
| TarifaServicio | historial de porcentajes con `vigenteDesde`; 10 % inicial. El reporte usa el valor guardado en cada reserva, así un cambio no altera las confirmadas (CA-22.1). |
| EventoAuditoria | acción, entidad, id de la entidad, detalle, resultado y fecha. La IP la llena el backend; en el prototipo queda vacía. |

## Estructura

- `src/data.ts`: tipos, datos de ejemplo y reglas (datos obligatorios para revisión, noches ocupadas).
- `src/store.tsx`: estado global y acciones (sesión, validaciones, cambios de estado).
- `src/layout.tsx`: diseño de acceso, barra lateral por rol y protección por rol.
- `src/pages/`: una carpeta de pantallas por módulo (`reportes.tsx` descarga los cinco reportes del servidor).
- `src/styles.css`: sistema visual (colores, tipografía, componentes).

Cuando exista la API, las acciones de `store.tsx` se reemplazan por llamadas con `src/api.ts`.
