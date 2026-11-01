from django.core.management.base import BaseCommand

from bots import params, population


class Command(BaseCommand):
    help = "Inicia uma execução do Bot Test (população-alvo, taxa de criação e seed configuráveis)."

    def add_arguments(self, parser):
        parser.add_argument("--name", default="bot-test")
        parser.add_argument("--target", type=int, default=params.DEFAULT_TARGET_POPULATION)
        parser.add_argument("--interval", type=int, default=params.DEFAULT_CREATION_INTERVAL_REAL_SECONDS, help="segundos REAIS entre criações")
        parser.add_argument("--seed", type=int, default=0)

    def handle(self, *args, **o):
        run = population.start_run(o["name"], target_population=o["target"], creation_interval_real_seconds=o["interval"], global_seed=o["seed"])
        self.stdout.write(f"execução {run.pk} iniciada: alvo={run.target_population} intervalo={run.creation_interval_real_seconds}s seed={run.global_seed}")
