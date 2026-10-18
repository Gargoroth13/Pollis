import json

from django.core.management.base import BaseCommand

from catalog import audit


class Command(BaseCommand):
    help = ("Exporta a tabela auditável dos valores provisórios [PROV] do catálogo (GD 2026-10-14, Q3) e a classificação "
            "(categoria, tags, canais). `--format markdown` gera as tabelas §3 e §4 do design/22.")

    def add_arguments(self, parser):
        parser.add_argument("--format", choices=("text", "json", "markdown"), default="text")

    def handle(self, *args, **opts):
        fmt = opts["format"]
        if fmt == "markdown":
            sections = (("### 3. Classificação e canais comerciais", audit.markdown_classification()),
                        ("### 4.1 Parâmetros gerais [PROV]", audit.markdown_general_provisional()),
                        ("### 4.2 Preço-base de referência por produto [PROV]", audit.markdown_base_prices()))
            for title, lines in sections:
                self.stdout.write(title + "\n")
                self.stdout.write("\n".join(lines) + "\n")
            return
        rows = audit.provisional_table()
        if fmt == "json":
            self.stdout.write(json.dumps([r.__dict__ for r in rows], ensure_ascii=False, indent=1))
            return
        for r in rows:
            self.stdout.write(f"[{r.status}] {r.scope:24} {r.parameter:28} {r.value}  ({r.rule}; {r.source})")
