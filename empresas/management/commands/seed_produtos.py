from decimal import Decimal

from django.core.management.base import BaseCommand

from empresas.models import Produto, Receita, TerrenoDeMatriz, TipoDeIndustria


class Command(BaseCommand):
    help = "Popula o catálogo completo de produtos e receitas da cadeia produtiva (idempotente)."

    def handle(self, *args, **options):
        produtos_por_nome = {}

        def materia_prima(nome, terreno, preco_base):
            obj, _ = Produto.objects.update_or_create(
                nome=nome,
                defaults={"eh_materia_prima": True, "terreno_produtor": terreno, "preco_base": Decimal(preco_base)},
            )
            produtos_por_nome[nome] = obj
            return obj

        def manufaturado(nome, tipo_industria, preco_base):
            obj, _ = Produto.objects.update_or_create(
                nome=nome,
                defaults={
                    "eh_materia_prima": False,
                    "tipo_industria_produtor": tipo_industria,
                    "preco_base": Decimal(preco_base),
                },
            )
            produtos_por_nome[nome] = obj
            return obj

        # ==================== MATÉRIAS-PRIMAS ====================
        # Nota: Petróleo aparece em Extrativismo E Mineração no DESIGN.md
        # (seção 2.2) — duas rotas pro mesmo insumo. Nosso modelo hoje só
        # aceita UM terreno_produtor por Produto, então ficou com
        # Extrativismo por ora. Dar suporte a dupla origem é melhoria futura.
        AGROPECUARIA = TerrenoDeMatriz.AGROPECUARIA
        EXTRATIVISMO = TerrenoDeMatriz.EXTRATIVISMO
        MINERACAO = TerrenoDeMatriz.MINERACAO

        materias_primas = [
            # Agropecuária
            ("Trigo", AGROPECUARIA, "3.00"),
            ("Leite", AGROPECUARIA, "4.00"),
            ("Cana", AGROPECUARIA, "3.00"),
            ("Grão de Café", AGROPECUARIA, "6.00"),
            ("Cacau", AGROPECUARIA, "7.00"),
            ("Carne", AGROPECUARIA, "8.00"),
            ("Ovos", AGROPECUARIA, "3.00"),
            ("Couro", AGROPECUARIA, "6.00"),
            ("Lã", AGROPECUARIA, "5.00"),
            ("Fruta", AGROPECUARIA, "3.00"),
            # Extrativismo
            ("Madeira", EXTRATIVISMO, "4.00"),
            ("Resina", EXTRATIVISMO, "6.00"),
            ("Látex", EXTRATIVISMO, "6.00"),
            ("Óleo natural", EXTRATIVISMO, "8.00"),
            ("Ervas", EXTRATIVISMO, "5.00"),
            ("Areia", EXTRATIVISMO, "2.00"),
            ("Pedra", EXTRATIVISMO, "2.00"),
            ("Químicos", EXTRATIVISMO, "9.00"),
            ("Petróleo", EXTRATIVISMO, "12.00"),
            ("Borracha", EXTRATIVISMO, "7.00"),
            # Mineração
            ("Ferro", MINERACAO, "6.00"),
            ("Cobre", MINERACAO, "7.00"),
            ("Sílica", MINERACAO, "5.00"),
            ("Carvão", MINERACAO, "4.00"),
            ("Sal", MINERACAO, "2.00"),
            ("Lítio", MINERACAO, "18.00"),
            ("Ouro", MINERACAO, "35.00"),
            ("Prata", MINERACAO, "20.00"),
            ("Diamante", MINERACAO, "60.00"),
        ]
        for nome, terreno, preco in materias_primas:
            materia_prima(nome, terreno, preco)

        # ==================== MANUFATURADOS ====================
        PRODUCAO = TipoDeIndustria.PRODUCAO
        ALIMENTICIA = TipoDeIndustria.ALIMENTICIA
        BENS_DE_CONSUMO = TipoDeIndustria.BENS_DE_CONSUMO
        TECNOLOGICA = TipoDeIndustria.TECNOLOGICA

        # (nome, tipo_industria, preco_base)
        manufaturados_lista = [
            # Produção
            ("Cimento", PRODUCAO, "10.00"),
            ("Aço", PRODUCAO, "16.00"),
            ("Tábuas", PRODUCAO, "9.00"),
            ("Vidro", PRODUCAO, "12.00"),
            ("Materiais de Construção", PRODUCAO, "45.00"),
            ("Plástico", PRODUCAO, "14.00"),
            ("Combustível", PRODUCAO, "20.00"),
            ("Fertilizante", PRODUCAO, "15.00"),
            ("Fios de cobre", PRODUCAO, "10.00"),
            ("EPIs", PRODUCAO, "35.00"),
            ("Materiais escolares", PRODUCAO, "30.00"),
            ("Materiais hospitalares", PRODUCAO, "50.00"),
            # Alimentícia
            ("Farinha", ALIMENTICIA, "6.00"),
            ("Açúcar", ALIMENTICIA, "5.00"),
            ("Queijo", ALIMENTICIA, "9.00"),
            ("Manteiga", ALIMENTICIA, "10.00"),
            ("Café em pó", ALIMENTICIA, "12.00"),
            ("Manteiga de cacau", ALIMENTICIA, "18.00"),
            ("Carne processada", ALIMENTICIA, "15.00"),
            # Bens de consumo
            ("Roupas", BENS_DE_CONSUMO, "12.00"),
            ("Móveis", BENS_DE_CONSUMO, "40.00"),
            ("Papel", BENS_DE_CONSUMO, "8.00"),
            ("Caneta", BENS_DE_CONSUMO, "5.00"),
            ("Calçado", BENS_DE_CONSUMO, "14.00"),
            ("Uniforme", BENS_DE_CONSUMO, "25.00"),
            ("Pão", BENS_DE_CONSUMO, "4.00"),
            ("Chocolate", BENS_DE_CONSUMO, "15.00"),
            ("Macarrão", BENS_DE_CONSUMO, "8.00"),
            ("Hambúrguer", BENS_DE_CONSUMO, "18.00"),
            ("Suco", BENS_DE_CONSUMO, "5.00"),
            ("Sorvete", BENS_DE_CONSUMO, "10.00"),
            ("Carne de Sol", BENS_DE_CONSUMO, "12.00"),
            ("Refrigerante", BENS_DE_CONSUMO, "6.00"),
            ("Carro", BENS_DE_CONSUMO, "5000.00"),
            # Tecnológica
            ("Componentes eletrônicos", TECNOLOGICA, "20.00"),
            ("Bateria", TECNOLOGICA, "30.00"),
            ("Celular", TECNOLOGICA, "150.00"),
            ("Computador", TECNOLOGICA, "250.00"),
        ]
        for nome, tipo_industria, preco in manufaturados_lista:
            manufaturado(nome, tipo_industria, preco)

        # Efeitos de consumo (nutrição / QoL) — só os alimentos têm isso.
        # Escala aproximada: nutrição 0-100 (100 = uma refeição completa),
        # efeito_qol é o delta aplicado na hora de comer (pode ser negativo).
        # Valores batem com a tabela qualitativa do DESIGN.md seção 2.3.
        efeitos_alimentares = {
            "Pão": {"nutricao": 20, "efeito_qol": "0.00"},
            "Chocolate": {"nutricao": 10, "efeito_qol": "0.05"},
            "Macarrão": {"nutricao": 60, "efeito_qol": "0.00"},
            "Hambúrguer": {"nutricao": 40, "efeito_qol": "0.05"},
            "Suco": {"nutricao": 5, "efeito_qol": "0.05"},
            "Sorvete": {"nutricao": 0, "efeito_qol": "0.10"},
            "Carne de Sol": {"nutricao": 40, "efeito_qol": "-0.05"},
            "Refrigerante": {"nutricao": 0, "efeito_qol": "0.10"},
        }
        for nome, efeito in efeitos_alimentares.items():
            Produto.objects.filter(nome=nome).update(
                nutricao=efeito["nutricao"], efeito_qol=Decimal(efeito["efeito_qol"])
            )

        # ==================== RECEITAS ====================
        # (produto_final, [(ingrediente, quantidade_necessaria), ...], quantidade_produzida, estrela_minima)
        receitas_lista = [
            # Produção
            ("Cimento", [("Pedra", 1), ("Areia", 1)], 1, 1),
            ("Aço", [("Ferro", 1), ("Carvão", 1)], 1, 2),
            ("Tábuas", [("Madeira", 1)], 1, 1),
            ("Vidro", [("Areia", 1)], 1, 2),
            ("Materiais de Construção", [("Cimento", 1), ("Aço", 1), ("Madeira", 1), ("Vidro", 1)], 1, 3),
            ("Plástico", [("Petróleo", 1)], 1, 2),
            ("Combustível", [("Petróleo", 1)], 1, 3),
            ("Fertilizante", [("Químicos", 1)], 1, 2),
            ("Fios de cobre", [("Cobre", 1)], 1, 1),
            ("EPIs", [("Borracha", 1), ("Plástico", 1), ("Aço", 1), ("Roupas", 1), ("Calçado", 1)], 1, 3),
            ("Materiais escolares", [("Borracha", 1), ("Caneta", 1), ("Móveis", 1), ("Papel", 1)], 1, 3),
            ("Materiais hospitalares", [("Químicos", 1), ("Componentes eletrônicos", 1), ("Plástico", 1), ("Ervas", 1)], 1, 4),
            # Alimentícia
            ("Farinha", [("Trigo", 1)], 1, 1),
            ("Açúcar", [("Cana", 1)], 1, 1),
            ("Queijo", [("Leite", 1)], 1, 1),
            ("Manteiga", [("Leite", 1)], 1, 2),
            ("Café em pó", [("Grão de Café", 1)], 1, 2),
            ("Manteiga de cacau", [("Cacau", 1)], 1, 3),
            ("Carne processada", [("Carne", 1)], 1, 2),
            # Bens de consumo
            ("Roupas", [("Lã", 1)], 1, 1),
            ("Móveis", [("Tábuas", 1), ("Aço", 1)], 1, 3),
            ("Papel", [("Madeira", 1), ("Sal", 1)], 1, 2),
            ("Caneta", [("Aço", 1), ("Químicos", 1)], 1, 1),
            ("Calçado", [("Couro", 1)], 1, 1),
            ("Uniforme", [("Roupas", 1), ("Calçado", 1)], 1, 3),
            ("Pão", [("Farinha", 1)], 1, 1),
            ("Chocolate", [("Manteiga de cacau", 1), ("Açúcar", 1), ("Leite", 1)], 1, 4),
            ("Macarrão", [("Queijo", 1), ("Farinha", 1), ("Ovos", 1)], 1, 3),
            ("Hambúrguer", [("Queijo", 1), ("Carne processada", 1), ("Pão", 1)], 1, 4),
            ("Suco", [("Fruta", 1), ("Açúcar", 1)], 1, 2),
            ("Sorvete", [("Leite", 1), ("Açúcar", 1), ("Fruta", 1)], 1, 3),
            ("Carne de Sol", [("Carne", 1), ("Sal", 1)], 1, 1),
            ("Refrigerante", [("Açúcar", 1), ("Suco", 1), ("Químicos", 1)], 1, 2),
            ("Carro", [("Aço", 1), ("Plástico", 1), ("Bateria", 1), ("Borracha", 1), ("Químicos", 1)], 1, 5),
            # Tecnológica
            ("Componentes eletrônicos", [("Fios de cobre", 1), ("Sílica", 1), ("Ouro", 1)], 1, 1),
            ("Bateria", [("Cobre", 1), ("Lítio", 1), ("Químicos", 1)], 1, 2),
            ("Celular", [("Componentes eletrônicos", 1), ("Plástico", 1), ("Bateria", 1)], 1, 3),
            ("Computador", [("Componentes eletrônicos", 1), ("Plástico", 1), ("Aço", 1), ("Químicos", 1)], 1, 4),
        ]

        total_receitas = 0
        for nome_final, ingredientes, quantidade_produzida, estrela_minima in receitas_lista:
            produto_final = produtos_por_nome[nome_final]
            for nome_ingrediente, quantidade_necessaria in ingredientes:
                ingrediente = produtos_por_nome[nome_ingrediente]
                Receita.objects.update_or_create(
                    produto_final=produto_final,
                    ingrediente=ingrediente,
                    defaults={
                        "quantidade_necessaria": quantidade_necessaria,
                        "quantidade_produzida": quantidade_produzida,
                        "estrela_minima": estrela_minima,
                    },
                )
                total_receitas += 1

        self.stdout.write(self.style.SUCCESS(
            f"Pronto: {len(materias_primas)} matérias-primas, {len(manufaturados_lista)} "
            f"manufaturados e {total_receitas} linhas de receita cadastradas."
        ))
