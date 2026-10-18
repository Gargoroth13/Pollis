# 24 — Registro Monetário (Ledger)

**Status: FINAL — BOT TEST.** Aprovado pelo Game Director em 2026-10-15 (decisão sobre P0.02 e P0.07a), com as correções A–D e os ajustes de R1–R10 incorporados abaixo. A implementação é a P0.07b; o teto de déficit (§24.16) está decidido e sua implementação pertence à P1.09/P1.12.

Este documento define **como o dinheiro existe, circula e é auditado** no Polis. Ele **não** define quanto custa nada, quem paga o quê nem alíquotas: isso pertence aos documentos de cada sistema (`02`, `04`, `05`, `09`, `10`, `11`, `18`, `19`...). O registro monetário só oferece as ferramentas e as garantias de integridade.

---

## 24.0. Fontes e decisões já aprovadas que este documento incorpora

| Origem | Decisão incorporada |
|---|---|
| `09` §1, §7, §18, §34, §45.9 | Dinheiro público é dinheiro existente; sem criação por déficit; log financeiro auditável; origem do dinheiro por dotação explícita; destinos das cobranças; sumidouro |
| `11` 11.1.0 | Dois contadores diários (`C_S`, `C_T`), natureza do lançamento, cálculo determinístico, soldo militar, sem criação de dinheiro |
| `19` 19.9, 19.11, 19.16; `18` 18.14 | Banco da milícia, conta de retenção do contrato (Requisição Especial), retenção de arrecadação durante ação de milícia |
| `20` | Toda fórmula composta devolve valor + detalhamento estruturado (`core.breakdown.Explained`) |
| `21` 21.60 | Dotações de cenário, contas reais, sem NPC e sem transação fictícia |
| `CLAUDE.md` §5.2 | Conservação monetária: transferência move dinheiro existente; dinheiro novo só por fonte documentada |
| Q1 (2026-10-14) | Fonte de dinheiro = dotação inicial explícita por conta, como lançamento de emissão; fonte contínua durante a formação da população; zero válido se explícito; valor ausente → cenário recusa iniciar; sem emissão periódica discricionária |
| GD 2026-10-15 | R1–R10 aprovadas com ajustes; teto de déficit decidido (§24.16); correções A–D (conservação bruto/reservado/disponível, ordem de liquidação estável, retenção genérica sem módulo militar, auditoria) |
| Q2 (2026-10-14) | Destinos: viagem, correio e fundação de empresa → caixa federal; leilão de lote público → Município do lote; milícia (fundação/melhorias) → sumidouro; campanhas → caixa federal pagador, destino final sumidouro; tratamento → hospital/prestador (`04` §13) |

---

## 24.1. Princípios

1. **Todo centavo tem origem e destino identificados.** Não existe lançamento "sem contraparte".
2. **Conservação.** A soma de todos os saldos (incluindo as contas de sistema) é sempre **zero**; o dinheiro existente é exatamente o que foi emitido por dotações, menos o que está no sumidouro.
3. **Sem saldo negativo.** Nenhuma conta comum fica negativa. A recusa é um código (`INSUFFICIENT_FUNDS`), nunca um débito parcial silencioso. A única conta com saldo negativo é a conta técnica de emissão (§24.3), por construção.
4. **Imutável e auditável.** Lançamentos nunca são alterados nem apagados; erro se corrige com **estorno** (um novo lançamento que referencia o original).
5. **Atômico e idempotente.** Uma transação grava todas as suas pernas ou nenhuma; repetir a mesma requisição com a mesma chave não duplica efeito.
6. **Um caminho só.** Jogadores humanos, Bots, o sistema e os governos usam os **mesmos serviços** do registro; não existe caminho privilegiado para Bots (`CLAUDE.md` §5.4).
7. **O registro não decide política nem balanceamento.** Ele recebe origem, destino, valor, natureza e referência de quem chama. Regras como "quanto custa viajar" ficam no sistema de origem.
8. **Explicável.** Todo valor calculado pelo registro (limite de remuneração, saldo disponível, divisão de imposto) devolve `Explained` com os fatores e quais limites restringiram o resultado.

---

## 24.2. Vocabulário

| Termo | Significado |
|---|---|
| **Conta** | Entidade que tem saldo. Pertence a um dono (jogador, empresa, governo, milícia) ou é uma conta de sistema |
| **Lançamento** (`Entry`) | Uma movimentação imutável de **uma conta para outra** (origem → destino), com valor, natureza, referência e saldos antes/depois |
| **Transação** (`Transaction`) | Conjunto de lançamentos gravados **juntos** (ex.: venda = preço ao vendedor + imposto à União). Atômica |
| **Natureza** | Classificação fechada do lançamento (§24.8). Decide, por exemplo, se conta nos contadores salariais |
| **Referência** | Aponta o fato que gerou o lançamento (lei, projeto, contrato, cenário, ação, viagem...) |
| **Reserva** (`Hold`) | Parte do saldo de uma conta marcada como **indisponível** sem mudar de dono (§24.7) |
| **Retenção** | Dinheiro que **sai** da conta do pagador e fica numa **conta de retenção** até uma condição ser resolvida (§24.10) |
| **Obrigação pendente** | Valor **devido e não pago** por falta de caixa. **Não é dinheiro**, não está em nenhum saldo (§24.9) |
| **Dotação** | Lançamento de emissão previsto no cenário (§24.11) |
| **Dia de competência** | Dia de jogo ao qual uma remuneração pertence (§24.12) |
| **Centavo** | Menor unidade; todo valor do registro é um número inteiro de centavos |

---

## 24.3. Contas

### 24.3.1. Tipos

| Tipo | Dono (referência) | Disponível para gasto | Pode ficar negativa | Observação |
|---|---|---|---|---|
| `PLAYER` | jogador | sim | não | Criada com o jogador (humano ou Bot) |
| `COMPANY` | empresa (P1.04) | sim | não | Caixa da empresa; Dono não é dono do saldo |
| `UNION` | — (singleton) | sim | não | **Caixa federal**; administrado pelo Presidente |
| `STATE` | Estado (`geography.State`) | sim | não | Caixa estadual; Governador |
| `MUNICIPALITY` | Cidade (`geography.City`) | sim | não | Caixa municipal; Prefeito (ver R8: Município = Cidade do `08`) |
| `MILITIA_BANK` | milícia (P1.17) | sim, conforme regras de `19` | não | Banco da milícia (19.9) |
| `RETENTION` | contrato ou ação militar | **não** (custódia) | não | Escrow de contrato; arrecadação retida durante ação de milícia |
| `SINK` | — (singleton) | **não** | não | **Sumidouro** (Q2) |
| `ISSUANCE` | — (singleton) | **não** | **sim, só por emissão** | Contrapartida técnica das dotações |

O Exército **não tem conta própria**: o orçamento militar é federal e usa o caixa federal (`09` §45.8). Estoques de itens não são dinheiro e pertencem ao Inventário (P1.02) e às Empresas (P1.04).

### 24.3.2. Regras

- Uma conta é identificada por `(tipo, dono)`; há no máximo uma por par. `UNION`, `SINK` e `ISSUANCE` são singletons.
- O registro **não depende** de apps que ainda não existem: a conta guarda `owner_kind` e `owner_id` (inteiro) e o app dono valida a existência ao pedir a conta. Jogadores e Geografia já existem e são validados desde a P0.07b.
- Contas **nunca são excluídas**. O fechamento de um dono (ex.: empresa dissolvida) é uma regra do sistema dono; o registro só impede mover dinheiro para uma conta marcada como encerrada (`ACCOUNT_CLOSED`), e exige saldo zero para encerrar.
- O saldo guardado na conta é uma **cópia de desempenho**: a verdade é a soma dos lançamentos. Um comando de auditoria reconstrói os saldos a partir do log e compara (§24.17).

### 24.3.3. Saldo bruto, reservado e disponível; conservação

