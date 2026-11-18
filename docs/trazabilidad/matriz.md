# Matriz de trazabilidad: permisos por rol (RF-D-USU-02.1)

Fuente: SRS v3.7, sección 2 (matriz de permisos) y RF-D-USU-02.1; HU-05 (CA-05.1 a CA-05.3).
Código: `backend/apps/comun/rbac.py` (matriz), `backend/apps/comun/permisos.py` (`RequierePermiso`).
Pruebas: `backend/apps/comun/tests/test_rbac.py`.

Cada cuenta tiene un único rol (`usuario.rol`); quien no inició sesión es Visitante. El permiso dice **qué** puede
hacer el rol; **sobre qué** recurso (regla de dueño, CA-05.3) lo revisa el service de cada módulo.

## Permiso, roles, rutas y requerimiento

| Permiso | Roles | Rutas | RF |
|---|---|---|---|
| `busqueda.ver` | Visitante, Huésped | `GET /busqueda/publicaciones` · `GET /busqueda/publicaciones/{id}` | RF-D-RES-01.1, 01.2 |
| `cuenta.registrar` | Visitante | `POST /identidad/registro` | RF-D-USU-01.1 |
| `catalogo.ver` | Visitante, Huésped, Anfitrión, Administrador | `GET /catalogo/ciudades` · `/tipos-alojamiento` · `/servicios` | RF-D-RES-01.1, ALO-01.1, ADM-05.2 |
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

`catalogo.ver` no estaba en la matriz de la tarea: se agregó porque los catálogos fijos (ciudades, tipos y
servicios) los necesitan los cuatro roles: el Visitante y el Huésped para filtrar la búsqueda (RF-D-RES-01.1), el
Anfitrión para crear la publicación (RF-D-ALO-01.1) y el Administrador para filtrar reportes (RF-D-ADM-05.2).

Rutas sin `RequierePermiso` (lista blanca): `GET /salud`, `POST /identidad/token`, `POST /identidad/token/renovar`,
`POST /identidad/salir`, `POST /identidad/recuperacion`, `GET y POST /identidad/recuperacion/{token}`,
`GET /identidad/permisos` y `POST /interno/tareas/diarias` (su propio token `X-Token-Tareas`).

## Criterios de aceptación y pruebas

| Criterio | Qué se verifica | Prueba |
|---|---|---|
| CA-05.1 | Sin sesión, una ruta cuyo permiso no tiene el Visitante responde 401 | `test_rbac.py::test_rol_por_ruta` (rol VISITANTE); `reservas/tests/test_cotizacion.py::test_ca_05_1_visitante_no_cotiza` |
| CA-05.2 | Con sesión y sin el permiso: 403 y `AccesoDenegado` con `exitoso=false`, ruta, permiso y rol | `test_rbac.py::test_rol_por_ruta`; `auditoria/tests/test_auditoria.py::test_ca_05_2_huesped_en_la_revision_de_publicaciones_queda_registrado` |
| CA-05.3 | Un anfitrión no modifica la publicación de otro (regla de dueño en el service) | `catalogo/tests/test_catalogo.py::test_ca_05_3_solo_el_dueno_o_el_admin_modifican` y `::test_ca_05_2_intento_ajeno_queda_registrado` |
| RF-D-USU-02.1 | Cada ruta con los cuatro roles devuelve 200/201, 403 o 401 según la matriz | `test_rbac.py::test_rol_por_ruta` |
| RF-D-USU-02.1 | Toda ruta declara `RequierePermiso`, salvo la lista blanca | `test_rbac.py::test_toda_ruta_declara_requiere_permiso_salvo_la_lista_blanca` |
| RF-D-USU-02.1 | `GET /identidad/permisos` devuelve el rol y sus permisos | `test_rbac.py::test_permisos_del_usuario_actual` |
| HU-05 | Ninguna vista usa `TieneRol` ni sus alias | `test_rbac.py::test_ninguna_vista_usa_tiene_rol_ni_sus_alias` |
