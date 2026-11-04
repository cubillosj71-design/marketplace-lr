# ADR-006. Pagos simulados con Stripe en modo prueba mediante un adaptador

**Estado:** Aceptada · 3 de noviembre de 2026

## Contexto

El enunciado exige simular los pagos con un servicio como Stripe en versión de pruebas.

## Decisión

El servicio Pagos encapsula Stripe detrás de la interfaz IPagos (cobrar y devolver). El front usa Stripe Elements para obtener el medio de pago; la API crea y confirma un PaymentIntent y, al cancelar, un Refund, siempre con clave de idempotencia.

## Alternativas

Simular el pago con una respuesta aleatoria propia (no demuestra integración con un servicio externo) y llamar a Stripe directamente desde Reservas (acopla el negocio a un proveedor).

## Consecuencias

A favor: cambiar de proveedor o usar un simulador en las pruebas solo afecta al adaptador. En contra: las pruebas de integración reales dependen de la red; en el pipeline se usa el simulador.
