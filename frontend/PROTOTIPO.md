# Frontend: Alojamientos LR

React 18 + TypeScript + Vite. **Todas las pantallas leen y escriben en la API** (`/api/v1`, ver `backend/API.md`);
no hay datos locales ni copias en el navegador.

- **Sesión real (HU-02, ADR-005).** Se entra solo con `POST /identidad/token`, con el correo y la contraseña que
  escribe el usuario. El token de acceso vive en memoria (nunca en `localStorage` ni `sessionStorage`) y el de
  renovación en una cookie httpOnly. Al recargar, la sesión se recupera con `POST /identidad/token/renovar`; si no se
  puede, se va a "Ingresar". Cualquier 401 intenta renovar una vez; si falla, la sesión se cierra y "Ingresar"
  muestra "Tu sesión terminó. Vuelve a iniciar sesión.". "Salir" llama a `POST /identidad/salir`.
- **Rutas y menú por permisos (RF-D-USU-02.1).** Al entrar y al recargar se pide `GET /identidad/permisos`. Cada ruta
  declara el permiso que necesita (mismo nombre que en `backend/apps/comun/rbac.py`, ver `src/App.tsx`); sin él se ve
  "No tienes permiso para ver esta página" y sin sesión se va a "Ingresar". El menú lateral muestra solo las opciones
  cuyo permiso tiene el usuario. El rol solo se muestra en pantalla.

## Cómo correrlo

```bash
cd backend && python manage.py migrate && python manage.py cargar_demo --reiniciar && python manage.py runserver
cd frontend
npm install
npm run dev        # http://localhost:5173 ; Vite reenvía /api/* a http://localhost:8000
```

Para generar la versión estática: `npm run build` (queda en `dist/`).

## Cuentas de prueba

Todas usan la contraseña `Clave1234`. La pantalla "Ingresar" no muestra atajos a estas cuentas, porque la ve el
cliente: el correo y la contraseña se escriben a mano.

| Rol | Correo |
|---|---|
| Anfitrión | anfitrion@correo.com |
| Huésped | huesped@correo.com |
| Administrador | admin@inversioneslr.com |
| Cuenta restringida | restringido@correo.com |

## Pantallas y permiso que exige cada una

| Pantalla | Ruta | Permiso |
|---|---|---|
| Iniciar sesión, registro, recuperar contraseña | `/ingresar`, `/registro`, `/recuperar`, `/restablecer/:token` | Sin sesión |
| Explorar sin cuenta y detalle | `/explorar-publico`, `/explorar-publico/:id` | Sin sesión (Visitante: `busqueda.ver`) |
| Mi perfil y desactivar cuenta · Cambiar contraseña | `/perfil`, `/perfil/contrasena` | `perfil.gestionar` (desactivar: `cuenta.desactivar`) |
| Roles y permisos (matriz de `GET /identidad/roles`) | `/roles` | Solo sesión |
| Avisos | `/avisos` | `notificaciones.ver` |
| Explorar y detalle | `/explorar`, `/explorar/:id` | `busqueda.ver` |
| Cotización y pago | `/cotizacion/:id` | `reservas.cotizar` |
| Mis reservas | `/reservas` | `reservas.ver_propias` |
| Mis publicaciones, nueva, detalle | `/publicaciones`, `/publicaciones/nueva`, `/publicaciones/:id` | `publicaciones.gestionar_propias` |
| Editar publicación | `/publicaciones/:id/editar` | `publicaciones.gestionar_propias` o `publicaciones.moderar` |
| Calendario | `/calendario` | `calendario.gestionar` |
| Reservas de mis alojamientos | `/reservas-alojamientos` | `reservas.ver_de_mis_alojamientos` |
| Tablero | `/admin/tablero` | `tablero.ver` |
| Todas las publicaciones, pendientes, revisar | `/admin/publicaciones`, `/admin/revision`, `/admin/.../:id` | `publicaciones.moderar` |
| Reservas en revisión | `/admin/reservas` | `reservas.resolver` |
| Usuarios | `/admin/usuarios` | `usuarios.ver` |
| Tarifa de servicio | `/admin/tarifa` | `tarifa.configurar` |
| Registro de acciones | `/admin/registro` | `auditoria.consultar` |
| Reportes | `/admin/reportes` | `reportes.descargar` |

## Imágenes de las publicaciones

La API guarda la dirección (URL) de cada imagen (`imagen_publicacion.ruta`, hasta 500 caracteres). El formulario
agrega imágenes por URL o con "Agregar imagen de ejemplo". No hay subida de archivos: el backend no tiene un servicio
de almacenamiento de archivos y el esquema no se cambia.

## Estructura

- `src/api.ts`: cliente HTTP, sesión (token en memoria, renovación con la cookie) y llamadas por servicio.
- `src/store.tsx`: sesión actual (usuario y permisos) y avisos. Sin datos locales.
- `src/data.ts`: tipos, textos (roles, estados, permisos) y formatos.
- `src/layout.tsx`: diseño, menú por permisos y protección de rutas (`ConPermiso`).
- `src/pages/`: pantallas por módulo.
- `src/styles.css`: sistema visual.
