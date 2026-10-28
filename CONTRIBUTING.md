# Estrategia de ramas y flujo de trabajo

Usamos un flujo basado en GitHub Flow: una rama principal estable y una rama corta por cada historia, tarea o defecto de Jira. Ningún cambio llega a `main` sin Pull Request.

## Ramas

| Rama | Para qué | Ejemplo |
|---|---|---|
| `main` | Código estable e integrado. Protegida: no recibe pushes directos. | |
| `feature/LR-<n>-<descripcion>` | Una historia de usuario o tarea nueva | `feature/LR-12-crear-reserva` |
| `fix/LR-<n>-<descripcion>` | Corrección de un defecto | `fix/LR-31-total-cotizacion` |
| `docs/<descripcion>` | Solo documentación | `docs/actualizar-readme` |

La descripción va en minúsculas, sin tildes y con guiones. Con la clave `LR-<n>` en el nombre, Jira enlaza la rama con su historia.

## Commits

Formato:

```
LR-<n>: <tipo> <descripción en presente>
```

Tipos: `feat` (funcionalidad), `fix` (corrección), `test` (pruebas), `docs` (documentación), `refactor` (cambio interno sin cambiar el comportamiento) y `chore` (configuración o dependencias).

Ejemplos:

```
LR-12: feat validar solapamiento de fechas al confirmar la reserva
LR-12: test agregar caso de reserva superpuesta
LR-31: fix redondear la tarifa de servicio a dos decimales
```

Cada commit debe ser un cambio coherente que se pueda entender solo.

## Flujo de una historia

```
Historia en Jira → rama → commits → Pull Request → GitHub Actions → pruebas → SonarCloud → revisión → merge
```

1. Mover la historia a "En curso" en Jira.
2. Actualizar `main` y crear la rama:
   ```
   git checkout main
   git pull
   git checkout -b feature/LR-12-crear-reserva
   ```
3. Hacer commits con el formato de arriba y subir la rama:
   ```
   git push -u origin feature/LR-12-crear-reserva
   ```
4. Abrir el Pull Request hacia `main` usando la plantilla. El título lleva la clave de Jira.
5. Esperar a que GitHub Actions y SonarCloud terminen en verde.
6. Pedir revisión a otro integrante. El autor corrige las observaciones o explica por qué no aplican.
7. Con la aprobación y los checks en verde, hacer merge con "Squash and merge" y borrar la rama.
8. Mover la historia a "Hecho" en Jira y actualizar la matriz de trazabilidad.

## Reglas de `main`

- Se requiere Pull Request para integrar.
- Se requiere al menos una aprobación de otro integrante.
- Las conversaciones del Pull Request deben quedar resueltas.
- Los checks de GitHub Actions y el Quality Gate de SonarCloud deben pasar (se activan en el Sprint 0).
- Nadie hace merge de su propio Pull Request sin aprobación.

## Releases

Al cerrar cada sprint se crea un release con etiqueta `vX.Y.Z` y la lista de historias incluidas:

| Release | Contenido |
|---|---|
| `v0.1.0` | Sprint 0: estructura, pipeline y SonarCloud |
| `v0.2.0` | Sprint 1: flujo crítico |
| `v1.0.0` | Sprint 2: MVP completo |
