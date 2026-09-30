import time

from django.core.management.base import BaseCommand

from core import ticks


class Command(BaseCommand):
    help = "Processa os ticks pendentes do mundo (escopo 'world') até o tempo de jogo atual."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="Máximo de ticks por passada.")
        parser.add_argument("--loop", action="store_true", help="Repete indefinidamente.")
        parser.add_argument("--interval", type=float, default=5.0, help="Segundos reais entre passadas (--loop).")

    def handle(self, *args, limit, loop, interval, **opts):
        while True:
            r = ticks.advance_world(limit=limit)
            self.stdout.write(
                f"ticks={r.ticks_processed} até t={r.processed_until}s "
                f"{'(completo)' if r.complete else '(parcial: há mais pendente)'}"
            )
            if not loop:
                return
            if r.complete:
                time.sleep(interval)
