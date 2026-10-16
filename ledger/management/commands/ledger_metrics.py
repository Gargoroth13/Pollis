import json

from django.core.management.base import BaseCommand

from ledger.audit import ledger_metrics


class Command(BaseCommand):
    help = "Métricas do registro monetário (emissão, circulação, retido, sumidouro, contadores). Valores em centavos."

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(ledger_metrics(), ensure_ascii=False, indent=2, default=str))