Três conceitos distintos, **sem sobreposição**:

| Conceito | Definição |
|---|---|
| **Saldo bruto** | Soma dos lançamentos da conta. É o dinheiro que a conta possui, **incluindo** o que está reservado |
| **Reservado** | Soma das reservas ativas da conta (§24.7). Faz **parte** do saldo bruto; não é conta, nem retenção, nem dinheiro adicional |
| **Disponível para gastar** | `saldo bruto − reservado`. Só serve para **autorizar gasto**; nunca entra na conservação |

```text
soma(saldo bruto de TODAS as contas, incluindo ISSUANCE) = 0
emitido_total = −saldo bruto(ISSUANCE)
emitido_total = saldos brutos das contas operacionais + retenções + sumidouro
```

- **contas operacionais** = `PLAYER`, `COMPANY`, `UNION`, `STATE`, `MUNICIPALITY`, `MILITIA_BANK`;
- **retenções** = saldo bruto das contas `RETENTION` (dinheiro que existe, em custódia, e voltará a circular);
- **dinheiro em circulação** (Q2) = saldos brutos operacionais + retenções, **excluído** o sumidouro.

A conservação usa **somente saldos brutos**. Reservas não são descontadas nessa fórmula e, portanto, não podem ser contadas duas vezes.

---

## 24.4. Precisão e limites técnicos

- Todo valor é **inteiro em centavos** (`BigInteger`). As operações do registro recebem **só inteiros**; `Decimal`, `float`, texto e booleano são **recusados** (`AMOUNT_NOT_IN_CENTAVOS`), em vez de arredondar sem avisar. A conversão de reais (`Decimal`) para centavos fica em `ledger.money.from_reais`, que **recusa** o que não estiver exatamente em centavos (`ValueError`). Float é proibido (igual a `core.breakdown`).
- **Valores calculados** (alíquotas, divisão proporcional) arredondam **uma vez**, com `ROUND_HALF_EVEN` (mesma regra já usada em `travel.rules.charge_amount`), e a **última perna é o resto** (`total − soma das demais`), de modo que nenhuma fração se perde nem se cria.
- Valor de lançamento > 0 (`AMOUNT_NOT_POSITIVE`). Não existe lançamento de valor zero.
- **Limite técnico** de valor por lançamento e por saldo: `MAX_AMOUNT = 10^15 centavos` (R$ 10 trilhões) `[PROV]`, calibrável. É o "limite técnico utilizado pelo sistema monetário" citado em `11` 11.1.1 (teto de preço). Passar dele recusa com `AMOUNT_TOO_LARGE`.

---

## 24.5. Lançamentos e transações

### 24.5.1. Campos do lançamento

| Campo | Descrição |
|---|---|
| `seq` | Sequência global crescente; é a **ordem do registro monetário** (11.1.0) |
| `transaction` | Transação à qual pertence |
| `idempotency_key` | Chave única da transação (no lançamento principal); ver §24.5.3 |
| `from_account`, `to_account` | Origem e destino (diferentes: `SAME_ACCOUNT`) |
| `amount` | Centavos, > 0 |
| `nature` | Natureza (§24.8) |
| `competence_day` | Dia de jogo de competência (§24.12) |
| `at` | Instante de jogo (`core.timeline`), mais o instante real para auditoria |
| `category`, `operation` | Para contas públicas: categoria orçamentária (`09` §12) e operação (§34). Texto livre validado quando a categoria for definida pela P1.09 |
| `reference_kind`, `reference_id` | **Obrigatórios** (`REFERENCE_REQUIRED`). Fato gerador: `scenario`, `law`, `project`, `contract`, `journey`, `action`, `obligation`, `hold`, `bond`... |
| `actor` | Quem pediu: jogador, `system` ou `scheduler`. Bot e humano são o mesmo tipo de ator |
| `from_balance_before/after`, `to_balance_before/after` | Saldos de cada lado (`09` §34) |
| `explained` | Detalhamento estruturado do cálculo que originou o valor, quando houve (§24.14) |
| `reverses` | Lançamento estornado (só para `REVERSAL`) |

Isso cobre integralmente o log exigido por `09` §34 (data/hora, governo, origem, destino, valor, categoria, operação, referência, saldo antes e depois).

### 24.5.2. Operações do serviço

Todas devolvem `ActionResult` (padrão do projeto): `ok` + código + detalhe estruturado.

| Operação | O que faz |
|---|---|
| `ensure_account(kind, owner_id)` | Cria (idempotente) ou devolve a conta |
| `transfer(from, to, amount, nature, reference, key, …)` | Uma perna |
| `post_transaction(legs, key, …)` | Várias pernas, atômicas (ex.: venda com imposto) |
| `quote(…)` / `can_afford(account, amount)` | Consulta **sem** mover dinheiro; devolve `Explained` (saldo, reservas, disponível, falta). É o que o `check_action` do Action Registry usa |
| `hold` / `release_hold` / `consume_hold` | Reservas (§24.7) |
| `open_obligation` / `settle_obligations` | Obrigações pendentes (§24.9) |
| `submit_remuneration` / `liquidate_remuneration` / `pay_remuneration_now` | Remuneração com limites S/T e **ordem de liquidação estável** (§24.12) |
| `grant_scenario_allocation` | Dotação (§24.11) |
| `retain` / `release_retention` | Retenções (§24.10) |
| `register_tax_resolver` / `route_tax` | Interface de roteamento do imposto por território; sem módulo militar (§24.10.3) |
| `reverse(entry, reason)` | Estorno técnico, auditado |

`transfer` **recusa** as naturezas de remuneração (`NATURE_REQUIRES_PAYROLL`): salário, soldo, salário de Dono e salário político só passam por `submit_remuneration`/`liquidate_remuneration`, para que ninguém contorne os contadores.

### 24.5.3. Atomicidade, concorrência e idempotência

- Cada transação roda em **uma transação de banco**. Falha em qualquer perna desfaz todas.
- **Ordem de travamento**: as contas envolvidas são travadas em **ordem crescente de id** (evita *deadlock*). O saldo é lido e gravado sob esse travamento.
- **Idempotência**: toda requisição traz uma `key` única do chamador (ex.: `travel:{jogador}:{instante}:{origem}:{destino}`, `grant:{scenario}:{account}`, `wage:{player}:{day}:{company}:{n}`). Repetir a mesma `key` com o mesmo conteúdo devolve o resultado original (`already_posted=True`) sem novo efeito. A mesma `key` com conteúdo diferente recusa com `IDEMPOTENCY_CONFLICT`, e **só** nesse caso. O contrato vale também **sob concorrência**: se duas requisições com a mesma `key` e o mesmo conteúdo disputam a criação, a que perde desfaz tudo o que tinha feito (inclusive reservas consumidas) e devolve a transação **original** (`already_posted=True`), nunca conflito nem erro; a mesma regra vale para reservas, obrigações e pedidos de remuneração. Cada transação guarda o conteúdo canônico (`payload`) com dois blocos: `request` (o que o chamador pediu: pernas, referência, dia **informado** ou nulo, reservas usadas, estorno), cujo hash é o `payload_hash` e identifica a requisição; e `competence_day`, o dia de competência **efetivo** gravado nos lançamentos, sempre presente mesmo sem dia informado. O dia derivado do relógio fica fora do hash de propósito: reenviar uma requisição sem dia depois da meia-noite devolve a transação original, com o dia original. A idempotência da obrigação pendente compara todos os campos que a definem, inclusive a alíquota (normalizada a 6 casas) e o território do imposto retido; alíquota com mais de 6 casas ou território fora de `tipo:id` é recusado (`TAX_RATE_INVALID`, `TAX_TERRITORY_INVALID`), nunca arredondado.
- **Falha de caixa**: `INSUFFICIENT_FUNDS` com `Explained` (saldo, reservas, disponível, valor pedido, falta). Nada é gravado.
- **Hot account**: a `UNION` recebe quase todo imposto e taxa e será a linha mais disputada. Na primeira versão há **um único travamento por conta** e o gargalo é **medido** (`CLAUDE.md` §9) antes de otimizar; a interface não muda se for preciso fatiar o caixa federal depois (risco R-LEDGER-01).

