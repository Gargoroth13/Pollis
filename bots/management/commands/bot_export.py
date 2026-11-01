import datetime

from django.core.management.base import BaseCommand, CommandError

from bots import export
from bots.models import BotRun


class Command(BaseCommand):
    help = "Exporta uma execução do Bot Test (bot_test_AAAA-MM-DD.zip: CSV, JSON e JSONL; 21 §21.53)."

    def add_arguments(self, parser):
        parser.add_argument("--run", type=int, required=True)
        parser.add_argument("--out", default=None)

    def handle(self, *args, **o):
        run = BotRun.objects.filter(pk=o["run"]).first()
        if run is None:
            raise CommandError("execução inexistente")
        path = o["out"] or f"bot_test_{datetime.date.today().isoformat()}.zip"
        sizes = export.export_run(run, path)
        self.stdout.write(f"{path}: " + ", ".join(f"{n}={b}B" for n, b in sizes.items()))
