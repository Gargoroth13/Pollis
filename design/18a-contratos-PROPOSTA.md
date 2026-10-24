# 18a — Contratos: o que foi implementado e o que depende de decisão (proposta)

> **Status:** PROPOSTA — **decisões 1–11 respondidas pelo Game Director em 2026-10-24** (seção 5); o que não está na seção 5 segue provisório
>
> O `18` está FINAL — BOT TEST e define a **estrutura** (partes, aceite, execução automática, inadimplência, quebra, multa, histórico),
> mas deixa em aberto detalhes necessários para executar de verdade. Cada lacuna abaixo foi preenchida com a **menor solução
> técnica possível**, marcada `[PROV]` em `contracts/params.py` ou descrita aqui; nenhuma mecânica nova foi criada (CLAUDE.md §13).

## 1. Etapas de P1.08

| Etapa | Conteúdo | Depende de |
|---|---|---|
| **P1.08a** (esta) | Motor (proposta, aceite, agenda, execução diária idempotente, inadimplência, multa, quebra, histórico imutável, auditoria, ações no Action Registry) + tipos **Fornecimento** e **Empréstimo** | — |
| P1.07 | Tipo **Aluguel** (handler `register_type`) e contratos de obra da Construtora | `10` |
| P1.09 | Tipo **Governamental** (pagamento e comprometimento pelo orçamento) | `09` |
| P1.17 | Fluxos A e B de `18.14` (milícia/Exército) reutilizando o motor | `19` |

O motor não conhece os tipos: cada um é um *handler* registrado (`contracts.handlers.register_type`). Um tipo de teste (aluguel
empresa → jogador) prova que o motor funciona para jogador↔empresa sem mudança no motor.

## 2. Checklist de `18.13` (Bot Test)

| # | Item | Estado |
|---|---|---|
| 1 | criação jogador↔jogador, jogador↔empresa, empresa↔empresa | motor genérico testado nas 3 combinações (jogador↔empresa com tipo de teste até P1.07) |
| 2 | aceite das duas partes | testado |
| 3 | fornecimento recorrente automático | testado |
| 4 | execução e pagamento de empréstimo | testado |
| 5 | aluguel | **pendente de P1.07** (handler) |
| 6 | contrato governamental | **pendente de P1.09** (handler) |
| 7 | falha por falta de dinheiro ou estoque | testado |
| 8 | inadimplência | testado |
| 9 | multa | testado (quebra voluntária e por inadimplência) |
| 10 | encerramento normal | testado |
| 11 | quebra antecipada | testado |
| 12 | histórico preservado | testado (imutável; `contract_view`) |

## 3. O que foi implementado (e como)

- **Partes**: A entrega o objeto (vendedor/credor), B o recebe; os papéis e os tipos de parte permitidos vêm do handler. Quem age por
  empresa é o seu **Dono** (02 §16); por si, o próprio jogador.
- **Proposta e aceite (18.4)**: quem propõe já aceita; o contrato só entra em vigor com o aceite da outra parte. Recusa (outra parte) e
  retirada (quem propôs) levam ao estado técnico `cancelled`. Termos congelados: selo `terms_hash`, `save` recusa mudança, auditoria confere.
- **Execução (18.5)**: tick diário do mundo (prioridade 70), uma ocorrência por vez, em ordem, com catch-up. Única por (contrato, sequência);
  chaves `contract:{id}:exec:{n}` no registro monetário e no estoque.
- **Fornecimento**: entre empresas; entrega do estoque + pagamento + registro da venda no mercado (canal `contract`) em **um ato tudo-ou-nada**.
- **Empréstimo**: entre jogadores; principal entregue ao ativar; parcelas; parcela sem caixa vira **obrigação pendente** (24 §24.9).
- **Inadimplência (18.6)**: `FAILED` registra qual obrigação, quem era responsável, quando, quanto ficou pendente (e a multa, se aplicada).
- **Quebra (18.7) e multa (18.8)**: multa = transferência `PENALTY` real do responsável à outra parte; nunca cria dinheiro.
- **Histórico (18.11)**: `ContractEvent` imutável e contínuo; `ContractExecution` imutável; `audit_contracts` reconstrói e confere.

## 4. Lacunas e interpretações — decisões necessárias do Game Director

1. **O que acontece depois de uma falha (18.6 "depende das condições previstas no contrato")?** Implementado: cada ocorrência é independente e
   **não é refeita** (uma falha de entrega não é reentregue depois); o contrato fica `defaulted` até a próxima ocorrência cumprida (fornecimento)
   ou até a dívida gerada ser quitada (empréstimo). Alternativa: refazer a ocorrência falha nos dias seguintes.
2. **Condição de quebra por inadimplência.** O `18` não define quando a inadimplência quebra o contrato. Implementado um campo opcional
   `max_failures` (número total de falhas): ao atingi-lo, o contrato fica `broken`, o responsável paga a multa (ou fica devendo, como obrigação
   `PENALTY`, se não tiver caixa). Sem `max_failures` nunca quebra sozinho.
3. **Juros do empréstimo.** O exemplo do `18` diz "2% de juros por 90 dias". Implementado: taxa **total simples** sobre o principal (não composta,
   não ao dia), dividida entre as parcelas; frequência `once` exige `term_days`. Alternativa: taxa ao mês/dia, composta.
4. **Quebra de empréstimo.** Implementado: o principal das parcelas ainda não vencidas vira dívida imediata do tomador (obrigação), os juros
   futuros deixam de existir, a multa vai de quem quebra à outra parte; vale também quando quem quebra é o credor.
