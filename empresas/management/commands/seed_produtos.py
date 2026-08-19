from decimal import Decimal

from django.core.management.base import BaseCommand

from empresas.models import Produto, Receita
from skills.models import CategoriaDeHabilidade


class Command(BaseCommand):
    help = "Popula o catálogo de produtos e as receitas da cadeia produtiva (idempotente)."

    def handle(self, *args, **options):
        agropecuaria = CategoriaDeHabilidade.objects.get(nome="Agropecuária")
        industria = CategoriaDeHabilidade.objects.get(nome="Indústria")

        def produto(nome, eh_materia_prima, setor, preco_base):
            obj, _ = Produto.objects.get_or_create(
                nome=nome,
                defaults={"eh_materia_prima": eh_materia_prima, "setor": setor, "preco_base": Decimal(preco_base)},
            )
            return obj

        # Matérias-primas: o que empresas do tipo Matriz produzem do zero.
        madeira = produto("Madeira", True, agropecuaria, "5.00")
        algodao = produto("Algodão", True, agropecuaria, "4.00")
        minerio = produto("Minério de Ferro", True, industria, "8.00")

        # Manufaturados: o que empresas do tipo Industrial fabricam a partir
        # das matérias-primas acima, comprando-as de uma Matriz.
        papel = produto("Papel", False, industria, "12.00")
        tecido = produto("Tecido", False, industria, "15.00")
        caneta = produto("Caneta", False, industria, "6.00")

        receitas = [
            (papel, madeira, 2, 3),
            (tecido, algodao, 2, 2),
            (caneta, minerio, 1, 4),
        ]
        for produto_final, materia_prima, necessaria, produzida in receitas:
            Receita.objects.get_or_create(
                produto_final=produto_final,
                materia_prima=materia_prima,
                defaults={"quantidade_necessaria": necessaria, "quantidade_produzida": produzida},
            )

        self.stdout.write(self.style.SUCCESS(
            "Pronto: 3 matérias-primas, 3 manufaturados e 3 receitas cadastradas."
        ))
