# ADR-005. Autenticación con JWT y permisos por rol

**Estado:** Aceptada · 3 de noviembre de 2026

## Contexto

La aplicación web corre en un dominio distinto al de la API y hay tres roles más el visitante.

## Decisión

Tokens JWT con SimpleJWT: acceso de 30 minutos y renovación de 24 horas, con lista negra para cerrar sesión. Permisos de DRF por rol y por dueño del recurso; el estado de la cuenta se revisa en cada petición, así que una cuenta restringida pierde el acceso de inmediato.

## Alternativas

Sesiones con cookies (más complejas entre dominios por CORS y CSRF) y un proveedor externo de identidad (fuera del alcance del MVP).

## Consecuencias

A favor: la API no guarda sesiones y la aplicación web es independiente. En contra: el token de acceso vigente sigue sirviendo hasta que vence; la revisión del estado de la cuenta en cada petición cubre ese caso.