5. **Fornecimento: partes e imposto.** Só empresas (jogador comprando de empresa pertence ao Varejo/Mercado, `17a`). O preço unitário é **bruto**;
   o comprador paga o bruto e o imposto sobre vendas (5%, `11` §11.1, padrão até existirem leis) é **retido do valor** (vendedor recebe o líquido:
   `SALE` líquida + `TAX_SALES`). Mesma lacuna 5 da `17a` (taxas/impostos): se o GD decidir outra forma, muda um ponto (`SupplyHandler.execute`).
6. **Qualidade entregue** no fornecimento = a qualidade média do estoque do vendedor no momento (a mistura no comprador segue a regra do estoque).
7. **Limite da multa** `[PROV]` = valor total do objeto (fornecimento: ocorrências × quantidade × preço; empréstimo: principal). A quebra
   voluntária com multa **sem caixa para pagá-la é recusada** (`PENALTY_UNPAYABLE`): não existe quebra "a prazo".
8. **Calendário.** Diária = 1 dia; semanal = 7 dias; mensal = mesmo dia do mês no calendário do jogo (limitado ao fim do mês). O fornecimento só
   pode começar num dia **futuro** (a execução ocorre à virada do dia); proposta cuja data passou é cancelada (`expired`).
9. **Sem reserva de fundos na proposta.** O credor precisa ter o principal no instante do segundo aceite (`LENDER_INSUFFICIENT_FUNDS` desfaz o aceite).
   Nem comprador nem vendedor reservam nada antes da execução.
10. **Falha por capacidade/uso do comprador** (`STOCK_FULL`, `NO_VALID_USE`) é responsabilidade do **comprador**; falta de estoque, do vendedor.
11. **Pagamentos de dívidas de contratos** seguem a regra global do registro monetário (R4: competência mais antiga, depois id), pelo caixa
    disponível do devedor, no começo de cada tick diário (antes das novas ocorrências).
12. **Contrato de trabalho**, reputação, arbitragem, cláusulas livres e mercado secundário: fora (18.12), nada implementado.

## 5. Decisões do Game Director (2026-10-24) — aplicadas

| # | Decisão | Como ficou |
|---|---|---|
| 1 | Ocorrência que falhou fica **perdida**; não é refeita (evita acúmulo de entregas/pagamentos); o contrato segue o calendário original, salvo quebra por inadimplência | como já estava; testado (`completed_with_failures`) |
| 2 | `max_failures` = falhas **consecutivas**; ocorrência cumprida **zera** o contador; nulo = sem quebra automática; cada falha vai ao histórico | novo `consecutive_failures` (audita contra a sequência de execuções); testes: sequência falha-cumpre-falha não quebra, duas seguidas quebram |
| 3 | Juros **simples** sobre o principal original, taxa total do contrato; sem composto/diário/mensal; taxa e **valor total dos juros congelados** nos termos | `terms.interest_total_cents` calculado na proposta, selado pelo `terms_hash`; a auditoria recalcula |
| 4 | Quebra de empréstimo: principal restante vira **obrigação exigível**; juros futuros deixam de ser cobrados; vencidos continuam; sem criar dinheiro nem duplicar dívida; pagamento pelo registro global | como já estava; chave única `contract:{id}:remaining` |
| 5 | Fornecimento só entre empresas, preço unitário bruto, bruto = SALE líquida + `TAX_SALES`, venda/estoque/pagamento/imposto atômicos | como já estava |
| 6 | Qualidade = média **ponderada pela quantidade das unidades efetivamente entregues**, congelada no registro da entrega | `delivered_quality` na execução e nos movimentos de estoque (saída e entrada), conferida pela auditoria. **Limitação registrada:** o estoque guarda UMA qualidade média por produto (`companies.stock`); logo o lote entregue tem essa qualidade — não existe dado por lote mais fino. A mistura no comprador é a média ponderada pela quantidade já existente no estoque |
| 7 | Multa limitada ao valor total do contrato; sem caixa na quebra voluntária a quebra **acontece** e a multa não paga vira obrigação pendente (auditável, sem perdão, sem cobrança dupla) | `PENALTY_UNPAYABLE` removido; `_charge_penalty` (uma transferência **ou** uma obrigação, mesma chave); vale também para a quebra por inadimplência |
| 8 | Semanal = 7 dias; mensal = mesmo dia do mês limitado ao último; fornecimento começa em data futura | como já estava; testes de limites de mês e primeira ocorrência |
| 9 | Sem reserva na proposta; credor precisa ter o principal no 2º aceite; verificação e transferência atômicas | teste de concorrência: aceite × gasto simultâneo do credor (exatamente um vence) |
| 10 | Falta de estoque = vendedor; estoque cheio / produto sem uso = comprador; mesma classificação em todos os handlers | `Handler.RESPONSIBILITY` por código; a auditoria acusa `RESPONSIBILITY_MISMATCH` |
| 11 | Quitação: regra global, mais antigas primeiro, antes das novas ocorrências do dia, sem passar do saldo, sem duplicidade no catch-up | teste de catch-up de vários dias: pago = caixa disponível, nada a mais |

Pendente apenas o que o GD não respondeu: nada nesta lista. Os `[PROV]` que restam em `contracts/params.py` são o teto de juros
(100%, não decidido) e o limite técnico de 1000 ocorrências por contrato.
