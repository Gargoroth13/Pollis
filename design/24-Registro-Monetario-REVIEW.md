# 24 — Registro Monetário (Ledger)

**Status: REVIEW — documento de design da P0.07a, aguardando aprovação do Game Director.** Nenhum código foi escrito. A implementação (P0.07b) só começa depois da aprovação.

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

### 24.3.3. Conservação em fórmula

```text
soma(saldo de TODAS as contas, incluindo ISSUANCE) = 0
emitido_total = −saldo(ISSUANCE)
emitido_total = disponível + retido + sumidouro
```

- **disponível** = soma dos saldos de `PLAYER`, `COMPANY`, `UNION`, `STATE`, `MUNICIPALITY`, `MILITIA_BANK` (menos reservas, quando se quer o *líquido*);
- **retido** = soma dos saldos de `RETENTION` (dinheiro que existe e voltará a circular);
- **dinheiro em circulação** (Q2) = disponível + retido, **excluído** o sumidouro.

---

## 24.4. Precisão e limites técnicos

- Todo valor é **inteiro em centavos** (`BigInteger`). O serviço aceita `Decimal` e **recusa** quem não está exatamente em centavos (`AMOUNT_NOT_IN_CENTAVOS`), em vez de arredondar sem avisar. Float é proibido (igual a `core.breakdown`).
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
| `reference_kind`, `reference_id` | Fato gerador: `scenario`, `law`, `project`, `contract`, `journey`, `action`, `obligation`, `hold`, `bond`... |
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
| `accrue_remuneration` | Remuneração com limites S/T (§24.12) |
| `grant_scenario_allocation` | Dotação (§24.11) |
| `retain` / `release_retention` | Retenções (§24.10) |
| `route_tax` | Destino do imposto de uma venda (§24.10.3) |
| `reverse(entry, reason)` | Estorno técnico, auditado |

`transfer` **recusa** as naturezas de remuneração (`NATURE_REQUIRES_PAYROLL`): salário, soldo, salário de Dono e salário político só passam por `accrue_remuneration`, para que ninguém contorne os contadores.

### 24.5.3. Atomicidade, concorrência e idempotência

- Cada transação roda em **uma transação de banco**. Falha em qualquer perna desfaz todas.
- **Ordem de travamento**: as contas envolvidas são travadas em **ordem crescente de id** (evita *deadlock*). O saldo é lido e gravado sob esse travamento.
- **Idempotência**: toda requisição traz uma `key` única do chamador (ex.: `travel:{journey_id}`, `grant:{scenario}:{account}`, `wage:{player}:{day}:{company}:{n}`). Repetir a mesma `key` com o mesmo conteúdo devolve o resultado original (`already_posted=True`) sem novo efeito. A mesma `key` com conteúdo diferente recusa com `IDEMPOTENCY_CONFLICT`.
- **Falha de caixa**: `INSUFFICIENT_FUNDS` com `Explained` (saldo, reservas, disponível, valor pedido, falta). Nada é gravado.
- **Hot account**: a `UNION` recebe quase todo imposto e taxa e será a linha mais disputada. Na primeira versão há **um único travamento por conta** e o gargalo é **medido** (`CLAUDE.md` §9) antes de otimizar; a interface não muda se for preciso fatiar o caixa federal depois (risco R-LEDGER-01).

---

## 24.6. Estorno

Erro técnico (não regra de jogo) se corrige com `REVERSAL`: novo lançamento no sentido oposto, mesmo valor, `reverses=<seq>`, motivo obrigatório e ator registrado. O original **permanece**. Um lançamento só pode ser estornado uma vez e só se o destino ainda tiver saldo; senão, recusa (`REVERSAL_NOT_POSSIBLE`) e o caso vira tratamento manual registrado. Estorno **não** é mecânica de jogo (devolução de compra, reembolso etc. são lançamentos normais de natureza `REIMBURSEMENT`).

---

## 24.7. Reservas (`Hold`)

Uma reserva marca um valor da **própria conta** como indisponível, sem movê-lo.

```text
saldo_disponível = saldo − soma(reservas ativas)
```

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

### 24.10.3. Retenção de arrecadação durante ação de milícia (`19` 19.16, `09` §45.6)

