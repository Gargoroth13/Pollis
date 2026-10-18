"""
Serviços do Inventário pessoal (design/05). Recusas são CÓDIGOS (`ActionResult`), como no resto do projeto.

PROTOCOLO DE TRAVAMENTO (um só; a ordem evita ciclo):
  1. as linhas de jogador (`players.Player`) envolvidas, em ordem crescente de pk: uma só (consumo, entrada/saída) ou as DUAS do
     envio (remetente e destinatário). Motivo real, visto em PostgreSQL: inserir movimento/envio que referencia o destinatário
     toma `FOR KEY SHARE` na linha dele (chave estrangeira), que conflita com o `FOR UPDATE` de quem a trava; com dois envios
     cruzados (A→B e B→A) cada um segurava a própria linha e pedia a do outro: deadlock. Travar as duas em ordem elimina o ciclo;
  2. as linhas de posse (`InventoryItem`) do par (jogador, produto) em ordem crescente de `player_id`;
  3. o registro monetário (contas em ordem crescente de id, `ledger`), só quando há taxa.
Quem compõe operações de outros sistemas (Varejo, Mercado) com o inventário deve seguir a mesma ordem, e travar TODOS os jogadores
que a operação referenciar (inclusive os que só recebem) antes de gravar qualquer linha que os referencie.

Nada aqui cria item, dinheiro ou regra do nada (CLAUDE.md §5, §12):
  - item só ENTRA por compra, produção ou recebimento e SAI por venda, consumo ou envio (`Operation`); `credit`/`debit` para
    outros sistemas só aceitam as operações que o design documenta (`EXTERNAL_CREDIT`/`EXTERNAL_DEBIT`);
  - compra não é consumo (05 §4): `credit(PURCHASE)` não aplica efeito algum;
  - o Correio sempre cobra a taxa (05 §11-14; não existe envio gratuito) e a cobrança move dinheiro existente
    (`MAIL_FEE`, jogador → União);
  - número não especificado pelo design NÃO é inventado: recusa `UNSPECIFIED_DESIGN_VALUE` (catálogo).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.db import IntegrityError, transaction

from catalog import services as catalog
from catalog.constants import QolEffect as CatalogQolEffect
from catalog.models import Product
from core import clock as game_clock
from core.breakdown import Calc, Explained
from ledger import services as ledger
from ledger.constants import Nature
from ledger.money import from_reais
from players import services as player_services
from players.balance import get_balance
from players.models import Player
from players.services import ActionResult, EffectSpec

from . import params
from .constants import (EXTERNAL_CREDIT, EXTERNAL_DEBIT, MAX_QUANTITY, Operation)
from .models import InventoryItem, InventoryMovement, Shipment

D = Decimal


def _refuse(code: str, **detail) -> ActionResult:
    return ActionResult(False, code, detail)


def _quantity_problem(quantity) -> Optional[ActionResult]:
    if isinstance(quantity, bool) or not isinstance(quantity, int) or not 0 < quantity <= MAX_QUANTITY:
        return _refuse("INVALID_QUANTITY", quantity=repr(quantity)[:40])
    return None


# --- leitura ------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ItemView:
    key: str
    name: str
    category: str                    # categoria do CATÁLOGO ("" = ainda não classificado); o inventário não cria categorias
    quantity: int
    is_consumable: bool
    is_permanent: bool


def quantity_of(player_id: int, product_key: str) -> int:
    value = InventoryItem.objects.filter(player_id=player_id, product__key=product_key).values_list("quantity", flat=True).first()
    return value or 0


def inventory_of(player_id: int) -> Dict[str, List[ItemView]]:
    """Itens do jogador agrupados pela categoria do catálogo (05 §3): categorias em ordem alfabética, produtos por chave."""
    rows = (InventoryItem.objects.filter(player_id=player_id).select_related("product")
            .order_by("product__category", "product__key"))
    grouped: Dict[str, List[ItemView]] = {}
    for item in rows:
        p = item.product
        grouped.setdefault(p.category, []).append(
            ItemView(p.key, p.name, p.category, item.quantity, p.is_consumable, p.is_permanent))
    return grouped


# --- movimentos (núcleo) ------------------------------------------------------------------------------------------------

def _next_key(prefix: str, player_id: int) -> str:
    """Chave determinística de um evento do jogador: serializada pela linha do jogador travada (ver protocolo)."""
    return f"{prefix}:{player_id}:{InventoryMovement.objects.filter(player_id=player_id).count() + 1}"


def _replay(key: str, player_id: int, product_id: int, delta: int, operation: Operation) -> Optional[ActionResult]:
    """A chave já foi usada? Mesmo conteúdo → repetição idempotente (nada muda); outro → IDEMPOTENCY_CONFLICT."""
    existing = InventoryMovement.objects.filter(key=key).first()
    if existing is None:
        return None
    same = (existing.player_id, existing.product_id, existing.delta, existing.operation) == (
        player_id, product_id, delta, operation.value)
    if not same:
        return _refuse("IDEMPOTENCY_CONFLICT", key=key)
    return ActionResult(True, "OK", {"already_applied": True, "movement": existing.pk, "quantity": existing.quantity_after})


def _locked_item(player_id: int, product_id: int) -> Optional[InventoryItem]:
    return InventoryItem.objects.select_for_update().filter(player_id=player_id, product_id=product_id).first()


def _apply(player_id: int, product: Product, delta: int, operation: Operation, *, origin: str, destination: str, key: str,
           reference_kind: str, reference_id, at: int, explained: Optional[Dict[str, Any]]) -> ActionResult:
    """Aplica UM movimento (entra +, sai −) sobre a posse, com a trilha. Deve rodar dentro de uma transação."""
    replay = _replay(key, player_id, product.pk, delta, operation)
    if replay is not None:
        return replay
    item = _locked_item(player_id, product.pk)
    have = item.quantity if item is not None else 0
    after = have + delta
    if after < 0:
        return _refuse("INSUFFICIENT_QUANTITY", have=have, required=-delta, product=product.key)
    try:
        with transaction.atomic():               # ponto de salvamento: uma corrida na criação não envenena a transação
            if item is None:
                item = InventoryItem.objects.create(player_id=player_id, product=product, quantity=after)
            elif after == 0:
                item.delete()
            else:
                item.quantity = after
                item.save(update_fields=["quantity"])
            movement = InventoryMovement.objects.create(
                player_id=player_id, product=product, delta=delta, quantity_after=after, operation=operation.value,
                origin=origin, destination=destination, key=key, reference_kind=reference_kind,
                reference_id=str(reference_id), at=at, explained=explained or {})
    except IntegrityError:
        # outra transação criou a posse (ou usou a chave) primeiro: relê sob bloqueio e decide de novo
        replay = _replay(key, player_id, product.pk, delta, operation)
        if replay is not None:
            return replay
        return _apply(player_id, product, delta, operation, origin=origin, destination=destination, key=key,
                      reference_kind=reference_kind, reference_id=reference_id, at=at, explained=explained)
    return ActionResult(True, "OK", {"movement": movement.pk, "quantity": after, "delta": delta, "product": product.key})


def _external(player_id: int, product_key: str, quantity: int, operation: Operation, allowed, *, origin: str, destination: str,
              key: str, reference_kind: str, reference_id, at: Optional[int], explained, sign: int) -> ActionResult:
    if operation not in allowed:
        return _refuse("OPERATION_NOT_ALLOWED", operation=getattr(operation, "value", str(operation)),
                       allowed=sorted(o.value for o in allowed))
    problem = _quantity_problem(quantity)
    if problem is not None:
        return problem
    if not (isinstance(origin, str) and origin and isinstance(destination, str) and destination
            and isinstance(key, str) and key and isinstance(reference_kind, str) and reference_kind
            and str(reference_id)):
        return _refuse("INVALID_PARAMS", why="origem, destino, chave e referência são obrigatórios")
    product = catalog.get_product(product_key)
    if product is None:
        return _refuse("UNKNOWN_PRODUCT", key=product_key)
    if not Player.objects.filter(pk=player_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=player_id)
    with transaction.atomic():
        Player.objects.select_for_update().get(pk=player_id)           # protocolo: jogador, depois a posse
        return _apply(player_id, product, sign * quantity, operation, origin=origin, destination=destination, key=key,
                      reference_kind=reference_kind, reference_id=reference_id,
                      at=game_clock.now() if at is None else at, explained=explained)


def credit(player_id: int, product_key: str, quantity: int, *, operation: Operation, origin: str, key: str,
           reference_kind: str, reference_id, at: Optional[int] = None, explained: Optional[Dict[str, Any]] = None
           ) -> ActionResult:
    """
    Entrada de itens por um sistema com origem documentada: `PURCHASE` (Varejo) ou `PRODUCTION` (empresa). Idempotente por
    `key`. NÃO aplica efeito do produto (05 §4) e NÃO move dinheiro: quem compra liga o pagamento (ledger) à entrada, na
    MESMA transação e na ordem do protocolo. Recusas: OPERATION_NOT_ALLOWED, INVALID_QUANTITY, INVALID_PARAMS,
    UNKNOWN_PRODUCT, PLAYER_NOT_FOUND, IDEMPOTENCY_CONFLICT.
    """
    return _external(player_id, product_key, quantity, operation, EXTERNAL_CREDIT, origin=origin, destination=f"player:{player_id}",
                     key=key, reference_kind=reference_kind, reference_id=reference_id, at=at, explained=explained, sign=1)


def debit(player_id: int, product_key: str, quantity: int, *, operation: Operation, destination: str, key: str,
          reference_kind: str, reference_id, at: Optional[int] = None, explained: Optional[Dict[str, Any]] = None
          ) -> ActionResult:
    """Saída de itens por um sistema com destino documentado: `SALE` (Mercado). Consumo e envio são ações do Inventário."""
    return _external(player_id, product_key, quantity, operation, EXTERNAL_DEBIT, origin=f"player:{player_id}",
                     destination=destination, key=key, reference_kind=reference_kind, reference_id=reference_id, at=at,
                     explained=explained, sign=-1)


# --- Consumir (05 §5-6; 04 §15-16) --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ConsumptionQuote:
    """O que consumir UMA unidade faz, calculado pela MESMA função que a execução usa (20: o detalhamento nasce da fórmula)."""
    product_key: str
    nutrition: Explained                    # ganho de Nutrição: valor do catálogo limitado ao espaço até o máximo
    qol_effect: Optional[EffectSpec]        # efeito temporário da categoria Comida (None = sem efeito)


def _sign(effect: CatalogQolEffect) -> int:
    return -1 if effect is CatalogQolEffect.DEBUFF else 1


def consumption_refusal(product_key: str) -> Optional[ActionResult]:
    """Recusa de CATÁLOGO: produto desconhecido, sem efeito de consumo definido (não é alimento) ou valor não especificado."""
    ready = catalog.check_consumption_ready(product_key)
    if ready.ok:
        return None
    if ready.code == "NOT_FOOD":
        return _refuse("NO_CONSUMPTION_EFFECT", key=product_key)     # o design só define efeito de consumo de alimentos
    return ready


def consumption_quote(player: Player, product_key: str, now: int) -> ConsumptionQuote:
    """`player` já processado até `now`. Pré-condição: `consumption_refusal(product_key)` é None."""
    food = catalog.food_of(product_key)
    bal = get_balance()
    room = max(D(0), bal.nutrition_max - player.nutrition)
    nutrition = Calc("food_nutrition", food.nutrition_amount).cap("nutrition_room", room).result(now)
    effect = None
    if food.qol_effect is not CatalogQolEffect.NO_EFFECT and food.qol_intensity > 0:
        effect = EffectSpec(f"food:{product_key}", _sign(food.qol_effect) * food.qol_intensity,
                            params.FOOD_EFFECT_DURATION_SECONDS)
    return ConsumptionQuote(product_key, nutrition, effect)


def consume(player_id: int, product_key: str) -> ActionResult:
    """
    Consome UMA unidade de um alimento do inventário: item → efeito → quantidade reduzida (05 §5-6). O efeito é o de
    `players.consume_food` (Nutrição + efeito temporário de Comida, que substitui o anterior, 04 §4.4); o mesmo serviço
    que o Auto-consumo usará (04 §16: "exatamente as mesmas regras do consumo manual").
    Recusas: PLAYER_NOT_FOUND, UNKNOWN_PRODUCT, NO_CONSUMPTION_EFFECT, UNSPECIFIED_DESIGN_VALUE, NOT_IN_INVENTORY.
    """
    refusal = consumption_refusal(product_key)
    if refusal is not None:
        return refusal
    product = catalog.get_product(product_key)
    if not Player.objects.filter(pk=player_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=player_id)
    with transaction.atomic():
        player = player_services.sync_player(player_id)                # trava o jogador e processa até agora
        now = game_clock.now()
        if quantity_of(player_id, product_key) < 1:
            return _refuse("NOT_IN_INVENTORY", key=product_key)
        quote = consumption_quote(player, product_key, now)
        before = player.nutrition
        moved = _apply(player_id, product, -1, Operation.CONSUMPTION, origin=f"player:{player_id}", destination="consumption",
                       key=_next_key("consume", player_id), reference_kind="consumption", reference_id=product_key, at=now,
                       explained={"nutrition_gain": quote.nutrition.to_dict()})
        if not moved.ok:
            return moved
        effect = player_services.consume_food(player_id, quote.nutrition.value, effect=quote.qol_effect)
        if not effect.ok:
            raise RuntimeError(f"consume_food recusou depois da validação: {effect.code}")
        applied = effect.detail["nutrition"] - before
        return ActionResult(True, "OK", {
            "product": product_key, "quantity": moved.detail["quantity"], "nutrition": effect.detail["nutrition"],
            "nutrition_gain": quote.nutrition, "nutrition_applied": applied,
            "qol_effect": None if quote.qol_effect is None else {
                "source": quote.qol_effect.source, "amount": quote.qol_effect.amount,
                "duration_seconds": quote.qol_effect.duration_seconds}})


# --- Correio (05 §11-14) ------------------------------------------------------------------------------------------------

def mail_fee(product_key: str, quantity: int) -> Tuple[Optional[Explained], Optional[ActionResult]]:
    """
    Taxa do envio: `MAX(taxa_mínima, valor_de_referência × percentual)` (05 §12), em centavos, arredondada UMA vez
    (`ROUND_HALF_EVEN`). O valor de referência é o `base_price` do catálogo × quantidade. Devolve `(Explained, None)` ou
    `(None, recusa)`: UNKNOWN_PRODUCT, INVALID_QUANTITY, UNSPECIFIED_DESIGN_VALUE (produto sem valor de referência: não
    existe envio gratuito, então a taxa não pode ser inventada).
    """
    problem = _quantity_problem(quantity)
    if problem is not None:
        return None, problem
    product = catalog.get_product(product_key)
    if product is None:
        return None, _refuse("UNKNOWN_PRODUCT", key=product_key)
    if product.base_price is None:
        return None, _refuse("UNSPECIFIED_DESIGN_VALUE", key=product_key, missing=["base_price"])
    reference = from_reais(product.base_price) * quantity
    calc = Calc("reference_value", reference).mul("mail_fee_rate", params.MAIL_FEE_RATE)
    calc.floor("mail_fee_min", params.MAIL_FEE_MIN_CENTS)
    return calc.result(game_clock.now()), None


def fee_cents(fee: Explained) -> int:
    """Centavos cobrados: o valor explicado arredondado uma única vez."""
    return int(fee.value.quantize(D(1), rounding=ROUND_HALF_EVEN))


def send_refusal(sender_id: int, recipient_id: int, product_key: str, quantity: int) -> Optional[ActionResult]:
    """Recusas que só LEEM: quantidade, destinatário, produto, valor de referência, posse e saldo para a taxa."""
    problem = _quantity_problem(quantity)
    if problem is not None:
        return problem
    if isinstance(recipient_id, bool) or not isinstance(recipient_id, int):
        return _refuse("INVALID_PARAMS", recipient=repr(recipient_id)[:40])
    if recipient_id == sender_id:
        return _refuse("SAME_PLAYER", player=sender_id)
    if not Player.objects.filter(pk=recipient_id).exists():
        return _refuse("RECIPIENT_NOT_FOUND", recipient=recipient_id)
    fee, refusal = mail_fee(product_key, quantity)
    if refusal is not None:
        return refusal
    have = quantity_of(sender_id, product_key)
    if have < quantity:
        return _refuse("INSUFFICIENT_QUANTITY", have=have, required=quantity, product=product_key)
    cents = fee_cents(fee)
    if cents > 0:
        funds = ledger.quote(ledger.player_account(sender_id).pk, cents)
        if not funds.ok:
            return _refuse("INSUFFICIENT_FUNDS", fee=cents, **{k: v for k, v in funds.detail.items() if k != "ok"})
    return None


def send_item(sender_id: int, recipient_id: int, product_key: str, quantity: int) -> ActionResult:
    """
    Envia `quantity` unidades pelo Correio, com taxa obrigatória cobrada do remetente (`MAIL_FEE`, jogador → União). Não
    existe envio gratuito, e o sistema não tenta distinguir presente de venda (05 §14). Atômico: sem taxa paga, nada se move.
    Recusas: INVALID_QUANTITY, INVALID_PARAMS, SAME_PLAYER, PLAYER_NOT_FOUND, RECIPIENT_NOT_FOUND, UNKNOWN_PRODUCT,
    UNSPECIFIED_DESIGN_VALUE, INSUFFICIENT_QUANTITY, INSUFFICIENT_FUNDS.
    """
    if not Player.objects.filter(pk=sender_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=sender_id)
    with transaction.atomic():
        ids = {sender_id} | ({recipient_id} if isinstance(recipient_id, int) and not isinstance(recipient_id, bool)
                             and -2 ** 63 <= recipient_id < 2 ** 63 else set())
        list(Player.objects.select_for_update().filter(pk__in=ids).order_by("pk").values_list("pk", flat=True))   # protocolo, 1
        return _send_locked(sender_id, recipient_id, product_key, quantity)


def _send_locked(sender_id: int, recipient_id: int, product_key: str, quantity: int) -> ActionResult:
    with player_services.locked_player(sender_id) as (_player, now, _bal):
        refusal = send_refusal(sender_id, recipient_id, product_key, quantity)
        if refusal is not None:
            return refusal
        product = catalog.get_product(product_key)
        fee, _ = mail_fee(product_key, quantity)
        cents = fee_cents(fee)
        # trava as posses do par (remetente, destinatário) em ordem crescente de player_id; relê a posse depois do bloqueio
        for pid in sorted((sender_id, recipient_id)):
            _locked_item(pid, product.pk)
        have = quantity_of(sender_id, product_key)
        if have < quantity:
            return _refuse("INSUFFICIENT_QUANTITY", have=have, required=quantity, product=product_key)
        sequence = Shipment.objects.filter(sender_id=sender_id).count() + 1
        ledger_key = ""
        if cents > 0:
            ledger_key = f"mail:{sender_id}:{sequence}"
            paid = ledger.transfer(
                ledger.player_account(sender_id).pk, ledger.union_account().pk, cents, Nature.MAIL_FEE, key=ledger_key,
                reference_kind="shipment", reference_id=f"{sender_id}:{sequence}", at=now, actor=f"player:{sender_id}",
                category="mail", operation="send_item",
                explained={"product": product_key, "quantity": quantity, "recipient": recipient_id, "fee": cents})
            if not paid.ok:
                return _refuse("INSUFFICIENT_FUNDS", fee=cents, **paid.detail)
        reference = from_reais(product.base_price) * quantity
        shipment = Shipment.objects.create(
            sender_id=sender_id, recipient_id=recipient_id, product=product, quantity=quantity, sequence=sequence,
            reference_value=reference, fee=cents, ledger_key=ledger_key, at=now, explained=fee.to_dict())
        ref = {"reference_kind": "shipment", "reference_id": shipment.pk, "at": now}
        out = _apply(sender_id, product, -quantity, Operation.TRANSFER_OUT, origin=f"player:{sender_id}",
                     destination=f"player:{recipient_id}", key=f"shipment:{shipment.pk}:out", explained=None, **ref)
        inn = _apply(recipient_id, product, quantity, Operation.TRANSFER_IN, origin=f"player:{sender_id}",
                     destination=f"player:{recipient_id}", key=f"shipment:{shipment.pk}:in", explained=None, **ref)
        if not (out.ok and inn.ok):
            raise RuntimeError(f"movimento do envio recusado depois da validação: {out.code}/{inn.code}")
        return ActionResult(True, "OK", {
            "shipment": shipment.pk, "product": product_key, "quantity": quantity, "recipient": recipient_id,
            "fee": cents, "fee_explained": fee, "reference_value": reference, "sender_quantity": out.detail["quantity"],
            "recipient_quantity": inn.detail["quantity"]})
