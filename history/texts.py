"""
Modelos de texto das notícias (design/12 §12.3): "manchete + contexto curto + dados relevantes", com VARIAÇÕES para não repetir sempre a
mesma frase. A descrição informa o fato SEM inventar motivos que o sistema não conhece. Funções puras: a variação escolhida é
determinística (hash da semente), então o mesmo acontecimento sempre gera o mesmo texto.

Campos entram por `str.format`; faltar um campo é erro (nunca texto pela metade). O artigo de nomes de produto não é usado porque o
catálogo não registra gênero (lacuna H4 de design/12a): "de {product}" serve a todos.
"""
from __future__ import annotations

import hashlib
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Mapping, Tuple

Variant = Tuple[str, str]            # (manchete, texto)

_TEMPLATES: Dict[str, List[Variant]] = {}


class TemplateError(Exception):
    pass


def register(key: str, variants: List[Variant]) -> None:
    if key in _TEMPLATES or not variants:
        raise ValueError(f"modelo duplicado ou vazio: {key}")
    _TEMPLATES[key] = list(variants)


def keys() -> List[str]:
    return sorted(_TEMPLATES)


def variant_count(key: str) -> int:
    return len(_TEMPLATES[key])


def pick_variant(key: str, seed: str) -> int:
    """Variação determinística: mesma semente, mesma variação; sementes diferentes espalham as variações."""
    n = len(_TEMPLATES[key])
    return int(hashlib.sha256(f"{key}|{seed}".encode()).hexdigest()[:8], 16) % n


def render(key: str, data: Mapping[str, object], seed: str) -> Tuple[int, str, str]:
    """(variação, manchete, texto). Erro se o modelo não existe ou falta algum campo."""
    if key not in _TEMPLATES:
        raise TemplateError(f"modelo inexistente: {key}")
    index = pick_variant(key, seed)
    headline, body = _TEMPLATES[key][index]
    try:
        return index, headline.format(**data), body.format(**data)
    except KeyError as exc:
        raise TemplateError(f"{key}: falta o campo {exc.args[0]!r}") from exc


def fmt_pct(value: Decimal) -> str:
    """Porcentagem em pt-BR com no máximo 1 casa: 8 → '8', 53.4 → '53,4' (arredondamento comercial)."""
    q = Decimal(value).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    text = f"{q:f}"
    if text.endswith(".0"):
        text = text[:-2]
    return text.replace(".", ",")


COMPANY_TYPE_PHRASE = {          # "primeira empresa {…}" (12.5): gramática por tipo
    "retail": "de Varejo", "services": "de Serviços", "matrix": "Matriz", "industrial": "Industrial",
    "construction": "Construtora", "financial": "Financeira",
}

OFFICE_NAME = {"president": "Presidente", "governor": "Governador", "mayor": "Prefeito", "chamber": "Câmara"}
ELECTION_PHRASE = {"president": "presidencial", "governor": "para Governador", "mayor": "para Prefeito", "chamber": "da Câmara"}

# --- economia (12.4) ---------------------------------------------------------------------------------------------------------------------------
register("economy.price_up", [
    ("Preço médio de {product} sobe {pct}%", "O preço médio nacional de {product} aumentou {pct}% nos últimos 7 dias."),
    ("Alta de {pct}% no preço médio de {product}", "Em comparação com os 7 dias anteriores, o preço médio de {product} subiu {pct}%."),
    ("{product} fica mais caro: alta de {pct}%", "A média de preços de {product} nos últimos 7 dias está {pct}% acima da semana anterior."),
])
register("economy.price_down", [
    ("Preço médio de {product} cai {pct}%", "O preço médio nacional de {product} diminuiu {pct}% nos últimos 7 dias."),
    ("Queda de {pct}% no preço médio de {product}", "Em comparação com os 7 dias anteriores, o preço médio de {product} recuou {pct}%."),
    ("{product} fica mais barato: queda de {pct}%", "A média de preços de {product} nos últimos 7 dias está {pct}% abaixo da semana anterior."),
])
# --- empresas (12.5) ---------------------------------------------------------------------------------------------------------------------------
register("milestone.first_company", [
    ("Nova Polis inaugura sua primeira empresa {type_phrase}", "A {company} é a primeira empresa {type_phrase} fundada em Nova Polis."),
    ("Primeira empresa {type_phrase} de Nova Polis", "A {company} abriu as portas e se tornou a primeira empresa {type_phrase} da cidade."),
])
register("company.bankruptcy", [
    ("Empresa {company} declara falência!", "A {company}, de {stars}★, encerrou suas operações após entrar em processo de falência."),
    ("{company} entra em falência", "A empresa {company}, de {stars}★, encerrou suas atividades ao falir."),
])
# --- política (12.6) ---------------------------------------------------------------------------------------------------------------------------
register("politics.election_winner", [
    ("Novo {office} eleito{where}", "{winner} venceu a eleição com {pct}% dos votos."),
    ("{winner} é eleito {office}{where}", "Com {pct}% dos votos, {winner} venceu a disputa."),
])
register("politics.chamber_elected", [
    ("Nova Câmara eleita", "A eleição da Câmara foi concluída e {seats} Deputados tomam posse."),
])
register("milestone.first_election", [
    ("Primeira eleição {office_phrase} concluída", "Nova Polis realiza a primeira eleição {office_phrase} de sua história."),
])
register("politics.government_change", [
    ("Novo Presidente assume o cargo após deposição", "{new} assume a Presidência depois que {deposed} foi deposto."),
    ("Presidente deposto", "{deposed} deixa a Presidência; {new} assume o cargo."),
])
register("politics.law_approved", [
    ("Câmara aprova {what} {law}", "A proposta recebeu {yes} votos favoráveis entre {seats} cadeiras (mínimo exigido: {required})."),
    ("{law}: Câmara aprova {what_short}", "Foram {yes} votos a favor entre {seats} cadeiras; eram necessários {required}."),
])
register("politics.law_vetoed", [
    ("Presidente veta {what} {law}", "A proposta aprovada pela Câmara foi vetada pelo Presidente."),
    ("Veto presidencial atinge {law}", "O Presidente vetou {what_the} aprovada pela Câmara."),
])
register("politics.veto_overridden", [
    ("Câmara derruba veto presidencial a {law}", "A Câmara reuniu {yes} votos entre {seats} cadeiras (mínimo exigido: {required}) e derrubou o veto."),
    ("Veto derrubado: {law} segue para vigor", "Com {yes} votos de {seats} cadeiras (mínimo exigido: {required}), a Câmara derrubou o veto."),
])
register("politics.law_in_force", [
    ("{law}: {what_short} entra em vigor", "{in_force_text}"),
    ("Entra em vigor a {what_short} de {law}", "{in_force_text}"),
])
# --- conflitos (12.7) --------------------------------------------------------------------------------------------------------------------------
register("conflict.started", [
    ("{faction} inicia ação contra {target}", "{faction} deu início a uma ação contra {target}."),
])
register("conflict.won", [
    ("{faction} vence confronto contra {target}", "A ação de {faction} contra {target} terminou com vitória de {faction}."),
])
register("conflict.lost", [
    ("{faction} é derrotada por {target}", "A ação de {faction} contra {target} terminou com derrota de {faction}."),
])