- Existe **uma conta `RETENTION` por ação de milícia** sobre uma região.
- Função única `route_tax(territory, at)` devolve o destino de qualquer imposto: **caixa federal**, ou a conta de retenção da ação **ativa** que cobre a região do imposto (atribuição territorial, `09` §45.5). Nenhum sistema escolhe o destino por conta própria.
- Só o imposto **efetivamente arrecadado** e vinculado à região **durante** a ação é retido; os 30 dias anteriores não são retirados retroativamente.
- Encerramento (decidido pelo sistema militar): **vitória da milícia** → `RETENTION_RELEASE` ao banco da milícia; **repressão, derrota ou falha** → `RETENTION_RELEASE` ao caixa federal. Nada fica em custódia depois do encerramento. Se o destino não existir ou estiver encerrado, o registro recusa e o estado fica pendente e auditável; ele não escolhe um beneficiário novo ("nenhum beneficiário é inventado").

### 24.10.4. Sumidouro (Q2)

- Só **recebe** (`SINK_NOT_SPENDABLE` para qualquer lançamento que o tenha como origem). Seus lançamentos nunca são apagados.
- Recebe: **fundação de milícia** (pago pela conta do fundador, não há banco ainda) e **melhorias** (pagas pelo banco da milícia) — `MILITIA_FOUNDING`, `MILITIA_UPGRADE`; **custos de campanhas** (`CAMPAIGN_COST`), pagos pelo **caixa federal**, depois de reservados (§24.7).
- Seu saldo faz parte da conservação (§24.3.3) e é **excluído** do dinheiro em circulação; aparece nas métricas como "destruído por custo de jogo".

---

## 24.11. Dotações de cenário (origem do dinheiro, Q1)

- **Única fonte de dinheiro novo**: lançamento `ISSUANCE → conta`, natureza `SCENARIO_GRANT`, referência `scenario:<id>`.
- O cenário declara, **explicitamente**: dotação inicial por conta de jogador (humano ou Bot), saldos iniciais da União, dos Estados e dos Municípios, bancos de milícia e demais saldos iniciais de governo (`21` 21.60). Cada valor é uma linha de configuração com `valor` ou `UNSPECIFIED`.
- **Zero é válido** quando escolhido explicitamente (linha com valor 0; não gera lançamento, mas fica registrado). **Valor ausente** (`UNSPECIFIED`) faz o cenário que depende dele **recusar a inicialização** com `SCENARIO_GRANT_UNSPECIFIED`, listando as pendências. Nenhum valor é inventado pelo desenvolvimento.
- **Conta nova depois do início** (Bot criado pelo controlador de população, humano novo): recebe a dotação configurada, **idempotente** por `grant:<cenário>:<conta>` (uma vez por conta).
- **Sem emissão periódica discricionária**: nenhum cargo, lei, orçamento, título ou transferência emite dinheiro. Qualquer lançamento com origem `ISSUANCE` e natureza diferente de `SCENARIO_GRANT` é **erro de integridade** (verificado pela auditoria e por teste).
- **Métricas** (Dashboard de Bots e finanças): emissão total, emissão por cenário/período, número de contas contempladas, dinheiro em circulação, retido e no sumidouro.
- **Itens** (estoque inicial de equipamentos, `19`/`21` 21.60): a dotação de itens segue o mesmo padrão (explícita, auditável, com cenário como referência), mas pertence ao Inventário/Empresas; **não** é dinheiro e não passa por este registro.

---

## 24.12. Remuneração: contadores `C_S` e `C_T`

Implementa 11.1.0 **sem alterar** a regra aprovada.

### 24.12.1. Dados

`(jogador, dia_de_competência)` guarda `C_S` e `C_T` em centavos. Parâmetros lidos no instante do lançamento: `W` (salário mínimo), `S = 1.5 × skill relevante` (`skills.balance`, `[PROV]`; Físico para soldo), `T` (teto legal; `∞` se não houver). Leis passam a valer no instante de vigência (D15): um valor já lançado **não é recalculado** quando a lei muda.

### 24.12.2. Cálculo (determinístico)

```text
cap_S   = max(W, S)
sobra_S = cap_S − C_S
sobra_T = T − C_T − P_reservada            # T = ∞ → sem limite
pagável_não_político = max(0, min(devido, sobra_S, sobra_T))
pagável_político     = max(0, min(devido_político, T − C_T))
```

