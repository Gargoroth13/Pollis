import time

from django.core.management.base import BaseCommand, CommandError

from bots import population, runner
from bots.constants import RunStatus
from bots.models import BotRun
from bots.policy import UniformMaskedPolicy
from core import ticks


class Command(BaseCommand):
    help = "Uma passada do Bot Test (ou um laço): avança o mundo, cria Bots devidos e avalia os Bots vencidos pelo Action Registry normal."

    def add_arguments(self, parser):
        parser.add_argument("--run", type=int, required=True)
        parser.add_argument("--loop", action="store_true", help="repete até Ctrl-C")
        parser.add_argument("--sleep", type=float, default=5.0, help="segundos reais entre passadas no laço")
        parser.add_argument("--limit", type=int, default=None, help="máximo de Bots avaliados por passada")

    def handle(self, *args, **o):
        run = BotRun.objects.filter(pk=o["run"]).first()
        if run is None:
            raise CommandError("execução inexistente")
        policy = UniformMaskedPolicy()
        while True:
            run.refresh_from_db()
            if run.status != RunStatus.RUNNING.value:
                self.stdout.write("execução parada")
                return
            ticks.advance_world()
            created = population.step(run)
            m = runner.run_due(run, policy, limit=o["limit"], created=len(created))
            population.snapshot_population(run)
            self.stdout.write(f"criados={m.created} avaliados={m.evaluated} agiram={m.acted} erros={m.errors} fila={m.backlog_after} t={m.real_seconds:.3f}s")
            if not o["loop"]:
                return
            time.sleep(o["sleep"])