---

## 24.6. Estorno

Erro técnico (não regra de jogo) se corrige com `REVERSAL`: novo lançamento no sentido oposto, mesmo valor, `reverses=<seq>`, motivo obrigatório e ator registrado. O original **permanece**. Um lançamento só pode ser estornado uma vez e só se o destino ainda tiver saldo; senão, recusa (`REVERSAL_NOT_POSSIBLE`) e o caso vira tratamento manual registrado. Estorno **não** é mecânica de jogo (devolução de compra, reembolso etc. são lançamentos normais de natureza `REIMBURSEMENT`).

---

## 24.7. Reservas (`Hold`)

Uma reserva marca um valor da **própria conta** como indisponível, sem movê-lo.

```text
disponível_para_gastar = saldo bruto − soma(reservas ativas)
```

A reserva **não altera o saldo bruto** e não é descontada na conservação (§24.3.3).

Usos previstos:

- **orçamento comprometido** (`09` §10, §31): P1.09 reserva o valor de projetos e contratos já assumidos; o governo não gasta o que está reservado;
- **campanhas temporárias** (`09` §36; decisão D16): reserva no momento em que a lei entra em vigor; sem fundos, a campanha não opera;
- **Fornecimento ao Exército** (`18` 18.14, fluxo B): reserva no caixa federal enquanto o contrato está aceito.

Regras: uma reserva tem estado `ACTIVE → RELEASED | CONSUMED`; `consume_hold` converte a reserva em transferência (para o destino) na mesma transação; liberar devolve a disponibilidade; reservas não podem somar mais que o saldo (`INSUFFICIENT_AVAILABLE`); toda mudança é auditável. Reserva **não é lançamento** (não move dinheiro) e não entra na conservação. Para o jogador comum **não** há reserva automática em lances de leilão: `10` §4.4 cobra no pagamento e invalida a arrematação se faltar dinheiro.

> **Reserva x retenção.** Reserva = mesma conta, dinheiro ainda do dono, só indisponível. Retenção = o dinheiro **saiu** da conta do dono e está em custódia numa conta própria (§24.10). Os dois existem porque o contrato de Requisição Especial exige que o valor "nunca esteja disponível ao mesmo tempo para comprador e vendedor", e a retenção de arrecadação exige que a mesma receita nunca esteja em dois lugares.

---

## 24.8. Naturezas

Toda natureza declara **como conta nos contadores salariais** e **qual sistema a possui**. O registro não infere natureza.

| Natureza | Contadores | Quem usa |
|---|---|---|
| `WAGE` (salário de trabalho, inclui servidor público) | `C_S` e `C_T` | P1.04, P1.06, governos |
| `MILITARY_PAY` (soldo) | `C_S` e `C_T` | P1.17 |
| `OWNER_SALARY` (cargo Dono) | `C_S` e `C_T` | P1.04 |
| `POLITICAL_SALARY` | **só** `C_T` | P1.11 |
| `TAX_SALES`, `TAX_INCOME`, `TAX_PROPERTY` | nenhum | 11, 05/17/02, 10 |
| `SALE` (varejo, mercado, contrato de fornecimento, venda de imóvel) | nenhum | P1.04, P1.05, P1.07, P1.08 |
| `SUBSIDY` | nenhum | 09 §29 |
| `GOV_TRANSFER` (repasse entre níveis) | nenhum | P1.09 |
| `PUBLIC_WORKS_PAYMENT` (projetos, Construtora) | nenhum | P1.09, P1.07 |
| `RENT`, `TUITION` | nenhum | 10, 03 |
| `LOAN_PRINCIPAL`, `LOAN_REPAYMENT`, `LOAN_INTEREST` (recebimento de dívida) | nenhum | 18 |
| `BOND_PURCHASE`, `BOND_INTEREST`, `BOND_REDEMPTION` | nenhum | P1.09 |
| `PENALTY` (multa), `DONATION`, `REIMBURSEMENT`, `INDEMNITY` | nenhum | 18, 19, vários |
| `TRAVEL_FEE`, `MAIL_FEE`, `COMPANY_FOUNDING`, `AUCTION_PAYMENT`, `TREATMENT` | nenhum | 04, 05, 02, 10 |
| `MILITIA_FOUNDING`, `MILITIA_UPGRADE`, `CAMPAIGN_COST` | nenhum | 19, 06/11 |
| `RETENTION_IN`, `RETENTION_RELEASE`, `RETENTION_REFUND` | nenhum | 18.14, 19.16 |
| `SCENARIO_GRANT` | nenhum | cenário (só ele) |
| `REVERSAL` | nenhum | auditoria técnica |

Doações, vendas, reembolsos, transferências, dotações, indenizações e recebimento de dívida **não consomem** `C_S` nem `C_T` (11 11.1.0). A lista é **fechada**: nova natureza exige mudança neste documento.

---

## 24.9. Obrigações pendentes

Obrigação pendente é o **registro de uma dívida vencida que o pagador não pôde pagar por falta de caixa**. Ela **não é dinheiro**: não aparece em saldo, não conta em circulação e **não cria dinheiro** ao ser quitada (quitar é uma transferência comum).

| Campo | |
|---|---|
| `debtor`, `creditor` | contas |
| `amount_due`, `amount_paid` | centavos |
| `nature`, `competence_day`, `reference` | como no lançamento |
| `status` | `OPEN`, `PAID`, `CANCELLED` |
| `created_at` | instante de jogo |

- **Quem cria**: o sistema de origem decide. O registro só oferece a ferramenta. Já aprovado: **salários políticos** (`06`, `09` §45.4: sem caixa, vira obrigação pendente). Despesas obrigatórias públicas são classificadas em `09` §13; se o não pagamento vira obrigação pendente é decisão da P1.09, e o registro suporta isso. **Não** criam obrigação: soldo excedente acima do recebível (11 11.1.0), mensalidade escolar (inadimplência = expulsão, `03` §6.1) e aluguel/parcelas de contrato (inadimplência de contrato, `18` §18.6 e `10` §11), que têm a própria consequência.
- **Quitação**: `settle_obligations(debtor)` paga o que o caixa permite, na ordem **competência mais antiga primeiro, depois id da obrigação** (ordem estável; ver R4). Pagamento parcial é permitido e registrado.
- **Prioridade entre obrigações do mesmo devedor**: `09` §11 manda priorizar obrigações já assumidas sobre novas despesas discricionárias; o registro não bloqueia despesas discricionárias (isso é da P1.09), mas oferece `pending_total(debtor)` para ela decidir.
- **Cancelamento**: só por regra do sistema de origem (ex.: o cargo político é perdido: o salário já acumulado **permanece devido**; nenhuma obrigação some sem registro).
- **Transparência**: obrigações pendentes de governos são públicas (`09` §33, "compromissos futuros").

---

## 24.10. Retenções e sumidouro

### 24.10.1. Conta de retenção de contrato (Requisição Especial, `19` fluxo A)

```text
fechamento:  banco da milícia ──(RETENTION_IN)──▶ RETENTION(contrato)
entrega ok:  RETENTION ──(SALE líquido)──▶ empresa fornecedora
                       ──(TAX_SALES)────▶ caixa federal (ou retenção de ação, §24.10.3)
falha:       RETENTION ──(RETENTION_REFUND)──▶ banco da milícia
```

O valor retido está **na conta de retenção**, não no saldo do comprador nem do vendedor: nunca está disponível aos dois ao mesmo tempo. O fechamento **recusa sem fundos** (`INSUFFICIENT_FUNDS`) e a milícia continua anônima publicamente (a conta de retenção registra a identidade real para auditoria, como `18` §18.1 manda).