- `P_reservada` = salário político **do dia** ainda não lançado para aquele jogador. Ele é **reservado desde o início do dia** em `sobra_T`, então o resultado da remuneração não política **não depende da ordem** em que os serviços pagam em relação ao salário político.
- Entre remunerações **não políticas** do mesmo jogador no mesmo dia vale a **ordem do registro** (`seq`); em obrigações, o desempate é o id da obrigação.
- `W` prevalece sobre um `S` menor, mas **não cria dinheiro** e **não ultrapassa `T`**.
- **Soldo**: `devido = W × m_patente` (Militar 1×, Capitão 2×, General 4×, Marechal 6×, `[PROV]`, parâmetros do sistema, não leis). O excedente acima do pagável **não é pago e não vira obrigação**.
- Sem salário político: `pagável/dia = max(W, min(S, T))` (pois `T ≥ W`), como em 11.1.0.

### 24.12.3. Competência e pagamento

- **O contador conta o valor reconhecido (acumulado) no dia de competência**, não quando o dinheiro sai. O limite é aplicado **uma vez**, na competência; pagar depois (obrigação quitada) **não** reaplica limite nem altera contador de outro dia.
- Fluxo de `accrue_remuneration(pagador, jogador, natureza, devido, dia, política, key)`:
  1. calcula o pagável e o `Explained` (§24.14);
  2. incrementa `C_S`/`C_T` do dia **na mesma transação** do pagamento;
  3. se o pagador tem caixa → transfere; se não, aplica a **política declarada pelo sistema de origem**: `PENDING` (cria obrigação) ou `REFUSE` (nada é reconhecido, devolve `INSUFFICIENT_FUNDS`).
- **Política por tipo de remuneração**: salário político → `PENDING` (aprovado). Salário de trabalho em empresa e do cargo Dono → **a decidir pela P1.04** (o `02` não diz o que acontece quando o caixa da empresa não cobre o salário; o registro suporta as duas políticas). Soldo e salário de servidores públicos → **a decidir pela P1.17/P1.09** (`09` §13 os classifica como despesa obrigatória; o registro suporta `PENDING` e `REFUSE`); o soldo excedente já foi descartado antes.
- **Imposto de renda** (`11`: "reduz o salário líquido recebido"): o valor reconhecido nos contadores é o **bruto pagável**; o pagador paga o bruto, dividido numa transação em **líquido ao jogador + imposto à `route_tax`** (R1).
- **Dia**: dia de jogo (`core.timeline`, fuso do jogo). Não há acúmulo entre dias.
- **Salário político**: acumula **uma vez por dia de jogo, no tick diário, para o ocupante naquele instante**; o substituto passa a acumular a partir da posse. A `P_reservada` acompanha o ocupante (R3). Se o jogador já consumiu `T` antes de tomar posse naquele dia, o pagável político é o que sobra (fórmula acima); o caso é raro e fica visível no `Explained`.
- Salário político e do Dono: pagador é a conta do governo/empresa correspondente (`09` §45.4: União paga Presidente e Deputados; Estado, Governador; Município, Prefeito).

### 24.12.4. Validações de `T`

As validações de proposta (`T ≥ W`; `T ≥ maior salário político vigente`) pertencem a `11`/P1.12; o registro **não** as repete, mas **nunca** produz pagável negativo se estiverem violadas (usa `max(0, …)`).

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

---

## 24.16. Proposta: teto de déficit público (para decisão do Game Director)

`11` mantém o parâmetro "Teto de déficit público" (Federal, 0%–50%, padrão 10%, "déficit máximo permitido como % da receita anual de referência") como `[ABERTO]`, à espera desta arquitetura. **Proposta**, sem inventar mecânica nova além de definir os termos já citados:

**Definições** (para cada governo: União, cada Estado, cada Município; o parâmetro federal vale igual para todos):

- **Receita** (R) = dinheiro **efetivamente recebido** na conta do governo por: impostos (União), transferências recebidas (Estados e Municípios), leilões de lote (Município), liberação de retenção ao caixa federal e demais receitas de natureza não financeira. **Não** conta: dotação de cenário, venda de títulos (financiamento) nem retenção ainda não liberada.
- **Despesa** (E) = dinheiro **efetivamente pago** em despesas reais: obras, salários, soldo, subsídios, serviço da dívida (juros), campanhas etc. **Não** conta: repasses a níveis inferiores (são alocação de receita; o nível receptor os conta como receita) nem amortização de principal de título.
- **Janela de referência**: últimos **360 dias de jogo (12 períodos de 30 dias)**, ou desde a abertura da conta se menor, **com mínimo de 30 dias**. `R_ref` = receita da janela **anualizada** (`R_janela × 360 / dias_da_janela`).
- **Déficit** `Δ` = `E_janela − R_janela`, anualizado do mesmo jeito (`Δ ≤ 0` = superávit).

