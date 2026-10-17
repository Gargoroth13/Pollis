import json

from django.core.management.base import BaseCommand, CommandError

from ledger.audit import audit_ledger


class Command(BaseCommand):
    help = "Audita o registro monetário (design/24 §24.17): reconstrói saldos a partir dos lançamentos. Sai com erro se falhar."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Saída estruturada exportável")

    def handle(self, *args, **options):
        report = audit_ledger()
        if options["json"]:
            self.stdout.write(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str))
        else:
            self.stdout.write(f"contas={report.stats.get('accounts')} lançamentos={report.stats.get('entries')} "
                              f"emitido={report.stats.get('emitted')} achados={len(report.findings)}")
            for f in report.findings:
                self.stdout.write(f"  [invariante {f['invariant']}] {f['code']} {({k: v for k, v in f.items() if k not in ('invariant', 'code')})}")
        if not report.ok:
            raise CommandError(f"{len(report.findings)} violação(ões) de integridade")
