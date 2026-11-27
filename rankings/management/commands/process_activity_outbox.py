import json
import time

from django.core.management.base import BaseCommand

from rankings import outbox


class Command(BaseCommand):
    help = ("Worker da outbox de atividade (design/14a §3.6): atualiza as sequências de atividade a partir dos eventos pendentes. "
            "Retomável: os eventos são duráveis. Seguro com vários workers (trava por jogador).")

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Repete até ser interrompido")
        parser.add_argument("--interval", type=float, default=5.0, help="Segundos entre passadas com --loop")
        parser.add_argument("--json", action="store_true", help="Saída estruturada")

    def handle(self, *args, **options):
        while True:
            summary = outbox.process_pending().to_dict()
            self.stdout.write(json.dumps(summary, ensure_ascii=False) if options["json"] else
                              f"jogadores={summary['players']} processados={summary['events_processed']} "
                              f"falhas={summary['events_failed']} pendentes={summary['pending_after']} "
                              f"{summary['duration_ms']}ms queries={summary['queries']}")
            if not options["loop"]:
                return
            time.sleep(options["interval"])
