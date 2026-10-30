import json

from django.core.management.base import BaseCommand, CommandError

from legislation.audit import audit_legislation


class Command(BaseCommand):
    help = "Audita o processo legislativo (design/07 §07.25-§07.26): propostas, votações, vigor. Sai com erro se falhar."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Saída estruturada exportável")

    def handle(self, *args, **options):
        report = audit_legislation()
        if options["json"]:
            self.stdout.write(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str))
        else:
            self.stdout.write(f"propostas={report.stats.get('proposals')} votacoes={report.stats.get('rounds')} achados={len(report.findings)}")
            for f in report.findings:
                self.stdout.write(f"  [invariante {f['invariant']}] {f['code']} {({k: v for k, v in f.items() if k not in ('invariant', 'code')})}")
        if not report.ok:
            raise CommandError(f"{len(report.findings)} violação(ões) de integridade")
