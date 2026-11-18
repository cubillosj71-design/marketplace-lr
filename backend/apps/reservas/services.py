"""Interfaz pública de SRV-04 Reservas.

Es el único módulo que otros servicios pueden importar de esta app.
Nadie fuera de apps.reservas debe importar apps.reservas.models (regla verificada
con import-linter en el pipeline, ADR-001).
"""


def tiene_reservas_confirmadas_pendientes(usuario_id: int) -> bool:
    """¿El usuario tiene reservas CONFIRMADAS cuya fecha de llegada no ha pasado,
    como huésped o en alguno de sus alojamientos? (RF-D-USU-01.4)

    La usa SRV-01 Identidad antes de desactivar una cuenta (sección 3.3 del
    diseño: SRV-01 -> SRV-04, síncrona).

    Implementación provisional: mientras SRV-04 no tenga la tabla reserva no
    puede existir ninguna reserva, así que la respuesta correcta es False.
    Cuando se cree el modelo Reserva (MAL-13), reemplazar el cuerpo por:

        hoy = timezone.localdate()
        return Reserva.objects.filter(
            Q(huesped_id=usuario_id) | Q(publicacion__anfitrion_id=usuario_id),
            estado="CONFIRMADA",
            fecha_llegada__gte=hoy,
        ).exists()

    (publicacion__anfitrion_id cruza a Catálogo; si se quiere respetar la
    frontera, pedir a apps.catalogo.services los ids de las publicaciones del
    anfitrión y filtrar por publicacion_id__in.)
    """
    return False