### 24.10.2. Fornecimento ao Exército (`19` fluxo B)

Sem retenção: o caixa federal **reserva** o valor (`Hold`, §24.7) quando o contrato é aceito; cada entrega **consome** a reserva e paga o fornecedor. As proteções contra pagamento e entrega duplos usam a idempotência (§24.5.3).

### 24.10.3. Retenção genérica e roteamento tributário (`19` 19.16, `09` §45.6)

O registro oferece **mecanismo genérico**; a regra militar pertence à P1.17. A P0.07b **não importa nem presume** nenhum módulo militar.

- **Retenção genérica**: `open_retention(purpose, owner_ref)` cria uma conta `RETENTION` com identificador opaco (`owner_ref`, ex.: `contract:123`, `militia_action:7`). `retain` move dinheiro para ela; `release_retention(retention, destino, nature)` move o saldo (todo ou parte) para um **destino escolhido por quem chama** e recusa se o destino não existir ou estiver encerrado (`ACCOUNT_CLOSED`/`ACCOUNT_NOT_FOUND`); nenhum beneficiário é inventado. A conta só pode ser encerrada com saldo zero.
- **Roteamento tributário**: `route_tax(territory_ref, at)` devolve a conta de destino de um imposto. `territory_ref` é um par opaco (`("city", id)`, `("state", id)`...), vindo da atribuição territorial de `09` §45.5. O destino padrão é a `UNION`. Outros módulos **registram resolvedores** com `register_tax_resolver(name, fn)`, onde `fn(territory_ref, at)` devolve uma conta de retenção ou `None`. Resolvedores são consultados em ordem alfabética do nome; se dois devolverem contas **diferentes**, o roteamento recusa com `TAX_ROUTE_AMBIGUOUS` (nunca escolhe por ordem de chegada). Sem resolvedor registrado, o imposto vai à `UNION`.
- **Ligação militar (P1.17)**: a P1.17 registra um resolvedor que consulta as ações de milícia ativas e devolve a conta de retenção da ação que cobre o território; ao encerrar a ação, ela chama `release_retention` para o banco da milícia (vitória) ou para a `UNION` (repressão, derrota, falha), conforme `19` 19.16. Só o imposto **efetivamente arrecadado durante** a ação é roteado; os 30 dias anteriores não são retirados retroativamente.
- A mesma receita **nunca** está em dois lugares: o imposto roteado vai **ou** à `UNION` **ou** à retenção, numa única perna.

### 24.10.4. Sumidouro (Q2)

- Só **recebe** (`SINK_NOT_SPENDABLE` para qualquer lançamento que o tenha como origem). Seus lançamentos nunca são apagados.
- Recebe: **fundação de milícia** (pago pela conta do fundador, não há banco ainda) e **melhorias** (pagas pelo banco da milícia) — `MILITIA_FOUNDING`, `MILITIA_UPGRADE`; **custos de campanhas** (`CAMPAIGN_COST`), pagos pelo **caixa federal**, depois de reservados (§24.7).
- Seu saldo faz parte da conservação (§24.3.3) e é **excluído** do dinheiro em circulação; aparece nas métricas como "destruído por custo de jogo".

---

## 24.11. Dotações de cenário (origem do dinheiro, Q1)

- **Única fonte de dinheiro novo**: lançamento `ISSUANCE → conta`, natureza `SCENARIO_GRANT`, referência `scenario:<id>`.
- **Só pela via de dotação (proteção no serviço, não por convenção).** `SCENARIO_GRANT` só é gravada por `grant_scenario_allocation`. `transfer()` e `post_transaction()` chamados diretamente **recusam** a natureza (`ISSUANCE_NOT_ALLOWED`, `why=grant_path_only`), mesmo com a natureza, a chave e a referência corretas. A via de dotação usa uma permissão interna (`_GrantPermit`) que descreve exatamente a transação (uma perna, destino, valor, chave `grant:<cenário>:<conta>`, referência) e, **dentro da transação e com as contas travadas**, `_post` revalida a dotação contra a configuração: uma permissão forjada não emite nada além do que o cenário configurou.
- **O que a via valida** (recusa com código; nada é gravado): cenário existente (`SCENARIO_NOT_FOUND`) e **ativo** (`SCENARIO_NOT_ACTIVE`; ativar exige todas as linhas explícitas, e só um cenário fica ativo); papel conhecido (`GRANT_ROLE_UNKNOWN`) com **linha explícita** no cenário (`SCENARIO_GRANT_UNSPECIFIED`); papel **compatível com o tipo da conta** de destino (`GRANT_ROLE_ACCOUNT_MISMATCH`); valor **exatamente igual** ao da linha (`GRANT_AMOUNT_MISMATCH`; sem valor padrão, sem arredondar, sem tolerância). Replay da mesma chave devolve a dotação original (idempotência), inclusive depois de o cenário deixar de estar ativo.
- **Papéis de dotação (lista fechada)**, o que este §24.11 nomeia: `player` → conta de jogador/Bot; `union` → União; `state` → Estado; `municipality` → Município; `militia_bank` → banco de milícia. Papel novo, ou dotação a outro tipo de conta (por exemplo, empresas), exige mudar este documento. `set_grant_line` recusa papel fora da lista, e uma linha que já gerou dotações **não muda de valor** (`GRANT_LINE_LOCKED`), para a auditoria poder comparar cada dotação com a linha. Estas três decisões foram aprovadas pelo Game Director em 2026-10-17 (mapa fechado de cinco papéis, empresas fora; cenário **ativo** para uma emissão nova, com o replay idempotente de dotação já existente permitido depois da desativação; linha com dotações é imutável).
- **Protocolo de travamento da configuração e da emissão (um só)**:
  1. **Mutação da configuração** (`activate_scenario`, `set_grant_line`, toda escrita do ORM em `ScenarioGrantLine` e o renome/exclusão de `LedgerScenario`): o **primeiro** bloqueio é o de **todos** os cenários, numa só instrução em ordem crescente de pk (`lock_all_scenarios`). Só depois a operação lê os dados (linha, histórico) e decide. **Nada é lido antes para escolher o que travar e nenhuma verificação trava mais nada**: se os dados mudarem enquanto a operação esperava (outra mutação moveu a linha para outro cenário), o que ela relê já está coberto pelo conjunto travado. Um cenário referenciado que não está no conjunto travado (criado depois) é recusado com `ScenarioSetChangedError` (`SCENARIO_SET_CHANGED`; repita a operação), em vez de ser travado fora da ordem.
  2. **Emissão** (`_check_grant`): contas em ordem crescente de id e, por último, **um** cenário (o emissor); nada depois.
  3. Ninguém adquire bloqueio fora da ordem global e quem segura contas só pede um cenário: **sem ciclo, sem deadlock**. Uma dotação em andamento termina antes de uma alteração de linha, de uma ativação ou de qualquer mutação; uma emissão que espera uma ativação relê o estado e é recusada (`SCENARIO_NOT_ACTIVE`). Não compor, numa mesma transação externa, uma emissão (que segura um cenário) e uma mutação (que pede todos).
  Defesa em profundidade: restrição única parcial no banco (`ledger_single_active_scenario`), no máximo um cenário com `active = true`.
