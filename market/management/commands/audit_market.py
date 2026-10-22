import json

from django.core.management.base import BaseCommand, CommandError

from market.audit import audit_market


class Command(BaseCommand):
    help = ("Audita a Transparência de Mercado (design/17): vendas do histórico contra o registro monetário e agregados diários "
            "contra o histórico bruto. Sai com erro se falhar.")

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Saída estruturada exportável")

    def handle(self, *args, **options):
        report = audit_market()
        if options["json"]:
            self.stdout.write(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str))
        else:
            s = report.stats
            self.stdout.write(f"transacoes={s.get('transactions')} dias_fechados={s.get('closed_days')} achados={len(report.findings)}")
            for f in report.findings:
                self.stdout.write(f"  [invariante {f['invariant']}] {f['code']} "
                                  f"{({k: v for k, v in f.items() if k not in ('invariant', 'code')})}")
        if not report.ok:
            raise CommandError(f"{len(report.findings)} violação(ões) de integridade")
