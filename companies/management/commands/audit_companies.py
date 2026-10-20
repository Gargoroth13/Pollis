import json

from django.core.management.base import BaseCommand, CommandError

from companies.audit import audit_companies


class Command(BaseCommand):
    help = ("Audita as Empresas (design/02 §15-17): cargo Dono, conta, fundação, aporte, cargos/mural, candidaturas, salário de "
            "trabalho e folha diária do Dono. Sai com erro se falhar.")

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Saída estruturada exportável")

    def handle(self, *args, **options):
        report = audit_companies()
        if options["json"]:
            self.stdout.write(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str))
        else:
            s = report.stats
            self.stdout.write(f"empresas={s.get('companies')} aportes={s.get('contributions')} capital={s.get('capital')} "
                              f"achados={len(report.findings)}")
            for f in report.findings:
                self.stdout.write(f"  [invariante {f['invariant']}] {f['code']} "
                                  f"{({k: v for k, v in f.items() if k not in ('invariant', 'code')})}")
        if not report.ok:
            raise CommandError(f"{len(report.findings)} violação(ões) de integridade")
