# ADR-004. Restricción de exclusión e idempotencia contra la doble reserva

**Estado:** Aceptada · 3 de noviembre de 2026

## Contexto

La doble reserva es el problema que motivó el proyecto (OB-02). La regla RN-08 exige verificar la disponibilidad otra vez al confirmar, y RN-13 que los reintentos no creen duplicados.

## Decisión

Restricción EXCLUDE USING gist en la tabla reserva sobre el alojamiento y el rango de fechas, y columna clave_idempotencia única que llega en el encabezado Idempotency-Key. La reserva se crea dentro de una transacción.

## Alternativas

Validar solo en la aplicación (dos solicitudes simultáneas podrían pasar la validación a la vez) y bloquear la tabla completa al reservar (funciona, pero frena a todos los usuarios).

## Consecuencias

A favor: la base de datos garantiza la regla aunque haya solicitudes simultáneas. En contra: requiere la extensión btree_gist, disponible en PostgreSQL gestionado.