- **Imutabilidade efetiva da configuração depois da primeira dotação (também contra o ORM).** Existindo dotação histórica para o par (cenário, papel) (lançamento `SCENARIO_GRANT` com a referência do cenário e `explained.role`), a linha de dotação **não muda de valor, cenário nem papel e não é excluída**, por nenhum caminho do ORM: `save` (também com `update_fields`), `QuerySet.update`, `bulk_update`, `bulk_create` (o upsert em lote é recusado), `update_or_create`, exclusão por instância, por `QuerySet` ou em cascata (e `_raw_delete`, bem como o `_base_manager`). Recusa com `GrantLineLockedError` (código `GRANT_LINE_LOCKED`; o serviço `set_grant_line` devolve o mesmo código como `LedgerRefusal`). Também **não se recria** a linha de um par com histórico com valor diferente do emitido (inserção, `set_grant_line` ou mover outra linha para aquele par); repor o valor histórico é permitido. O cenário com dotações não muda de nome nem é excluído. Chamadas que não alteram nada (mesmos valores) e linhas/cenários sem dotações continuam livres. A guarda segue o protocolo acima (todos os cenários travados em ordem como primeiro passo; **o histórico é consultado depois do bloqueio**), de modo que uma emissão em andamento termina antes da mutação. A verificação roda antes da exclusão (não dentro do Collector do Django), para a recusa não envenenar uma transação externa.
- **Segunda defesa na emissão** (`_check_grant`): antes de autorizar uma dotação nova, o valor configurado tem de ser coerente com TODAS as dotações históricas do cenário e papel; se alguém contornar o ORM por SQL direto e a linha divergir do emitido, a emissão é recusada com `GRANT_HISTORY_INCONSISTENT` (detalhes: valor configurado e valores históricos), sem gravar nada. A auditoria continua apontando as dotações antigas (`GRANT_AMOUNT_MISMATCH`, invariante 18). O replay idempotente de uma dotação já gravada continua devolvendo a original.
- O cenário declara, **explicitamente**: dotação inicial por conta de jogador (humano ou Bot), saldos iniciais da União, dos Estados e dos Municípios, bancos de milícia e demais saldos iniciais de governo (`21` 21.60). Cada valor é uma linha de configuração com `valor` ou `UNSPECIFIED`.
- **Zero é válido** quando escolhido explicitamente (linha com valor 0; não gera lançamento, mas fica registrado). **Valor ausente** (`UNSPECIFIED`) faz o cenário que depende dele **recusar a inicialização** com `SCENARIO_GRANT_UNSPECIFIED`, listando as pendências. Nenhum valor é inventado pelo desenvolvimento.
- **Conta nova depois do início** (Bot criado pelo controlador de população, humano novo): recebe a dotação configurada, **idempotente** por `grant:<cenário>:<conta>` (uma vez por conta).
- **Sem emissão periódica discricionária**: nenhum cargo, lei, orçamento, título ou transferência emite dinheiro. Qualquer lançamento com origem `ISSUANCE` e natureza diferente de `SCENARIO_GRANT` é **erro de integridade** (verificado pela auditoria e por teste).
- **Métricas** (Dashboard de Bots e finanças): emissão total, emissão por cenário/período, número de contas contempladas, dinheiro em circulação, retido e no sumidouro.
- **Itens** (estoque inicial de equipamentos, `19`/`21` 21.60): a dotação de itens segue o mesmo padrão (explícita, auditável, com cenário como referência), mas pertence ao Inventário/Empresas; **não** é dinheiro e não passa por este registro.

---

## 24.12. Remuneração: contadores `C_S` e `C_T`

Implementa 11.1.0 **sem alterar** a regra aprovada, com **ordem de liquidação estável**.

### 24.12.1. Dados

Por `(jogador, dia_de_competência)` o registro guarda, em centavos: `C_S`, `C_T` e `C_P` (parcela **política** já reconhecida; subconjunto de `C_T`). Parâmetros lidos no instante da liquidação: `W` (salário mínimo), `S = 1.5 × skill relevante` (`skills.balance`, `[PROV]`; Físico para soldo), `T` (teto legal; `∞` se não houver). Leis passam a valer no instante de vigência (D15): valor já reconhecido **não é recalculado** quando a lei muda.

O salário político devido de um dia vem de um **provedor** registrado pela P1.11 (`register_political_due_provider(fn)`, `fn(jogador, dia) → centavos`); sem provedor, `P_dia = 0`. O registro não conhece cargos.

### 24.12.2. Reserva política sem dupla subtração

```text
P_reservada = max(0, P_dia − C_P − P_liberada)   # política ainda não reconhecida
```

- `P_reservada` é **derivada**, não guardada: ao reconhecer o salário político, `C_P` e `C_T` aumentam pelo valor reconhecido e `P_reservada` cai pelo mesmo valor (**consumo**). Se o valor reconhecido for menor que o devido (limitado por `T`), a diferença deixa de ser reservada (**liberação**), e o registro guarda essa diferença como `P_liberada` (por jogador e dia; equivale a marcar essa parte de `P_dia` como liquidada, sem impedir dois pedidos políticos no mesmo dia). `P_reservada = max(0, P_dia − C_P − P_liberada)` nunca desconta a mesma parcela duas vezes.
- Se o jogador deixa o cargo antes do reconhecimento, o provedor devolve `P_dia = 0` e a reserva some; o substituto passa a ter a reserva a partir da posse e **não recebe retroativo** por períodos anteriores (R3).

### 24.12.3. Cálculo

```text
cap_S   = max(W, S)
sobra_S = cap_S − C_S
sobra_T = T − C_T − P_reservada                 # T = ∞ → sem limite
reconhecido_não_político = max(0, min(devido, sobra_S, sobra_T))
reconhecido_político     = max(0, min(devido_político, T − C_T))
```

- A parcela política só **recebe prioridade** dentro de `T` porque `P_reservada` já foi subtraída de `sobra_T` das demais: o resultado não depende de quando o serviço político roda.
- `W` prevalece sobre um `S` menor, mas **não cria dinheiro** e **não ultrapassa `T`**.
- **Soldo**: `devido = W × m_patente` (Militar 1×, Capitão 2×, General 4×, Marechal 6×, `[PROV]`, parâmetros do sistema, não leis); o excedente acima do reconhecível **não é pago e não vira obrigação**.
- Sem salário político: `reconhecido/dia = max(W, min(S, T))` (pois `T ≥ W`).

### 24.12.4. Ordem de liquidação estável (independente da ordem das chamadas)

Serviços **não pagam** remuneração diretamente: eles **submetem** pedidos (`submit_remuneration`) e uma **liquidação** (`liquidate_remuneration`) os processa **como um conjunto**, em ordem determinada **apenas por dados do próprio pedido**, nunca pela ordem de chegada:

```text
chave = (classe, dia_de_competência, instante_do_fato, conta_pagadora, natureza, reference_kind, reference_id, key)
classe 0 = salário político   |   classe 1 = demais remunerações
```

- `instante_do_fato` é o instante de jogo em que a remuneração foi devida (ex.: a ação de trabalho), não o instante em que a chamada chegou.
- A liquidação ordena o conjunto pela `chave` e aplica as fórmulas **em sequência** (cada pedido vê o `C_S`/`C_T` deixado pelos anteriores da mesma ordenação). A **falta de caixa do pagador** é avaliada na mesma sequência global; por isso o conjunto reconhecido é o mesmo, qualquer que seja a permutação dos pedidos.
- **Lote de liquidação**: tudo que for submetido antes de uma chamada de `liquidate_remuneration`. A folha diária (política, Dono, soldo, servidores periódicos) é processada **em um único lote por tick**; remuneração de trabalho, que nasce de uma ação, liquida no ato (`pay_remuneration_now` = submeter + liquidar um pedido). O que um lote anterior já reconheceu e pagou é **definitivo** (o dinheiro já se moveu): a estabilidade vale **dentro** do lote; entre lotes vale a ordem do tempo de jogo em que as liquidações ocorrem. Serviços **não devem** liquidar em pedaços o que pode ir em um lote.
- A `key` de idempotência do pedido impede reconhecer o mesmo pedido duas vezes (mesmo lote ou lotes diferentes).

### 24.12.5. Competência, pagamento e imposto