**Regra**:

```text
Δ_projetado = Δ + valor de novos compromissos DISCRICIONÁRIOS que a decisão cria
exigido:     Δ_projetado ≤ teto% × R_ref
```

- Vale **na aprovação de novas despesas discricionárias** (`09` §13, §31: projetos, subsídios novos, campanhas, investimentos). Se não cumprir: **recusa, redução, adiamento ou financiamento por dívida dentro do limite** (as opções de `09` §31).
- Despesas **obrigatórias** (salários, serviço da dívida, contratos já assinados, constitucionais) **nunca** são recusadas pelo teto, mas contam em `Δ`. Passar do teto bloqueia só as novas discricionárias (`09` §24), sem criar dinheiro.
- Com menos de 30 dias de histórico a regra **não bloqueia** (não há receita de referência), mas as restrições de caixa (saldo disponível, §24.7) e de `09` §31 continuam valendo.
- Teto 0% = nenhuma discricionária nova que aumente o déficit; teto 50% = permite chegar a metade da receita anual de referência.
- Explicabilidade: `Explained` com `Δ`, `R_ref`, teto, `Δ_projetado`, folga e o que restringiu.

**Decisão pedida ao GD**: aprovar, alterar ou rejeitar esta definição (janela de 360 dias anualizada; exclusão de repasses, financiamento e dotações; só discricionárias são bloqueadas). **Alternativa** (se preferir mais simples): usar só o período orçamentário de 30 dias (`09` §8), com `Δ_30d ≤ teto% × R_30d`; é mais fácil de explicar e mais sensível a oscilações. A recomendação é a janela de 360 dias, por casar com o texto de `11` ("receita anual"). A implementação é da P1.09/P1.12, **não** da P0.07b; sem decisão, o parâmetro continua não implementado.

---

## 24.17. Integridade, auditoria e métricas

**Invariantes** (verificadas por `audit_ledger` e por testes):

1. soma de todos os saldos = 0;
2. nenhuma conta comum com saldo < 0; `ISSUANCE` ≤ 0 e só se altera por `SCENARIO_GRANT`;
3. saldo guardado = soma dos lançamentos de cada conta (reconstrução do log);
4. `emitido_total = disponível + retido + sumidouro`;
5. `SINK` nunca é origem;
6. lançamentos imutáveis (sem `UPDATE`/`DELETE` via serviço; teste tenta e falha);
7. toda transação com todas as pernas ou nenhuma; `seq` sem lacuna lógica;
8. cada `key` de idempotência aparece uma vez;
9. nenhuma reserva ativa maior que o saldo; nenhuma obrigação paga acima do devido;
10. `C_S` e `C_T` do dia = soma das remunerações reconhecidas naquela competência;
11. remuneração só por `accrue_remuneration`; nenhuma natureza fora da lista.

**Comandos** (P0.07b): `audit_ledger` (invariantes, exit code ≠ 0 se falhar) e `ledger_metrics` (emissão, circulação, retido, sumidouro, por tipo de conta, uso dos contadores). Logs estruturados e exportáveis (`CLAUDE.md` §8).

**Desempenho** (`CLAUDE.md` §9): o registro mede tempo de transação, conflitos de travamento e contas mais disputadas; permite agrupar vários pagamentos de um mesmo pagador numa transação (folha diária) quando o gargalo for medido.

---

## 24.18. Integração com os sistemas existentes

- **Viagem (P0.06.1)**: o serviço já expõe `register_payment_handler`. A P0.07b registra o handler do registro: jogador → `UNION`, natureza `TRAVEL_FEE`, `key = travel:<journey_id>`, preenchendo `Journey.charged`. Sem o registro, nada muda hoje (viagem calcula e não cobra).
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
4. contadores `C_S`/`C_T` e `accrue_remuneration`, com `Explained`;
5. dotações de cenário e recusa por valor ausente (`SCENARIO_GRANT_UNSPECIFIED`);
6. sumidouro e retenções (contrato e ação militar), `route_tax`;
7. handler de pagamento da viagem; `audit_ledger` e `ledger_metrics`.

**Fora** da P0.07b: caixa de empresa (P1.04), mercado e correio (P1.02/P1.05), orçamento, categorias e dívida (P1.09), teto de déficit, contratos (P1.08), milícias e Exército (P1.17), cenário completo (P1.18).

