"""Corre a mano las tareas diarias: python manage.py tareas_diarias

Hace lo mismo que POST /api/v1/interno/tareas/diarias: COMPLETADA, EN_REVISION vencidas y conciliación de pagos.
"""

from django.core.management.base import BaseCommand

from apps.comun.tareas import ejecutar_tareas_diarias


class Command(BaseCommand):
    """Comando `python manage.py tareas_diarias`: corre a mano las tareas programadas.

    Hace lo mismo que POST /api/v1/interno/tareas/diarias y muestra el resumen; si alguna tarea
    falla, lo informa en rojo y las demás corren igual.
    """
    help = "Completa reservas vencidas, cancela EN_REVISION sin resolver y concilia pagos EN_VERIFICACION."

    def handle(self, *args, **opciones):
        r = ejecutar_tareas_diarias("comando")
        resumen = (f"Reservas completadas: {r['reservas_completadas']} · canceladas sin resolución: "
                   f"{r['reservas_canceladas_sin_resolucion']} · pagos conciliados: {r['pagos_conciliados']}")
        if r.get("errores"):  # las demás tareas sí corrieron; el detalle quedó en el log y en la auditoría
            self.stderr.write(self.style.ERROR(f"{resumen} · fallaron: {', '.join(r['errores'])} (ver ErrorOperacion)"))
        else:
            self.stdout.write(self.style.SUCCESS(resumen))