- **O contador conta o valor reconhecido no dia de competência**, não quando o dinheiro sai. O limite é aplicado **uma vez**, na liquidação; quitar depois uma obrigação **não** reaplica limite nem altera contadores de outro dia.
- Para cada pedido reconhecido, na mesma transação: incrementa `C_S`/`C_T` (e `C_P`), e se o pagador tem caixa → transfere; se não, aplica a **política declarada pelo sistema pagador**: `PENDING` (cria obrigação, §24.9) ou `REFUSE` (nada é reconhecido; devolve `INSUFFICIENT_FUNDS`; o limite que sobrar vale para o próximo pedido da sequência). O tratamento de caixa insuficiente é **responsabilidade do sistema pagador**.
- **Política por tipo**: salário político → `PENDING` (aprovado). Salário de trabalho e do Dono → **P1.04** decide (`02` não diz). Soldo e servidores públicos → **P1.17/P1.09** (`09` §13 os classifica como despesa obrigatória). O registro suporta as duas políticas.
- **Imposto de renda** (R1): os contadores usam a remuneração **bruta** reconhecida; o imposto divide o bruto pago pelo pagador em **líquido ao jogador** + **imposto à conta tributária** (`route_tax`), numa só transação.
- **Dia**: dia de jogo (`core.timeline`, fuso do jogo); sem acúmulo entre dias.
- **Salário político** (R3): reconhecido **no tick diário** para o ocupante elegível naquele instante; pagador: União (Presidente e Deputados), Estado (Governador), Município (Prefeito) (`09` §45.4).
- Explicabilidade: o `Explained` do pedido traz `devido`, `W`, `S`, `T`, `C_S`, `C_T`, `C_P`, `P_reservada`, `sobra_S`, `sobra_T`, qual limite restringiu, reconhecido, descartado, pendente, imposto e líquido, e a posição do pedido na ordenação.

### 24.12.6. Validações de `T`

As validações de proposta (`T ≥ W`; `T ≥ maior salário político vigente`) pertencem a `11`/P1.12; o registro **não** as repete, mas **nunca** produz valor negativo se estiverem violadas (usa `max(0, …)`).

---

## 24.13. Mapa de fluxos (origem → destino)

| Fluxo | Origem → destino | Natureza | Sistema dono |
|---|---|---|---|
| Dotação inicial | `ISSUANCE` → conta | `SCENARIO_GRANT` | cenário (P1.18) |
| Salário de trabalho | empresa → jogador (+ IR → União/retenção) | `WAGE` | P1.04 |
| Salário do Dono | empresa → Dono | `OWNER_SALARY` | P1.04 |
| Soldo | União → militar | `MILITARY_PAY` | P1.17 |
| Salário político | União/Estado/Município → ocupante | `POLITICAL_SALARY` | P1.11 |
| Venda (com imposto) | comprador → vendedor; imposto → `route_tax` | `SALE`, `TAX_SALES` | P1.04/P1.05 |
| IPTU | proprietário → `route_tax` | `TAX_PROPERTY` | P1.07 |
| Viagem | jogador → União | `TRAVEL_FEE` | P0.06.1 (já existe o gancho de pagamento) |
| Correio | jogador → União | `MAIL_FEE` | P1.02 |
| Fundação de empresa | fundador → União | `COMPANY_FOUNDING` | P1.04 |
| Leilão de lote público | arrematante → Município do lote | `AUCTION_PAYMENT` | P1.07 |
| Tratamento | jogador → hospital/prestador | `TREATMENT` | `04` §13 |
| Aluguel / mensalidade | inquilino/aluno → proprietário/escola | `RENT`, `TUITION` | P1.07, P1.06 |
| Empréstimo | credor → devedor; devolução e juros → credor | `LOAN_*` | P1.08 |
| Multa | parte → parte | `PENALTY` | P1.08 |
| Repasse | União → Estado → Município | `GOV_TRANSFER` | P1.09 |
| Obra pública | governo → empresa | `PUBLIC_WORKS_PAYMENT` | P1.09/P1.07 |
| Subsídio | governo → beneficiário | `SUBSIDY` | P1.09 |
| Fundação/melhoria de milícia | fundador/banco → sumidouro | `MILITIA_*` | P1.17 |
| Campanha | União (reserva) → sumidouro | `CAMPAIGN_COST` | P1.11/P1.12 |
| Requisição Especial | banco da milícia → retenção → empresa | `RETENTION_*`, `SALE` | P1.17/P1.08 |
| Título público | comprador → governo; juros e principal → detentor | `BOND_*` | P1.09 |

---

## 24.14. `Explained` (`20`)

Toda decisão numérica do registro devolve estrutura, não texto:

- **Saldo disponível**: `saldo`, `reservas` (lista), `obrigações pendentes`, `disponível`, `valor pedido`, `falta`;
- **Remuneração**: `devido`, `W`, `S`, `T`, `C_S`, `C_T`, `cap_S`, `sobra_S`, `P_reservada`, `sobra_T`, **qual limite restringiu** (`binding`), `pagável`, `descartado` (soldo), `pendente` (obrigação), `imposto`, `líquido`;
- **Divisão de imposto**: base, alíquota, valor, destino (`route_tax`) e se foi retido por ação militar;
- **Dotação**: cenário, conta, valor, linha de configuração.

Usa `core.breakdown.Explained`/`Calc` (valores `Decimal` exatos; o arredondamento a centavos é explícito e registrado como passo).

---

## 24.15. Dívida pública e títulos (relação com a P1.09)

- **Título não cria dinheiro** (`09` §45.7). Compra = transferência do **comprador** (conta com saldo real) para a conta do governo emissor (`BOND_PURCHASE`); juros e principal = transferências do governo ao detentor (`BOND_INTEREST`, `BOND_REDEMPTION`). O registro **recusa** qualquer emissão com origem `ISSUANCE` ligada a título, lei, orçamento ou despesa.
- O **estoque de dívida** (títulos, juros, vencimento, situação) é um dado da P1.09, não do registro. O registro fornece: as transferências, as reservas dos pagamentos futuros e as obrigações pendentes por serviço da dívida.
- **Serviço da dívida sem caixa** → obrigação pendente + consequências de `09` §22 (atraso, restrições, crise); **nunca** emissão para evitar inadimplência.
- A P1.09 **declara a origem dos recursos** de cada despesa financiada por dívida: o comprador do título. Empréstimo entre jogadores (`18`) usa o mesmo mecanismo (transferência real credor → devedor), sem criar dinheiro.
- **Título é financiamento de caixa, não receita fiscal**: a venda de títulos fornece liquidez, **não reduz o déficit calculado** e **não contorna o teto** (§24.16). Despesa que ultrapassa o teto não se torna legal por ser financiada por dívida.

---

## 24.16. Teto de déficit público — decisão aprovada (GD 2026-10-15)

Fecha o `[ABERTO]` de `11` ("Teto de déficit público", Federal, 0%–50%, padrão 10%). A **implementação** pertence à P1.09/P1.12, não à P0.07b; a P0.07b fornece os dados (lançamentos por natureza, categoria e conta).

**Aplicação**: separadamente à **União**, a cada **Estado** e a cada **Município**, com o **mesmo parâmetro federal**.

**Janela**: móvel de **360 dias de jogo (12 períodos de 30 dias)**, ou desde a abertura da conta se menor, **com mínimo de 30 dias**; referência **anualizada**. Todas as quantias comparadas usam a **mesma unidade temporal**:

```text
R_ref   = R_janela × 360 / dias_da_janela           # receita de referência anualizada
Δ_anual = (E_janela − R_janela) × 360 / dias_da_janela   # déficit anualizado (≤ 0 = superávit)
Δ_proj  = Δ_anual + C_360
exigido: Δ_proj ≤ teto% × R_ref
```

`C_360` = valor que o **novo compromisso discricionário** representa em pagamentos **dentro do horizonte projetado de 360 dias** (cronograma de pagamento do próprio compromisso; recorrente conta as parcelas do horizonte).

**Receita (R)**: dinheiro efetivamente recebido por impostos (União), **transferências recebidas** (Estados e Municípios; contam como receita do destinatário), leilões de lote (Município), liberação de retenção ao caixa federal e demais receitas não financeiras. **Não contam**: dotações iniciais de cenário, **emissão de títulos** e **dinheiro ainda retido**.

