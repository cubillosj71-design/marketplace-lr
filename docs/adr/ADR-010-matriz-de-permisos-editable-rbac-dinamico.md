# ADR-010. Matriz de permisos editable por el Administrador (RBAC dinámico)

**Estado:** Propuesta · 18 de noviembre de 2026. Complementa a ADR-005 y no lo reemplaza: la autenticación con JWT y la revisión del estado de la cuenta en cada petición no cambian.

## Contexto

El control de acceso por rol (RF-D-USU-02.1, HU-05) usaba una matriz fija en el código (`apps/comun/rbac.py`), así que cambiar qué puede hacer un rol obligaba a modificar el código y volver a desplegar. El cliente pidió que los roles sean dinámicos: que el Administrador decida, desde la plataforma, qué puede hacer cada rol.

Hay tres límites que vienen de los documentos y del código:

- El SRS fija tres roles con cuenta más el Visitante, y AMB-07 dice que cada cuenta tiene un único rol. El SRS dice además que el MVP no necesita un cuarto rol.
- `usuario.rol` tiene `CHECK rol IN ('HUESPED','ANFITRION','ADMINISTRADOR')`.
- Algunos services atan una función a un rol, además del permiso. Por ejemplo, moderar revisa que quien llama sea ADMINISTRADOR, y gestionar publicaciones revisa que sea el anfitrión dueño. Si a un rol se le diera un permiso así, pasaría el control de la vista y el service lo seguiría tratando como su rol real.

## Decisión

Los **roles son fijos** y los **permisos de cada rol son editables**.

- Dos tablas nuevas en Identidad: `permiso` (código y descripción) y `rol_permiso` (rol y permiso, únicos juntos, con `CHECK` sobre los cuatro roles). Que exista la fila significa que el rol tiene el permiso.
- `rbac.permisos_de()` lee `rol_permiso` en cada petición, sin caché. Gunicorn corre varios procesos y una caché en memoria dejaría a algunos con la matriz vieja. Es una consulta por llave única.
- `apps.comun` no importa Identidad. Identidad registra su consulta con `rbac.registrar_fuente()` al iniciar (inversión de dependencia), así `lint-imports` sigue verificando que ninguna app depende de otra a través de `comun` (ADR-001).
- `rbac.py` conserva las reglas que no se editan:
  - `PERMISOS`: la matriz inicial del SRS.
  - `ASIGNABLES`: qué permisos se le pueden dar a cada rol. Las consultas de administración que solo dependen del permiso (usuarios, tablero, reportes y registro de acciones) se pueden dar a otros roles. Las acciones que el service ata a un rol, no.
  - `FIJOS`: lo que no se le puede quitar a un rol. `catalogo.ver`, porque sin él no cargan ni las ciudades del registro, y `roles.gestionar` del Administrador, porque si se lo quitara nadie podría volver a editar la matriz.
- La matriz inicial se carga en `post_migrate` y **solo si `rol_permiso` está vacía**. `post_migrate` corre después de cada `migrate` y de cada `flush` (`cargar_demo --reiniciar` y las pruebas con `transaction=True`). Un despliegue no deshace lo que cambió el Administrador.
- Nuevo permiso `roles.gestionar` y nuevas rutas `PUT` y `DELETE /admin/roles/{rol}/permisos/{codigo}`. Cada cambio queda en el registro de acciones (`PermisoConcedido` y `PermisoRetirado`, tipo "Cambio de permisos de un rol").

## Alternativas

- **Matriz fija en el código** (la decisión anterior): más simple, pero cada cambio de permisos exige desplegar.
- **Roles nuevos creados por el Administrador**: contradice el SRS y AMB-07, obliga a cambiar `usuario.rol` y a revisar las 38 comparaciones con un rol fijo que hay en 14 archivos. El riesgo es alto y ningún requerimiento lo pide.
- **Grupos y permisos de Django** (`PermissionsMixin`): agrega cinco tablas pensadas para el panel de Django y no para la API, y el modelo de Identidad lo descartó a propósito.

## Consecuencias

- A favor: el Administrador cambia qué puede hacer cada rol sin desplegar, y el cambio rige desde la siguiente petición, incluso con el token vigente. La matriz inicial sigue siendo la del SRS.
- En contra: el modelo relacional del SDD (sección 10) gana dos tablas que no estaban en el diseño, y la trazabilidad debe registrarlo. Cada petición protegida hace una consulta más a la base. La pantalla de un usuario que ya está dentro muestra el menú viejo hasta que recarga, aunque la API ya aplica la matriz nueva.
