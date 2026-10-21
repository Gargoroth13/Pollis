"""
Permissões de compra (design/02 §4): derivadas das receitas e dos usos do catálogo, SEM lista paralela.

Uma empresa só compra um produto quando ele é uma ENTRADA VÁLIDA para uma receita ou operação disponível para ELA:
  - produtora (Matriz/Industrial): o produto é insumo de uma receita que a empresa pode produzir (tipo, estrela, receita pronta);
  - Varejo: a operação do Varejo é revender ao jogador, então só compra o que o catálogo declara com o canal `retail_sale`;
  - demais tipos (Serviços, Construtora, Financeira): ainda sem operação que consuma produtos definida no design → sem uso válido
    (a Construtora não consome materiais na obra; 02 §10 — consumo operacional — é limitação conhecida).
E o produto circula entre empresas só se o catálogo declara o canal `inter_company` (Q8: nenhum canal é inferido).
A venda entre empresas depende do comprador ter uso válido: `purchase_refusal(comprador, produto)` é a pergunta que o mercado (P1.05) faz.
"""
from __future__ import annotations

from typing import Any, Optional

from catalog import services as catalog
from catalog.constants import Channel
from players.services import ActionResult

from . import production
from .constants import CompanyType
from .models import Company


def _refuse(code: str, **detail) -> ActionResult:
    return ActionResult(False, code, detail)


def purchase_refusal(company_id: Any, product_key: Any) -> Optional[ActionResult]:
    """A empresa pode comprar este produto? None = sim. Só LÊ."""
    if not isinstance(product_key, str) or catalog.get_product(product_key) is None:
        return _refuse("UNKNOWN_PRODUCT", key=repr(product_key)[:40])
    company = Company.objects.filter(pk=company_id).first() if isinstance(company_id, int) and not isinstance(company_id, bool) else None
    if company is None:
        return _refuse("COMPANY_NOT_FOUND", company=repr(company_id)[:40])
    if not catalog.has_channel(product_key, Channel.INTER_COMPANY):
        return _refuse("PRODUCT_NOT_TRADABLE_BETWEEN_COMPANIES", product=product_key)
    ctype = CompanyType(company.type)
    if ctype is CompanyType.RETAIL:
        if not catalog.has_channel(product_key, Channel.RETAIL_SALE):
            return _refuse("NO_VALID_USE", product=product_key, company_type=company.type, why="o Varejo só compra o que revende (canal retail_sale)")
        return None
    if ctype in (CompanyType.MATRIX, CompanyType.INDUSTRIAL):
        for target in catalog.consumers_of(product_key):
            if production._eligible(company, target) is None:
                return None
        return _refuse("NO_VALID_USE", product=product_key, company_type=company.type,
                       why="não é insumo de nenhuma receita que esta empresa possa produzir (tipo, estrela, receita pronta)")
    return _refuse("NO_VALID_USE", product=product_key, company_type=company.type, why="o tipo ainda não tem operação que consuma produtos")
