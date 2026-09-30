from django.core.management.base import BaseCommand, CommandError

from core import clock
from core.models import WorldClock
from core.timeline import describe


class Command(BaseCommand):
    help = "Mostra ou altera o relógio do mundo."

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest="action", required=True)
        sub.add_parser("show", help="Mostra o tempo de jogo atual e a velocidade.")
        sp = sub.add_parser("set-speed", help="Define quantos segundos reais dura 1 dia de jogo.")
        sp.add_argument("real_seconds_per_game_day", type=int)

    def handle(self, *args, action, **opts):
        if action == "set-speed":
            try:
                clock.set_speed(opts["real_seconds_per_game_day"])
            except ValueError as e:
                raise CommandError(str(e))
        wc = WorldClock.load()
        now = clock.now()
        self.stdout.write(f"Agora (jogo): t={now}s = {describe(now)}")
        self.stdout.write(f"Velocidade: 1 dia de jogo = {wc.real_seconds_per_game_day}s reais")
        self.stdout.write(f"Ticks do mundo processados até: t={wc.world_processed_until}s")
