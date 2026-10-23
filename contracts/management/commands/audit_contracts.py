import json

from django.core.management.base import BaseCommand, CommandError

from contracts.audit import audit_contracts


class Command(BaseCommand):
    help = "Audita os Contratos (design/18): termos, histórico, execuções, dinheiro e estoque. Sai com erro se falhar."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Saída estruturada exportável")

    def handle(self, *args, **options):
        report = audit_contracts()
        if options["json"]:
            self.stdout.write(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str))
        else:
            self.stdout.write(f"contratos={report.stats.get('contracts')} achados={len(report.findings)}")
            for f in report.findings:
                self.stdout.write(f"  [invariante {f['invariant']}] {f['code']} "
                                  f"{({k: v for k, v in f.items() if k not in ('invariant', 'code')})}")
        if not report.ok:
            raise CommandError(f"{len(report.findings)} violação(ões) de integridade")
