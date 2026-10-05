from django.core.management.base import BaseCommand, CommandError

from geography.integrity import check_integrity


class Command(BaseCommand):
    help = "Confere a integridade territorial do mundo existente contra o cenário em vigor."

    def handle(self, *args, **opts):
        report = check_integrity()
        self.stdout.write(f"{report.stats}")
        for v in report.violations[:50]:
            self.stdout.write(f"  {v.code}: {v.detail}")
        if not report.ok:
            raise CommandError(f"{len(report.violations)} violação(ões): {report.codes}")
        self.stdout.write("integridade: OK")
