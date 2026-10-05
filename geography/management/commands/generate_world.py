from django.core.management.base import BaseCommand, CommandError

from geography.balance import get_scenario
from geography.generator import WorldAlreadyExists, generate_world
from geography.integrity import check_integrity


class Command(BaseCommand):
    help = "Gera o mundo (Estado → Cidade → Bairro → Lote) a partir do cenário e confere a integridade."

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int)
        parser.add_argument("--states", type=int)
        parser.add_argument("--cities-per-state", type=int)

    def handle(self, *args, seed, states, cities_per_state, **opts):
        overrides = {k: v for k, v in (("seed", seed), ("states", states), ("cities_per_state", cities_per_state)) if v is not None}
        sc = get_scenario(**overrides)
        try:
            s = generate_world(sc)
        except WorldAlreadyExists as e:
            raise CommandError(str(e))
        self.stdout.write(f"cenário '{sc.name}' (seed {sc.seed}): {s.states} estados, {s.cities} cidades, "
                          f"{s.neighborhoods} bairros, {s.lots} lotes")
        self.stdout.write(f"lotes por categoria: {s.lots_by_category}")
        self.stdout.write(f"depósitos: {s.deposits_by_resource}")
        report = check_integrity(sc)
        self.stdout.write("integridade: OK" if report.ok else f"integridade: FALHOU {report.codes}")
        if not report.ok:
            raise CommandError("O mundo gerado violou a integridade territorial.")
