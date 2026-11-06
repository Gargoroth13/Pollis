import json

from django.core.management.base import BaseCommand, CommandError

from rankings.audit import audit_rankings


class Command(BaseCommand):
    help = "Audita os Rankings (design/14 §14.9): integridade das sequências e dos recordes. Sai com erro se falhar."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Saída estruturada exportável")

    def handle(self, *args, **options):
        report = audit_rankings()
        if options["json"]:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        else:
            st = report["stats"]
            self.stdout.write(f"sequências={st['streaks']} recordes={st['records']} achados={len(report['findings'])}")
            for f in report["findings"]:
                self.stdout.write(f"  {f}")
        if not report["ok"]:
            raise CommandError(f"{len(report['findings'])} violação(ões) de integridade")
