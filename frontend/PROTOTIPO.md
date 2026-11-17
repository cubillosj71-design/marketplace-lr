# Prototipo funcional: Usuarios y Alojamientos

Frontend en React 18 + TypeScript + Vite, con datos de ejemplo en memoria (sin backend). Los cambios se guardan en el `localStorage` del navegador.

## Cómo correrlo

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
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
| ALO | Mis publicaciones | `/publicaciones` | CU-ALO-03, RF-D-ALO-02.1 |
| ALO | Detalle, pausar, reactivar, enviar a revisión | `/publicaciones/:id` | CU-ALO-02, CU-ALO-05 |
| ALO | Nueva y editar publicación (2 pasos) | `/publicaciones/nueva`, `/publicaciones/:id/editar` | CU-ALO-01, CU-ALO-04, RF-D-ALO-01.1 |
| ALO | Calendario de disponibilidad | `/calendario` | CU-ALO-06, RF-D-ALO-02.2 |
| (RES) | Explorar alojamientos, huésped y visitante | `/explorar`, `/explorar-publico` | Búsqueda básica; la completa es del módulo RES |
| (ADM) | Todas las publicaciones, revisar, bloquear | `/admin/...` | RF-D-ADM-01.1, para cerrar el ciclo de estados |

## Estructura

- `src/data.ts`: tipos, datos de ejemplo y reglas (datos obligatorios para revisión, noches ocupadas).
- `src/store.tsx`: estado global y acciones (sesión, validaciones, cambios de estado).
- `src/layout.tsx`: diseño de acceso, barra lateral por rol y protección por rol.
- `src/pages/`: una carpeta de pantallas por módulo.
- `src/styles.css`: sistema visual (colores, tipografía, componentes).

Cuando exista la API, las acciones de `store.tsx` se reemplazan por llamadas con `src/api.ts`.
