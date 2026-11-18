"""Corre a mano las tareas diarias: python manage.py tareas_diarias

Hace lo mismo que POST /api/v1/interno/tareas/diarias: COMPLETADA, EN_REVISION vencidas y conciliación de pagos.
"""

from django.core.management.base import BaseCommand

from apps.comun.tareas import ejecutar_tareas_diarias


class Command(BaseCommand):
    help = "Completa reservas vencidas, cancela EN_REVISION sin resolver y concilia pagos EN_VERIFICACION."

    def handle(self, *args, **opciones):
        r = ejecutar_tareas_diarias("comando")
        self.stdout.write(self.style.SUCCESS(
            f"Reservas completadas: {r['reservas_completadas']} · canceladas sin resolución: "
            f"{r['reservas_canceladas_sin_resolucion']} · pagos conciliados: {r['pagos_conciliados']}"
        ))
