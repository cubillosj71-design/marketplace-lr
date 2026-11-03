# ADR-007. Comunicación entre servicios: interfaces síncronas y eventos de dominio

**Estado:** Aceptada · 3 de noviembre de 2026

## Contexto

Notificaciones y Auditoría deben enterarse de casi todo lo que pasa, y Catálogo necesita que Reservas actúe al bloquear una publicación sin crear dependencias circulares.

## Decisión

Las consultas entre servicios son llamadas síncronas a su interfaz pública. Los hechos que interesan a otros se publican como eventos de dominio con señales de Django, que se despachan con transaction.on_commit para que solo salgan si la transacción se guardó.

## Alternativas

Un intermediario de mensajes como RabbitMQ con Celery (más infraestructura de la que el MVP necesita) y llamar directamente a Notificaciones y Auditoría desde cada servicio (acopla a todos con todos).

## Consecuencias

A favor: agregar un nuevo suscriptor no cambia a quien publica. En contra: los eventos se procesan en el mismo proceso y sin reintentos; si un suscriptor falla, la falla queda registrada (RNF-O-OPE-01).
