from decimal import Decimal

from django.core.management.base import BaseCommand

from empresas.models import Produto, Receita, TerrenoDeMatriz, TipoDeIndustria


class Command(BaseCommand):
    help = "Popula um recorte pequeno do catálogo de produtos (idempotente). Catálogo completo (~40 itens) vem na Fase 2."

    def handle(self, *args, **options):
        def materia_prima(nome, terreno, preco_base):
            obj, _ = Produto.objects.get_or_create(
                nome=nome,
                defaults={"eh_materia_prima": True, "terreno_produtor": terreno, "preco_base": Decimal(preco_base)},
            )
            return obj

        def manufaturado(nome, tipo_industria, preco_base):
            obj, _ = Produto.objects.get_or_create(
                nome=nome,
                defaults={
                    "eh_materia_prima": False,
                    "tipo_industria_produtor": tipo_industria,
                    "preco_base": Decimal(preco_base),
                },
            )
            return obj

        # Recorte pequeno do catálogo completo do DESIGN.md (seção 2.3) —
        # só o suficiente pra validar que a classificação por terreno/tipo
        # de indústria funciona de ponta a ponta. O catálogo com as ~40
        # receitas entra na Fase 2.
        madeira = materia_prima("Madeira", TerrenoDeMatriz.EXTRATIVISMO, "5.00")
        ferro = materia_prima("Ferro", TerrenoDeMatriz.MINERACAO, "6.00")
        carvao = materia_prima("Carvão", TerrenoDeMatriz.MINERACAO, "4.00")
        la = materia_prima("Lã", TerrenoDeMatriz.AGROPECUARIA, "5.00")

        tabuas = manufaturado("Tábuas", TipoDeIndustria.PRODUCAO, "9.00")
        aco = manufaturado("Aço", TipoDeIndustria.PRODUCAO, "14.00")
        roupas = manufaturado("Roupas", TipoDeIndustria.BENS_DE_CONSUMO, "10.00")

        receitas = [
            (tabuas, madeira, 1, 2),  # Madeira = Tábuas (1★)
            (aco, ferro, 1, 1),        # Ferro + Carvão = Aço (2★) — 2 receitas pro mesmo produto final
            (aco, carvao, 1, 1),
            (roupas, la, 2, 1),        # Lã = Roupas (1★)
        ]
        for produto_final, materia, necessaria, produzida in receitas:
            Receita.objects.get_or_create(
                produto_final=produto_final,
                materia_prima=materia,
                defaults={"quantidade_necessaria": necessaria, "quantidade_produzida": produzida},
            )

        self.stdout.write(self.style.SUCCESS(
            "Pronto: 4 matérias-primas, 3 manufaturados e 4 receitas cadastradas (recorte da Fase 1)."
        ))
