"""
Vocabulário do Inventário (design/05). Nenhum valor de balanceamento vive aqui: os números `[PROV]` estão em `params.py`.
"""
import enum


class Operation(str, enum.Enum):
    """Tipo da operação que altera a posse (05 §19): compra, consumo, transferência, venda, recebimento, produção."""
    PURCHASE = "purchase"            # entra: compra (Varejo, P1.04/P1.05)
    PRODUCTION = "production"        # entra: produção empresarial, quando aplicável (P1.04)
    TRANSFER_IN = "transfer_in"      # entra: recebimento de um envio pelo Correio
    SALE = "sale"                    # sai: venda (Mercado de Jogadores, P1.05)
    CONSUMPTION = "consumption"      # sai: consumo (alimento, 05 §6)
    TRANSFER_OUT = "transfer_out"    # sai: envio pelo Correio


CREDIT_OPERATIONS = frozenset({Operation.PURCHASE, Operation.PRODUCTION, Operation.TRANSFER_IN})
DEBIT_OPERATIONS = frozenset({Operation.SALE, Operation.CONSUMPTION, Operation.TRANSFER_OUT})
# O que OUTROS sistemas podem pedir por `credit`/`debit`. Recebimento, consumo e envio só existem dentro das ações do próprio
# Inventário (Correio e Consumir): nenhum item nasce ou some por um nome de operação que o design não documenta.
EXTERNAL_CREDIT = frozenset({Operation.PURCHASE, Operation.PRODUCTION})
EXTERNAL_DEBIT = frozenset({Operation.SALE})

MAX_QUANTITY = 10 ** 12
