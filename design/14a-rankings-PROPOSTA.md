# 14a — Rankings: implementação da P1.15a (fatia 1) — mapa de fontes, interpretações e proposta técnica de QoL (PROPOSTA)

**Status:** PROPOSTA — documento de apoio ao `14 — Rankings` (FINAL — BOT TEST). Nada aqui altera o design. Cada linha é uma lacuna **técnica** onde o `14` é
silencioso, a escolha feita para não bloquear e o que o Game Director pode revisar. O `14` continua **FINAL — BOT TEST** (só vira IMPLEMENTED depois de integrado e validado na `main`).

## 1. Mapa de fontes (numeração: ao vivo 1–11 = 14.3.1–14.3.11; históricas 12–15 = 14.4.1–14.4.4)

| # | Ranking | Métrica / regra | Fonte | Está na `main`? | Estado na fatia 1 |
|---|---|---|---|---|---|
| 1 | Maior patrimônio líquido | saldo bruto da conta − obrigações em aberto (só o que o ledger reconhece) | `ledger.Account.balance`, `ledger.Obligation` | sim | **ativo** |
| 2 | Maior empresa | estrelas; desempate: funcionários | empresa (P1.04a/b, PRs #15/#16) | não | pendente de fonte (fatia 2) |
| 3 | Maior produção (14 dias) | quantidade efetivamente produzida **por produto**, na unidade do produto | registro de produção (P1.04c, PR #17) | não | pendente de fonte (fatia 2) |
| 4 | Melhor QoL pessoal | QoL atual comparável entre jogadores | `players.qol` (função do estado, não guardada) | função sim; valor comparável não | **pendente de decisão** (§4) |
| 5 | Maior influência política | — | — | — | **fora do Bot Test** (14.3.5, 14.10) |
| 6 | Maior empregador | por empresa: funcionários da empresa (o Dono não conta); por jogador: soma das empresas que possui | vínculos/propriedade (P1.04a/b) | não | pendente de fonte (fatia 2) |
| 7 | Maior contribuinte (30 dias) | imposto efetivamente pago | `ledger.Entry` (`tax_*`, não estornado) | sim | **ativo** |
| 8 | Melhor escola/universidade | qualidade atual da instituição | `QualityDay` (P1.06a, PR #21) | não | pendente de fonte (fatia 3) |
| 9 | Maior organização | membros da milícia (a contagem, não a composição) | P1.17 | não | pendente de fonte (fatia 4) |
| 10 | Conta mais antiga | agora − criação da conta | `players.Player.created_at_game` | sim | **ativo** |
| 11 | Maior tempo ativo | maior sequência com intervalo < 72 h entre ações válidas | `rankings.ActivityStreak` (alimentado pelo Action Registry) | sim (nova) | **ativo** |
| 12 | Maior patrimônio já alcançado | recorde de (1) | `RankingHistorico` | sim (nova) | **ativo** |
| 13 | Maior empresa já alcançada | estrelas; desempate: pico de funcionários | empresa (P1.04a/b) | não | pendente de fonte (fatia 2) |
| 14 | Maior tempo ativo já alcançado | recorde de (11) | `RankingHistorico` | sim (nova) | **ativo** |
| 15 | Presidente com maior % de votos | votos/total de uma eleição presidencial | resultado de eleição (P1.11) | não | **interface pronta**, sem chamador (fatia 5) |

Nenhuma categoria foi removida. As que não têm fonte aparecem na página com o estado e a dependência explícitos e **nunca** com valores inventados.

## 2. O que a fatia 1 entrega (app `rankings`, migração `0001`)
- `constants.py`: catálogo das 15 categorias com número, referência ao `14`, unidade, janela, fonte, estado e dependência.
- `RankingHistorico` (genérica, 14.5): categoria única, entidade, valor, instante do recorde, instante da gravação, metadados. Substituição só por valor **estritamente maior**.
- `ActivityStreak`: uma linha por jogador (sequência corrente + melhor sequência).
- Consultas ao vivo por agregação no banco (sem recalcular o mundo a cada acesso), posições com empate, limite de linhas, detalhamento estruturado (doc 20).
- Gancho `players.registry.register_action_observer` (genérico, não é um caminho de ação) e varredura diária do mundo para o recorde de patrimônio.
- Página pública `/rankings/` (ao vivo e histórico separados), `/rankings/data/` e `/rankings/<categoria>/` em JSON, `audit_rankings`, Admin somente-leitura.
- `record_presidential_result(...)`: interface para a Política, **sem chamador** e sem eleição inventada.

## 3. Interpretações (revisáveis)
| # | Ponto | O que o design diz | Escolha técnica | Revisão |
|---|---|---|---|---|
| R1 | Patrimônio líquido | "componentes reconhecidos pelo sistema financeiro, menos passivos" | Saldo bruto (o reservado continua do jogador) − Σ obrigações abertas em que o jogador é devedor. **Créditos a receber não entram.** Sem imóveis/empresas/estoque até haver regra de avaliação dos sistemas donos (decisão do GD, 2026-11-02) | créditos a receber |
| R2 | Janelas de 14/30 dias | "evitar diferenças causadas pelo horário em que cada jogador abre a página" (14.6) | Dias de competência **fechados**: `[hoje−N, hoje−1]`. O resultado não muda com a hora da consulta; o dia corrente entra quando fechar | convenção |
| R3 | Quem "pagou" o imposto | "jogador ou entidade que pagou" | A **conta pagadora do lançamento** `tax_*` (jogador ou empresa). No imposto retido sobre remuneração, o ledger lança a perna de imposto a partir da conta **pagadora da remuneração** (empresa/governo), não da do beneficiário; o ranking segue o lançamento, sem reatribuir | GD, se quiser contribuinte = beneficiário da renda |
| R4 | Lançamentos estornados | "efetivamente pagos" | Lançamento `tax_*` estornado não conta | — |
| R5 | Ação válida (14.3.11) | "ações reais de gameplay; login, chat e navegação não contam" | Toda execução **bem-sucedida** pelo Action Registry (a mesma de jogadores e bots). Recusas, login e páginas não contam. Novas ações do registro entram sozinhas | — |
| R6 | Período da sequência | "maior período de atividade contínua" | `última ação − primeira ação` da sequência (uma ação isolada = 0). Independe de a página ser aberta depois | — |
| R7 | Intervalo | "inferior a 72 h" | `intervalo < 72 h` continua; **exatamente 72 h encerra** ("3 dias ou mais") | — |
| R8 | Ranking ao vivo de tempo ativo | "armazenar o maior período já alcançado pela conta" | Ordena pela **melhor sequência da conta**; a sequência corrente e se ainda está ativa aparecem como informação | GD pode preferir a corrente |
| R9 | Recorde de patrimônio sem gancho no ledger | "recalculado quando uma alteração relevante ocorrer" | O ledger não tem gancho pós-lançamento. Verifica-se (a) a cada ação bem-sucedida do jogador e (b) numa varredura diária do **maior** patrimônio atual (uma consulta). **Limite conhecido:** um pico de patrimônio que surja e desapareça entre duas verificações pode não ser registrado; `audit_rankings` aponta recorde atrás da fonte | gancho no ledger |
| R10 | Falha do observador de ação | — | A ação já foi executada: a falha é registrada em log e isolada por savepoint; **nunca** recusa nem desfaz a ação. Efeito: uma ação pode deixar de contar para a sequência se o observador falhar (o log mostra) | — |
| R11 | Conta mais antiga | `data atual − criação` | `Player.created_at_game` (tempo de jogo); empate = mesma posição | — |
| R12 | Recorde presidencial | votos/total; "percentual efetivamente registrado" | Comparação **exata** por fração (votos/total); o valor guardado é o piso em partes por milhão, para exibição e índice. Guarda presidente, eleição (referência opaca), votos, total, percentual e data. Nenhum chamador nesta fatia | — |
| R13 | Nomes de entidade | — | Jogador: nome de usuário. Empresa/escola: `registrar nomeador` (`register_entity_namer`); sem nomeador a página mostra `tipo #id` | — |
| R14 | Tamanho da página | — | `[PROV]` 20 linhas por ranking (máx. 100); sem efeito de jogo | valor |

## 4. Proposta técnica — QoL comparável (item 4 do GD, 2026-11-02)

**Problema.** A QoL não é guardada: `qol_current(player, at, bal)` é uma função do estado estrutural em `at`, das flags de Burnout/Saúde e dos efeitos temporários. Cada jogador só é "atualizado" quando age (processamento lazy por ciclos de 10 minutos). Usar o último valor calculado de cada jogador compara instantes diferentes; recalcular todos a cada acesso à página é inviável. Nenhum dos dois é aceito.

**Proposta: snapshot periódico com referência de tempo comum.**
- `QolSnapshot(reference_at único, status, players_total, players_exact, started_at, finished_at)` e `QolSnapshotEntry(snapshot, player, qol, processed_until, exact)` com índice `(snapshot, -qol, player)`.
- Um job de **mundo** (tick horário, alinhado ao ciclo de 10 minutos) escolhe `reference_at B` = fronteira de ciclo atual. Para cada jogador, em **lotes** retomáveis: se `processed_until ≤ B`, faz o catch-up lazy até `B` (a MESMA `_catch_up` do 04: nenhuma regra duplicada) e calcula `qol_current(player, B)`; se o jogador já foi processado **além** de `B` (agiu durante o job), marca `exact=False` e usa o valor do estado em `B` quando reconstruível, senão fica sem valor e entra na contagem de auditoria — **nunca** um valor de outro instante apresentado como se fosse de `B`.
- A página lê **apenas o último snapshot completo** (`status=COMPLETE`): uma consulta ordenada pelo índice, `limit N`; mostra `reference_at` ("QoL em <instante>"). Todos os jogadores listados têm o mesmo instante de referência.
- Idempotente (`reference_at` único; reexecutar retoma de onde parou), em lotes com tempo medido (CPU, queries, jogadores/s — CLAUDE.md §9), retenção parametrizada (`[PROV]`: manter os últimos K snapshots, só o último é necessário).
- O `Explained` da QoL de cada jogador vem do mesmo cálculo (não reconstruído); a página mostra o valor e o detalhamento do 04.

**Alternativas descartadas.** (a) Guardar a QoL a cada sync do jogador: instantes diferentes, volta ao problema. (b) Cache mantido por evento: a QoL muda por tempo (efeitos expirando, histerese) sem evento. (c) Recalcular ao acessar: custo O(jogadores) por visita.

**Custo.** O(jogadores) por snapshot horário (não por acesso). Com ~1.000 bots, cada snapshot é um lote de ~1.000 cálculos; a medição real do custo decide a frequência (`[PROV]`: 1 h).

**Decisão necessária do Game Director:** aprovar este desenho (ou indicar outro) e a frequência/retenção. Até lá a categoria 4 permanece `PENDING_DESIGN`, sem bloquear as demais.

## 5. Próximas fatias (dependências explícitas)
2 (após #15–#17 na `main`): Maior empresa, Maior empregador (Dono não conta; por jogador, soma das empresas que possui), Maior produção por produto (14 dias, unidade do produto, nunca somando produtos), recorde de empresa. 3: Escola (#21, `QualityDay`). 4: Maior organização (P1.17, provedor). 5: chamada real do recorde presidencial (P1.11). QoL: após a decisão do §4.
