"""
Parâmetros do motor de contratos. O `18` (FINAL) define a estrutura e não fixa números; o que está aqui está marcado e auditável.
"""
from __future__ import annotations

from decimal import Decimal
from typing import List

from companies.params import ProvisionalRow

# 11 §11.1: imposto sobre vendas, federal, padrão 5% do valor de cada venda, até o sistema de leis existir. Retido do valor pago
# pelo comprador (`ledger.post_taxed_payment`): o vendedor recebe o líquido. A decisão SALE x TAX_SALES do Mercado é lacuna 5 da 17a.
SALES_TAX_RATE = Decimal("0.05")

# 18.7/18.8: "dentro dos limites permitidos pelo tipo". [PROV]: a multa nunca passa do valor total do objeto do contrato
# (fornecimento: ocorrências × quantidade × preço; empréstimo: principal).
PENALTY_MAX_IS_CONTRACT_VALUE = True

# Empréstimo: taxa de juros total sobre o principal, simples (não composta), entre 0 e 100% [PROV: o 18 só dá o exemplo "2% de juros"].
MAX_INTEREST_RATE = Decimal("1")

SOURCE = "18 FINAL; valores [PROV]"


def provisional_table() -> List[ProvisionalRow]:
    return [
        ProvisionalRow("contracts", "sales_tax_rate", str(SALES_TAX_RATE),
                       "imposto sobre vendas dos pagamentos de fornecimento até o sistema de leis existir", "11 §11.1 padrão"),
        ProvisionalRow("contracts", "penalty_max", "valor total do objeto do contrato",
                       "limite da multa de quebra (18.8 'dentro dos limites do tipo')", SOURCE),
        ProvisionalRow("contracts", "max_interest_rate", str(MAX_INTEREST_RATE),
                       "juros totais simples do empréstimo (18.2 só dá o exemplo de 2%)", SOURCE),
        ProvisionalRow("contracts", "max_occurrences", "1000", "limite técnico de ocorrências por contrato", SOURCE),
        ProvisionalRow("contracts", "monthly_period", "mês de calendário do jogo",
                       "dia do mês da âncora, limitado ao último dia do mês (18.5: 'primeiro dia de cada mês')", SOURCE),
    ]
