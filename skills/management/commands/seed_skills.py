from django.core.management.base import BaseCommand

from skills.models import CategoriaDeHabilidade

CATEGORIAS = [
    ("Indústria", "Fábricas, produção e manufatura"),
    ("Comércio", "Vendas, varejo e negociação"),
    ("Tecnologia", "Software, dados e infraestrutura digital"),
    ("Saúde", "Atendimento médico e cuidado da população"),
    ("Educação", "Ensino, pesquisa e formação"),
    ("Jurídico", "Direito, contratos e representação legal"),
    ("Serviços", "Atendimento, logística e serviços gerais"),
    ("Agropecuária", "Produção agrícola e pecuária"),
]


class Command(BaseCommand):
    help = "Popula as categorias de habilidade iniciais (idempotente)."

    def handle(self, *args, **options):
        criados = 0
        for nome, descricao in CATEGORIAS:
            _, foi_criado = CategoriaDeHabilidade.objects.get_or_create(
                nome=nome, defaults={"descricao": descricao}
            )
            criados += int(foi_criado)

        self.stdout.write(self.style.SUCCESS(
            f"Pronto: {len(CATEGORIAS)} categorias de habilidade ({criados} criadas agora)."
        ))
