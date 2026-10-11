from django.core.management.base import BaseCommand, CommandError

from catalog.integrity import check_integrity


class Command(BaseCommand):
    help = "Confere a integridade do catálogo gravado. Erros reprovam; pendências de design apenas são listadas."

    def add_arguments(self, parser):
        parser.add_argument("--pending", action="store_true", help="lista também as pendências de design")

    def handle(self, *args, **opts):
        r = check_integrity()
        self.stdout.write(f"{r.stats}")
        for f in r.errors[:50]:
            self.stdout.write(f"  ERRO {f.code}: {f.subject} {f.detail}")
        if opts["pending"]:
            for f in r.pending:
                self.stdout.write(f"  PENDÊNCIA {f.code}: {f.subject}")
        else:
            self.stdout.write(f"pendências de design: {len(r.pending)} (use --pending)")
        if not r.ok:
            raise CommandError(f"{len(r.errors)} erro(s): {r.codes}")
        self.stdout.write("integridade: OK")
