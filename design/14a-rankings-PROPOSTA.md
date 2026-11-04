# 14a — Rankings: implementação da P1.15a (fatia 1) — mapa de fontes, interpretações e decisões aplicadas (PROPOSTA)

**Status:** PROPOSTA — documento de apoio ao `14 — Rankings` (FINAL — BOT TEST). Nada aqui altera o design. Cada linha é uma lacuna **técnica** onde o `14` é
silencioso, a escolha feita para não bloquear e o que o Game Director pode revisar. O `14` continua **FINAL — BOT TEST** (só vira IMPLEMENTED depois de integrado e validado na `main`).
Revisão de 2026-11-03: aplica as decisões do Game Director sobre o PR #32 (itens D1–D4 e correção do recorde de patrimônio, §3).

## 1. Mapa de fontes (numeração: ao vivo 1–11 = 14.3.1–14.3.11; históricas 12–15 = 14.4.1–14.4.4)

| # | Ranking | Métrica / regra | Fonte | Está na `main`? | Estado |
|---|---|---|---|---|---|
| 1 | Maior patrimônio líquido | saldo bruto + créditos a receber − obrigações a pagar (só o que o ledger reconhece) | `ledger.Account`, `ledger.Obligation` | sim | **ativo** |
| 2 | Maior empresa | estrelas; desempate: funcionários | empresa (P1.04a/b, PRs #15/#16) | não | pendente de fonte (fatia 2) |
| 3 | Maior produção (14 dias) | quantidade efetivamente produzida **por produto**, na unidade do produto | registro de produção (P1.04c, PR #17) | não | pendente de fonte (fatia 2) |
| 4 | Melhor QoL pessoal | QoL de todos os jogadores no MESMO instante de referência | `rankings.QolSnapshot` (de `players.qol`) | sim (nova) | **ativo** (§4) |
| 5 | Maior influência política | — | — | — | **fora do Bot Test** (14.3.5, 14.10) |
| 6 | Maior empregador | por empresa: funcionários (o Dono não conta); por jogador: soma das empresas que possui | vínculos/propriedade (P1.04a/b) | não | pendente de fonte (fatia 2) |
| 7 | Maior contribuinte (30 dias) | imposto efetivamente pago, atribuído ao contribuinte (§3.2) | `ledger.Entry` (`tax_*`) | sim | **ativo** |
| 8 | Melhor escola/universidade | qualidade atual da instituição | `QualityDay` (P1.06a, PR #21) | não | pendente de fonte (fatia 3) |
| 9 | Maior organização | membros da milícia (a contagem, não a composição) | P1.17 | não | pendente de fonte (fatia 4) |
| 10 | Conta mais antiga | agora − criação da conta | `players.Player.created_at_game` | sim | **ativo** |
| 11 | Maior tempo ativo (sequência atual) | sequência corrente ainda ativa (< 72 h desde a última ação válida) | `rankings.ActivityStreak` | sim (nova) | **ativo** |
| 12 | Maior patrimônio já alcançado | recorde de (1), mantido pelo ledger (§3.5) | `RankingHistorico` | sim (nova) | **ativo** |
| 13 | Maior empresa já alcançada | estrelas; desempate: pico de funcionários | empresa (P1.04a/b) | não | pendente de fonte (fatia 2) |
| 14 | Maior tempo ativo já alcançado | recorde da MELHOR sequência (`best_length`) | `RankingHistorico` | sim (nova) | **ativo** (§3.6: confiabilidade) |
| 15 | Presidente com maior % de votos | votos/total de uma eleição presidencial | resultado de eleição (P1.11) | não | **interface pronta**, sem chamador (fatia 5) |

Nenhuma categoria foi removida. As que não têm fonte aparecem na página com o estado e a dependência explícitos e **nunca** com valores inventados.

## 2. O que a fatia 1 entrega (app `rankings`, migrações `0001`–`0003`)
Catálogo das 15 categorias; `RankingHistorico` genérico (14.5); `ActivityStreak`; consultas ao vivo por agregação no banco; página pública `/rankings/` (ao vivo e histórico separados), JSON, `audit_rankings`, Admin somente-leitura; `record_presidential_result` (interface, sem chamador). Ganchos genéricos novos nos sistemas de origem, **sem alterar regra de jogo ou monetária**: `players.registry.register_action_observer`, `players.hooks.register_checkpoint` (+ `sync_player_until`) e `ledger.hooks` (fim de operação).

## 3. Decisões do Game Director aplicadas (2026-11-03) e interpretações

### 3.1 D2 — Patrimônio líquido
`saldo bruto + créditos a receber − obrigações a pagar`. Créditos a receber = restante (`amount_due − amount_paid`) das obrigações **abertas** em que o jogador é credor; pagas e canceladas não entram; o reservado continua no saldo bruto. Sem imóveis, empresas ou estoque até haver regra de avaliação dos sistemas donos. O detalhamento estruturado traz `balance`, `receivables`, `open_obligations`. **Risco registrado:** o crédito é contado pelo valor restante, sem avaliar a solvência do devedor.

### 3.2 D3 — Maior contribuinte (atribuição por natureza e referência; sem substituição global de `from_account`)
- **Imposto retido sobre remuneração** (`tax_income` lançado junto com um pagamento de remuneração ou com a quitação de obrigação de remuneração): contribuinte = **jogador beneficiário**. A empresa/governo que só recolhe e remete não recebe o crédito.
- **Demais impostos** (`tax_sales`, `tax_property`, `tax_income` que não seja de remuneração): a conta pagadora do lançamento (jogador ou empresa).
- Como o beneficiário é identificado (`rankings/taxes.py`): (1) mesma transação tem a perna líquida de natureza de remuneração (WAGE, MILITARY_PAY, OWNER_SALARY, POLITICAL_SALARY) → conta de destino dela; (2) sem perna líquida (alíquota de 100%): pela referência da transação (`remuneration:<pedido>` → `RemunerationRequest.player_id`; `settle:<lote>:<obrigação>` → credor da `Obligation` de remuneração); (3) nenhuma das duas: fica a conta pagadora e o caso entra em `unresolved_in_window` (visível no detalhe).
- Imposto autocompensado (governo paga remuneração e a própria União recebe o imposto) não gera lançamento: sem crédito. Estornado não conta. Janela: 30 dias de competência **fechados** (`[hoje−30, hoje−1]`).

### 3.3 D4 — Maior tempo ativo
Ao vivo: ordenado pela **sequência corrente**; só entram contas cuja sequência está ativa (intervalo desde a última ação **< 72 h**); valor = `consulta − current_start`. Histórico (14.4.3): `best_length`, a maior sequência já alcançada. Ação válida = execução bem-sucedida pelo Action Registry; exatamente 72 h encerra a sequência.

### 3.4 Interpretações mantidas
| # | Ponto | Escolha técnica |
|---|---|---|
| R2 | Janelas de 14/30 dias | Dias de competência fechados: o resultado não muda com a hora da consulta (14.6) |
| R4 | Lançamentos estornados | Não contam |
| R6 | Período da sequência | `última ação − primeira ação` da sequência (uma ação isolada = 0) |
| R11 | Conta mais antiga | `Player.created_at_game`; empate = mesma posição |
| R12 | Recorde presidencial | Comparação exata por fração; guarda presidente, eleição (referência opaca), votos, total, percentual e data; sem chamador |
| R13 | Nomes de entidade | Jogador: usuário. Empresa/escola: `register_entity_namer`; sem nomeador, `tipo #id` |
| R14 | Tamanho da página | `[PROV]` 20 linhas (máx. 100) |
| R15 | Desempate de recorde | Valor estritamente maior; em empate fica quem o alcançou **antes** (instante do recorde), mesmo que aplicado depois |

### 3.5 Correção — recorde de patrimônio líquido confiável (ledger)
A versão anterior (observer de ação + varredura diária) podia perder picos produzidos por operações automáticas. Agora o recorde é mantido **pelas operações centrais do ledger**:
- `ledger/hooks.py` (extensão pequena; **nenhuma regra monetária muda**): uma *operação* é uma chamada pública que altera saldo ou obrigações (`post_transaction` e quem a usa, `open_obligation`, `settle_obligations`, `cancel_obligation`, `liquidate_remuneration`). Operações aninhadas formam **uma** operação: o gancho roda **uma vez**, ao fim da mais externa, com o **estado final** (saldos e obrigações já atualizados), **dentro da transação** (se a operação for desfeita, o efeito também é). Só dispara para contas que de fato escreveram; repetição idempotente e recusas não disparam.
- `rankings.records.on_ledger_operation`: para cada jogador afetado calcula o patrimônio com o estado final e oferece ao recorde (leitura sem trava quando não supera; trava só da linha do recorde quando supera — ordem de travas: contas do ledger → linha do recorde, sem ciclo).
- **Nunca descarta em silêncio:** se gravar o recorde falhar, grava um `NetWorthCandidate` (valor e instante da operação) **na mesma transação**; a tarefa horária (`drain_net_worth_candidates`) reaplica na ordem cronológica e remove. Se nem o candidato puder ser gravado, o erro propaga e a **operação financeira inteira é desfeita**. `audit_rankings` aponta candidatos pendentes (`NET_WORTH_CANDIDATES_PENDING`) e recorde atrás da fonte.
- A varredura diária virou **reconciliação** (reaplica candidatos e confere o maior patrimônio atual); não é mais o mecanismo principal.
- Testes: operação automática sem ação do jogador (transferência, folha, dotação), abertura/pagamento parcial/quitação/cancelamento de obrigação (inclusive que **não** se registra pico transitório no meio da quitação), pico revertido antes da varredura, atomicidade (rollback externo; falha de gravação → candidato; falha total → operação desfeita) e concorrência (PostgreSQL e SQLite).
- **Custo medido por construção:** por operação financeira com jogador, 1 consulta de patrimônio + 1 leitura do recorde. A medição em carga real (Bot Test) decide se precisa otimizar.

### 3.6 Observer de atividade — limitação e proposta (decisão do GD: propor antes de considerar a sequência plenamente confiável)
**Limitação atual (registrada):** o observer roda depois que a ação foi executada; se falhar, a ação é preservada, a falha vai para o **log** e o log **não recupera automaticamente** a ação perdida (a sequência pode ficar uma ação atrás). Para o recorde histórico isso é pequeno (uma ação isolada raramente muda o recorde), mas não é garantia.
**Proposta (não implementada; aguarda aprovação do GD porque altera a semântica transacional do registro):** *registro durável de ações* (outbox).
1. `players.ActionEvent(player, action_id, at, processed)` gravado **na mesma transação** da ação (o registro passa a envolver `entry.execute` em `transaction.atomic`, ou cada serviço dono grava o evento no seu fim). Ação e evento são atômicos: não há ação sem evento.
2. Consumidores (Rankings: `record_action`) leem eventos não processados em ordem e marcam `processed`; `record_action` já é idempotente (`at ≤ última ação` é ignorado) e retomável; um worker (tick de 10 min do mundo) drena o atraso.
3. O observer imediato continua como caminho rápido; o outbox é a rede de segurança (a falha do observer não perde mais nada, só atrasa).
4. Custo: 1 INSERT por ação + 1 UPDATE no consumo; retenção do outbox parametrizada (só os já processados e antigos).
Alternativa mais barata: o observer, ao falhar, grava só o evento (`player_id`, `at`) num registro durável mínimo e o worker reaplica. Preferência técnica: a opção completa (1–4), por servir também a Eventos/Jornal no futuro. **Decisão do GD:** aprovar/escolher.

## 4. QoL — snapshots periódicas com referência de tempo comum (decisão do GD aprovada; implementada)
**Problema.** A QoL não é guardada (`players.qol`): é função do estado do jogador em um instante; cada jogador só é atualizado quando age (lazy, ciclos de 10 min). Usar o último valor calculado de cada um compara instantes diferentes; recalcular todos a cada acesso é inviável.
**Solução implementada.**
- `QolSnapshot(reference_at único, status OPEN|COMPLETE|INCOMPLETE, eligible, represented, missing, metrics)` e `QolSnapshotEntry(snapshot, player, qol exato, explained, source)`, índice `(snapshot, -qol, player)`. Frequência `QOL_SNAPSHOT_INTERVAL_SECONDS = 3600` (parametrizada, múltiplo do ciclo de 10 min); retenção das **últimas 24 COMPLETE** (`QOL_SNAPSHOT_RETAIN_COMPLETE`); incompletas anteriores à mais antiga mantida e as COMPLETE mais antigas são apagadas (entradas em cascata).
- **Captura ao avançar o jogador** (`players.hooks.register_checkpoint`): a referência da próxima hora é aberta **com antecedência** (tick de 10 min do mundo; e, se o tick atrasar, pelo próprio provedor). Quando um jogador avança atravessando o instante de uma snapshot aberta, o catch-up é **dividido nesse instante** (mesmos ciclos e hooks de acesso; sem checkpoint o caminho é idêntico ao de antes — testado por equivalência), a QoL é lida ali **antes** de qualquer mudança posterior (ação, efeito substituído) e gravada com o `Explained` do MESMO cálculo. Isso evita que jogadores ativos tornem a snapshot incompleta por terem agido depois da referência.
- **Varredura de finalização** (em lotes, cada jogador em transação própria, retomável/idempotente, **fora** da transação do mundo via `on_commit`): leva os jogadores ainda não processados além da referência até ela (`sync_player_until`, a MESMA `_catch_up` do 04) e captura pelo mesmo caminho.
- **COMPLETE** só quando todos os elegíveis (`created_at_game ≤ reference_at`) estão representados **exatamente** em `reference_at` (o banco recusa COMPLETE com `missing > 0`). Se algum jogador já foi processado além da referência sem captura (valor não reconstruível), a snapshot fica **INCOMPLETE**, nunca se misturam instantes e a página continua mostrando a **última COMPLETE**.
- A página lê só a última COMPLETE (uma consulta pelo índice, `limit N`), mostra o `reference_at` e nunca recalcula jogadores no acesso (testado).
- **Métricas** por snapshot (CLAUDE.md §9): duração, consultas, jogadores por origem (`advance`/`sweep`), atraso da finalização; `audit_rankings` aponta COMPLETE inconsistente e OPEN vencida.
- Testes explícitos de concorrência entre ações de jogadores e a finalização (PostgreSQL e SQLite), exatidão por jogador (o efeito aplicado depois da referência não aparece no valor dela), efeito substituído depois, Burnout, elegibilidade, retomada após falha, idempotência, retenção, intervalo parametrizado e validado.
**Riscos.** A varredura é O(jogadores) por hora (a medição no Bot Test decide a frequência); a captura adiciona 1 consulta aos syncs que cruzam uma referência (nenhuma quando não cruzam); um tick de mundo muito atrasado pode deixar uma referência INCOMPLETE (visível na auditoria e nas métricas, nunca exibida).

## 5. Próximas fatias (dependências explícitas)
2 (após #15–#17 na `main`): Maior empresa, Maior empregador (Dono não conta; por jogador, soma das empresas que possui), Maior produção por produto (14 dias, unidade do produto, nunca somando produtos), recorde de empresa. 3: Escola (#21, `QualityDay`). 4: Maior organização (P1.17, provedor). 5: chamada real do recorde presidencial (P1.11). Sequência de atividade plenamente confiável: depende da decisão do §3.6.
