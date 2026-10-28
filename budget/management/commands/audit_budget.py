import json

from django.core.management.base import BaseCommand, CommandError

from budget.audit import audit_budget


class Command(BaseCommand):
    help = "Audita o Orçamento Público (design/09 §34): repasses, planos e pisos. Sai com erro se falhar."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Saída estruturada exportável")

    def handle(self, *args, **options):
        report = audit_budget()
        if options["json"]:
            self.stdout.write(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str))
        else:
            self.stdout.write(f"repasses={report.stats.get('transfer_decisions')} planos={report.stats.get('plans')} achados={len(report.findings)}")
            for f in report.findings:
                self.stdout.write(f"  [invariante {f['invariant']}] {f['code']} {({k: v for k, v in f.items() if k not in ('invariant', 'code')})}")
        if not report.ok:
            raise CommandError(f"{len(report.findings)} violação(ões) de integridade")
