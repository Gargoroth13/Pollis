import json

from django.core.management.base import BaseCommand, CommandError

from geography.models import Lot
from properties import services
from properties.constants import OwnerKind


class Command(BaseCommand):
    help = ("Ferramenta do sistema/Dev: abre leilões públicos (design/10 §4) para lotes do governo. Quem decide abrir leilões no jogo "
            "é lacuna de design registrada em design/10a; este comando NÃO é ação de jogador.")

    def add_arguments(self, parser):
        parser.add_argument("--lot", type=int, action="append", help="id do lote (repetível); sem isso, usa --category/--limit")
        parser.add_argument("--category", default=None, help="categoria dos lotes do governo a leiloar")
        parser.add_argument("--limit", type=int, default=0, help="máximo de lotes quando usa --category")
        parser.add_argument("--min-bid", type=int, required=True, help="lance mínimo em centavos")

    def handle(self, *args, **opts):
        lots = list(opts["lot"] or [])
        if not lots:
            if not opts["category"] or opts["limit"] <= 0:
                raise CommandError("Informe --lot, ou --category com --limit > 0")
            for lot in Lot.objects.filter(category=opts["category"], occupation="empty").order_by("pk"):
                if services.owner_of_lot(lot.pk)[0] is OwnerKind.GOVERNMENT:
                    lots.append(lot.pk)
                if len(lots) >= opts["limit"]:
                    break
        results = [{"lot": lot, **{"code": (r := services.open_auction(lot, opts["min_bid"])).code, "ok": r.ok, "detail": r.detail}} for lot in lots]
        self.stdout.write(json.dumps(results, ensure_ascii=False, default=str))
        if any(not r["ok"] for r in results):
            raise CommandError("Algum leilão não pôde ser aberto")