**Testes obrigatórios**: caminho normal; limites (`MAX_AMOUNT`, 1 centavo, valores não inteiros em centavos); permissões (naturezas proibidas, origem `SINK`, emissão por natureza errada); estados inválidos (conta encerrada, mesma conta); efeitos econômicos (conservação após cada operação, em teste de propriedade com sequências aleatórias); idempotência (repetição e conflito); atomicidade (falha na 2ª perna não deixa a 1ª); concorrência (dois pagamentos disputando o mesmo saldo); reservas e obrigações (ordem de quitação, parcial, nunca cria dinheiro); contadores (ordem política × não política não altera o resultado; `W` > `S`; `T` binding; soldo excedente descartado; dia de competência; lei que muda depois do lançamento); retenção (valor nunca nos dois lados; liberação para o destino correto; sem retroatividade); dotação (zero explícito, ausente recusa, idempotência por conta); auditoria reconstrói saldos e detecta adulteração direta no banco.

---

## 24.20. Interpretações técnicas registradas (padrões adotados; ratificáveis na aprovação)

Nenhuma altera mecânica aprovada. Cada uma é o padrão que a P0.07b usará **salvo objeção do GD**:

| Id | Interpretação |
|---|---|
| R1 | Os contadores `C_S`/`C_T` medem a remuneração **bruta** reconhecida; o imposto de renda é uma divisão do bruto pago pelo pagador (líquido ao jogador, imposto à União/retenção) |
| R2 | O registro é **neutro quanto à incidência** do imposto sobre vendas: quem chama informa as pernas. Recomendação para P1.05/P1.08: o imposto é **retido do valor da venda** (o comprador paga o preço anunciado; o vendedor recebe preço − imposto), coerente com "reduz margens" em `11`. Compra do governo federal: a perna de imposto da União para a União **não gera lançamento** (fica no `Explained`) |
| R3 | Salário político acumula uma vez por dia de jogo, no tick diário, para o ocupante naquele instante; `P_reservada` acompanha o ocupante |
| R4 | Ordem de quitação de obrigações do mesmo devedor: competência mais antiga, depois id |
| R5 | Base dos pisos municipais (`09` §45.3): "arrecadação própria" do Município = leilões de lote público; "transferências efetivamente recebidas" = repasses estaduais. Imposto atribuído por território (§45.5) é só rastreio e **não** compõe a base |
| R6 | Centavos inteiros; arredondamento `HALF_EVEN` uma vez; última perna é o resto; `MAX_AMOUNT = 10^15` centavos `[PROV]` |
| R7 | Reserva (mesma conta) e retenção (conta de custódia) são mecanismos distintos, com usos distintos (§24.7) |
| R8 | "Município" do `09` = `City` do `08`; "Estado" = `State` |
| R9 | A auditoria trata o saldo guardado como cache; a verdade é o log |
| R10 | Fundação de milícia (`19` 19.7.1, "custo monetário"): o pagador é a conta do fundador, único dono existente no momento; melhorias saem do banco da milícia (`19` 19.8) |

**Questões deixadas para tarefas seguintes (não bloqueiam a P0.07b)**:

- **P1.04**: o `02` não diz o que ocorre quando o caixa da empresa não cobre um salário (política `PENDING` ou `REFUSE`); e como a empresa vira conta (fundação debita o fundador e credita a União; o capital inicial da empresa vem de transferência do dono, não de dinheiro novo).
- **P1.05/P1.08**: incidência do imposto sobre vendas (R2) e quando o imposto de uma Requisição Especial é cobrado (recomendado: na liberação do escrow).
- **P1.06**: conta da escola particular (jogador dono ou empresa).
- **P1.09**: categorias orçamentárias, comprometimento, serviço da dívida e o teto de déficit (§24.16).

---

## 24.21. Dependências

`01` (S), `02` (empresas, fundação), `04` (tratamento, viagem), `05` (correio), `06`/`11` (salários, campanhas, leis), `09` (orçamento), `10` (leilão, aluguel, IPTU), `18` (contratos), `19` (milícia, Exército, retenção), `20` (`Explained`), `21` (cenário, métricas).

---

## 24.22. Status

REVIEW — P0.07a. Ao ser aprovado pelo Game Director, passa a **FINAL — BOT TEST** e libera a P0.07b.
