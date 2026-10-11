from django.core.management.base import BaseCommand, CommandError

from catalog.loader import CatalogDefinitionError, sync_catalog


class Command(BaseCommand):
    help = "Carrega (idempotente) o catálogo de Produtos e Receitas transcrito do design/22."

    def handle(self, *args, **opts):
        try:
            result = sync_catalog()
        except CatalogDefinitionError as e:
            for f in e.report.errors[:50]:
                self.stdout.write(f"  {f.code}: {f.subject} {f.detail}")
            raise CommandError(str(e))
        self.stdout.write(f"criados={result.created} atualizados={result.updated} inalterados={result.unchanged}")
        self.stdout.write(f"pendências de design: {len(result.report.pending)} (rode `check_catalog` para ver)")