**Despesa (E)**: dinheiro efetivamente pago em despesas reais (obras, salários, soldo, subsídios, campanhas, **juros pagos**...). **Não contam**: **transferências feitas a níveis inferiores** (não são nova despesa econômica para o remetente) e **amortização do principal** da dívida.

**Efeito**:

- O teto limita **novas despesas discricionárias** (`09` §13, §31). Recusa, redução, adiamento ou alteração para compensar; **financiar por dívida não torna legal** a despesa que passa do limite.
- **Salários, obrigações existentes, contratos já assumidos e despesas constitucionais não são recusados** por esta regra, mas **continuam compondo** o déficit. Passar do teto bloqueia só as novas discricionárias (`09` §24).
- **Menos de 30 dias de histórico**: o teto ainda **não bloqueia**; restrições de caixa, reservas (§24.7) e dívida continuam valendo.
- **Dívida**: a emissão de títulos fornece liquidez com dinheiro de compradores reais, **não reduz o déficit calculado** e **não permite contornar o teto**; é fonte de financiamento de caixa, não receita fiscal.
- Teto 0% = nenhuma discricionária nova que aumente o déficit anualizado; teto 50% = permite chegar a metade da receita de referência.
- Explicabilidade (`20`): `Explained` com `R_ref`, `Δ_anual`, `C_360`, `Δ_proj`, teto, folga, dias da janela e o que restringiu.

---

## 24.17. Integridade, auditoria e métricas

**Invariantes** (verificadas por `audit_ledger` e por testes):

1. soma de todos os saldos = 0;
2. nenhuma conta comum com saldo < 0; `ISSUANCE` ≤ 0 e só se altera por `SCENARIO_GRANT`;
3. saldo guardado = soma dos lançamentos de cada conta (reconstrução do log);
4. `emitido_total = saldos brutos operacionais + retenções + sumidouro` (reservas **não** entram na fórmula, §24.3.3);
5. `SINK` nunca é origem;
6. lançamentos **e transações** imutáveis (sem `UPDATE`/`DELETE` por instância, `QuerySet.update/delete`, `bulk_update`, `update_or_create` ou `bulk_create` com *upsert*; teste tenta e falha);
7. toda transação com todas as pernas ou nenhuma; `seq` sem lacuna lógica;
8. cada `key` de idempotência aparece uma vez;
9. nenhuma reserva ativa maior que o saldo bruto; nenhuma obrigação paga acima do devido;
10. `C_S` e `C_T` do dia = soma das remunerações reconhecidas naquela competência;
11. remuneração só por `submit_remuneration`/`liquidate_remuneration`; nenhuma natureza fora da lista;
12. todo lançamento tem natureza, origem, destino e referência (`REFERENCE_REQUIRED`); estorno, retenção, liberação e dotação preservam as contrapartidas e apontam o original;
13. `SINK` nunca é origem; só `SCENARIO_GRANT` tem origem `ISSUANCE`; título e empréstimo **transferem** dinheiro de contas existentes;
14. o conjunto reconhecido em um lote de remuneração é **invariante à permutação** dos pedidos (§24.12.4);
15. todo valor de enumeração gravado (tipo de conta, natureza, estado, política) está no domínio; um valor inválido é **achado estruturado**, nunca exceção (a auditoria roda cada seção isolada e converte falha inesperada em achado `AUDIT_SECTION_FAILED`);
16. os metadados de cada transação conferem com seus lançamentos: chave não vazia, instante e ator, referência e dia iguais em todas as pernas, `payload_hash` = hash de `payload.request`, `payload.request` (pernas, referência, estorno) = o que foi gravado, e `payload.competence_day` (dia efetivo) = o dia de **todos** os lançamentos, sempre;
17. o consumo de reservas registrado nas transações (`payload.request.uses`, somado por reserva) é igual a `original_amount − amount` de cada reserva; reserva inexistente, reserva de outra conta ou `uses` malformado são achados estruturados;
18. toda emissão (`SCENARIO_GRANT`) corresponde a uma dotação explícita do cenário, reconferida só pelo log e pela configuração (a auditoria não confia no serviço): cenário existente (`GRANT_SCENARIO_UNKNOWN`), `explained.scenario` igual à referência (`GRANT_EXPLAINED_MISMATCH`), chave `grant:<cenário>:<conta>` (`GRANT_KEY_MISMATCH`), transação de uma só perna (`GRANT_TRANSACTION_NOT_SINGLE`), uma só dotação por (cenário, conta) (`GRANT_DUPLICATE`), papel gravado e conhecido (`GRANT_ROLE_INVALID`), compatível com o tipo da conta de destino (`GRANT_ROLE_ACCOUNT_MISMATCH`), linha existente (`GRANT_LINE_MISSING`) e valor igual ao da linha (`GRANT_AMOUNT_MISMATCH`). O estado *ativo* do cenário não é reconferido (muda depois da emissão); quem o exige é o serviço, na hora de emitir.

**Comandos** (P0.07b): `audit_ledger` (invariantes, exit code ≠ 0 se falhar) e `ledger_metrics` (emissão, circulação, retido, sumidouro, por tipo de conta, uso dos contadores). Logs estruturados e exportáveis (`CLAUDE.md` §8).

**Desempenho** (`CLAUDE.md` §9): o registro mede tempo de transação, conflitos de travamento e contas mais disputadas; permite agrupar vários pagamentos de um mesmo pagador numa transação (folha diária) quando o gargalo for medido.

---

## 24.18. Integração com os sistemas existentes

- **Viagem (P0.06.1)**: o serviço já expõe `register_payment_handler`. A P0.07b registra o handler do registro: jogador → `UNION`, natureza `TRAVEL_FEE`, `key = travel:<jogador>:<instante>:<origem>:<destino>` (o pagamento acontece antes de a `Journey` existir, então não há id da viagem; a chave composta identifica a partida), preenchendo `Journey.charged`. O handler só cobra **enquanto houver cenário monetário ativo**; sem cenário, a viagem se comporta como antes (calcula e registra, não cobra). `check_action` consulta o saldo (`quote`) e devolve `INSUFFICIENT_FUNDS` sem cobrar. Sem o registro, nada muda hoje (viagem calcula e não cobra).
- **Action Registry (P1.03)**: `check_action` usa `can_afford`/`quote` e informa `INSUFFICIENT_FUNDS` com `Explained` **antes** de executar; a execução usa os mesmos serviços para humanos e Bots.
- **Jogador**: a conta é criada com o jogador (`ensure_account`) e recebe a dotação do cenário; o registro **não** altera o modelo de jogador.
- **Tratamento (P0.04)**: hoje pendente "do sistema de dinheiro" (CHANGELOG). Será ligado quando existir um prestador ou hospital que receba o pagamento (`04` §13); o registro só recebe a conta de destino.
- **Catálogo (P0.02)**: `base_price` serve de **valor de referência** (taxa do correio), nunca como preço de mercado; o registro não o usa.

---

## 24.19. Escopo e critérios de aceitação da P0.07b

**Entrega** (app `ledger`, sem depender de Empresas, Mercado ou Orçamento):

1. contas, lançamentos, transações, estorno, auditoria e imutabilidade;
2. conservação, precisão em centavos, `MAX_AMOUNT`, idempotência, ordem de travamento;
3. reservas e obrigações pendentes (com quitação determinística);
4. contadores `C_S`/`C_T`/`C_P`, submissão e **liquidação estável** de remuneração (`submit_remuneration`/`liquidate_remuneration`), com `Explained`;
5. dotações de cenário e recusa por valor ausente (`SCENARIO_GRANT_UNSPECIFIED`);
6. sumidouro, **retenções genéricas** e a **interface de roteamento tributário** (`register_tax_resolver`/`route_tax`), sem importar módulos militares (a ligação com ações de milícia é da P1.17);
7. handler de pagamento da viagem; `audit_ledger` e `ledger_metrics`.

**Fora** da P0.07b: caixa de empresa (P1.04), mercado e correio (P1.02/P1.05), orçamento, categorias e dívida (P1.09), teto de déficit, contratos (P1.08), milícias e Exército (P1.17), cenário completo (P1.18).

**Testes obrigatórios**: caminho normal; limites (`MAX_AMOUNT`, 1 centavo, valores não inteiros em centavos); permissões (naturezas proibidas, origem `SINK`, emissão por natureza errada); estados inválidos (conta encerrada, mesma conta); efeitos econômicos (conservação após cada operação, em teste de propriedade com sequências aleatórias); idempotência (repetição e conflito); atomicidade (falha na 2ª perna não deixa a 1ª); concorrência (dois pagamentos disputando o mesmo saldo); reservas e obrigações (ordem de quitação, parcial, nunca cria dinheiro); contadores (**permutar a ordem dos pedidos de um lote e verificar que o conjunto reconhecido é o mesmo**; ordem política × não política; reserva política consumida/liberada sem dupla subtração; `W` > `S`; `T` binding; soldo excedente descartado; dia de competência; lei que muda depois do lançamento); retenção genérica (valor nunca nos dois lados; liberação ao destino escolhido; destino inexistente recusa); roteamento tributário (padrão União; resolvedor registrado; ambiguidade recusa); invariante `emitido = brutos + retenções + sumidouro` com reservas ativas; dotação (zero explícito, ausente recusa, idempotência por conta); auditoria reconstrói saldos e detecta adulteração direta no banco.

### 24.19.1. Decisões técnicas da implementação (P0.07b; não alteram a mecânica)

- **Pedido sem caixa, política `PENDING`**: se o disponível do pagador não cobre o pagamento (líquido + imposto que sai da conta), o pedido reconhecido vira **uma obrigação do valor bruto inteiro**, sem pagamento parcial na liquidação; a quitação parcial é feita depois por `settle_obligations`, que recolhe o imposto em parcelas proporcionais (arredondado uma vez; a última fecha o resto). Se há caixa, paga na hora, mesmo havendo obrigações antigas de outros pedidos.
- **Política `REFUSE`** não altera nenhum contador: o limite que sobrar vale para o pedido seguinte da mesma sequência.
- **Pedido que não cabe em nenhum limite** (reconhecido 0) fica processado (`NO_ROOM`) e não é reaproveitado; para pedir de novo, usa-se nova `key`.
- **Roteamento tributário ambíguo ou inválido durante uma liquidação** desfaz o **lote inteiro** (nada é reconhecido nem pago): é erro de configuração, não de um pedido.
- **Provedor de limites ausente** (`register_limits_provider`): a liquidação recusa com `REMUNERATION_LIMITS_UNSPECIFIED`; o registro não inventa `W`, `S` nem `T`.
- **Viagem**: o handler só cobra com cenário monetário ativo (§24.18).
- **Banco**: o saldo não-negativo (exceto `ISSUANCE`) também é restrição do banco de dados (defesa em profundidade).
- **Emissão (correção do bloqueio P0, 2026-10-17; interpretações a confirmar pelo GD)**: (1) o mapa papel → tipo de conta do §24.11 é fechado nos cinco papéis que o próprio §24.11 nomeia, e **empresas não são papel de dotação**; (2) "cenário autorizado a emitir" = cenário **ativo**; (3) linha que já gerou dotações não muda de valor. Os testes (que usam contas de empresa) registram um papel só de teste por `mock.patch.dict`; o mapa de produção não muda.
- **Concorrência**: em PostgreSQL as contas são travadas com `SELECT ... FOR UPDATE` em ordem de id; em SQLite o banco serializa as escritas. Os testes verificam a propriedade (um só vencedor, saldo nunca negativo, conservação, mesma chave devolve a original, consumo de reserva uma só vez) nos dois. A suíte foi executada de fato em PostgreSQL 16 (ver `CHANGELOG_DEV.md`); para repetir, defina `DATABASE_URL` para um PostgreSQL com codificação UTF8 e `POLIS_EXPECT_DB=postgresql` (o teste `test_runs_on_the_expected_database` falha se a suíte não estiver rodando em PostgreSQL, evitando declarar cobertura que não houve).
  Os testes de **ordem estrita** da configuração de cenários (`PostgresLockOrderTests`: uma thread segura o bloqueio e a outra tem de esperar e terminar depois) só rodam em PostgreSQL e são **pulados** em SQLite; em SQLite valem apenas os testes de propriedade (emitido coerente com a linha final, no máximo um cenário ativo, auditoria limpa).

---

## 24.20. Interpretações técnicas R1–R10 (aprovadas pelo GD em 2026-10-15, com ajustes)

Nenhuma altera mecânica de design.

| Id | Interpretação aprovada |
|---|---|
| R1 | Os contadores medem a remuneração **bruta** reconhecida; o imposto divide o valor entre o líquido ao jogador e a conta tributária. Caixa insuficiente é responsabilidade do sistema pagador |
| R2 | Padrão para P1.05/P1.08: o comprador paga o preço anunciado; o imposto é **retido do valor da venda** e reduz o líquido do vendedor. Quando o comprador é o governo federal e o destino do imposto é a própria União, **não há transferência de uma conta para ela mesma**; o cálculo e a compensação ficam no `Explained` e na auditoria, **sem lançamento fictício** |
| R3 | Salário político reconhecido no tick diário para o ocupante elegível; o substituto **não recebe retroativo** por períodos anteriores à posse; `P_reservada` acompanha o ocupante e é **reduzida pelo valor político reconhecido** (§24.12.2), para não ser descontada duas vezes |
| R4 | Quitação de obrigações do mesmo devedor: competência mais antiga, depois id da obrigação |
| R5 | Base dos pisos municipais: leilões de lote público + transferências efetivamente recebidas. Atribuição territorial de impostos federais é **rastreamento**, não receita municipal; outro tipo de receita municipal futura entra na base **só de forma explícita** |
| R6 | Centavos inteiros; `HALF_EVEN`; última perna é o resto; `MAX_AMOUNT = 10^15` centavos `[PROV]` |
| R7 | Reserva (valor fica na conta do dono, indisponível) x retenção (valor vai para custódia) |
| R8 | Município = `City` do `08`; Estado = `State` |
| R9 | Saldo guardado é cache; o histórico imutável de lançamentos é a verdade e o comando de auditoria reconstrói os saldos |
| R10 | Fundação de milícia debitada da conta do fundador; melhorias debitadas do banco da milícia; ambas ao sumidouro |

**Questões deixadas para tarefas seguintes (não bloqueiam a P0.07b)**:

- **P1.04**: política de caixa insuficiente da empresa no salário (`PENDING` ou `REFUSE`); capital inicial da empresa (transferência do dono, não dinheiro novo); produtor do Exército = Industrial/Produção (decidido).
- **P1.05/P1.08**: aplicar R2; quando o imposto de uma Requisição Especial é cobrado (recomendado: na liberação do escrow).
- **P1.06**: conta da escola particular (jogador dono ou empresa).
- **P1.09/P1.12**: categorias orçamentárias, comprometimento, serviço da dívida e **implementação** do teto de déficit (§24.16).
- **P1.11**: provedor do salário político devido (§24.12.1).
- **P1.17**: resolvedor tributário e uso de `release_retention` (§24.10.3).

---

## 24.21. Dependências

`01` (S), `02` (empresas, fundação), `04` (tratamento, viagem), `05` (correio), `06`/`11` (salários, campanhas, leis), `09` (orçamento), `10` (leilão, aluguel, IPTU), `18` (contratos), `19` (milícia, Exército, retenção), `20` (`Explained`), `21` (cenário, métricas).

---

## 24.22. Status

FINAL — BOT TEST (aprovado pelo Game Director em 2026-10-15). Libera a P0.07b.
