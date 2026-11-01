# 21a — Bots: infraestrutura da P1.18a — lacunas técnicas e interpretações (PROPOSTA)

**Status:** PROPOSTA — documento de apoio ao `21 — Bots para Testes de Beta` (FINAL — BOT TEST). Nada aqui altera o design; cada linha é uma lacuna
**técnica** onde o `21` é silencioso, a escolha feita para não bloquear e o que o GD pode revisar. Valores sem fonte: `bots/params.py::parameter_table()`.

## 1. O que a P1.18a entrega (app `bots`, migração `0001`)
Entidade **Bot** (conta de jogador normal + identidade administrativa), **execução** (`BotRun`: versões, seed global, população-alvo, velocidade do relógio, contadores),
**Population Controller** (criação a 1 Bot por minuto REAL, configurável, até a meta; perfis escolhidos por lacuna de cobertura), **scheduler individual**
(avaliação variável por Bot, reproduzível), **observação restrita** (só o que o jogador veria), **máscara de ações** sobre o Action Registry compartilhado,
**ciclo de decisão** (observar → mascarar → política → ação pelo registro normal → logs → próxima avaliação), **logs de ação e de decisão**, **armazenamento
de experiência** (`next_observation`; reward é da P1.19), **seeds** reproduzíveis, **métricas de desempenho** por passada, **ferramentas de Admin** (congelar,
descongelar, remover, parar), **dashboard técnico básico**, **exportação** (`bot_test_AAAA-MM-DD.zip`) e os comandos `bot_run`, `bot_step`, `bot_export`.

**Fora desta etapa:** o modelo híbrido de RL, reward e exploração (P1.19); a lógica dos 10 arquétipos (P1.20); dashboards completos (P1.21); detecção de anomalias
e de lacunas de sistema (P1.22); enumeração de alvos para ações que exigem alvo (modelo da P1.19). A política desta etapa é **só de infraestrutura**.

## 2. Lacunas e interpretações
| # | Ponto | O que o design diz | Escolha técnica | Revisão |
|---|---|---|---|---|
| B1 | Intervalos entre avaliações (21 §21.4) | "variável"; sem valores | `[PROV]` 10–30 min de jogo depois de agir, 30 min–2 h sem ação, primeira avaliação espalhada em 0–60 min; sorteio pela seed do Bot | valores `[PROV]` |
| B2 | "1 Bot por minuto" (21 §21.2) | taxa padrão, configurável | Minuto **real** do servidor (não do jogo); o controlador recebe o instante real como parâmetro (testável); rajada máxima `[PROV]` 10 para recuperar uma pausa sem criar centenas de uma vez; ao atingir a meta, não acumula criações atrasadas | técnica |
| B3 | Cobertura (21 §21.2) | "maximizar a cobertura útil", sem proporção fixa | O próximo perfil usa o arquétipo e a especialização MENOS cobertos entre os ativos (desempate pela seed); as especializações acompanhadas são configuráveis por execução. Lacunas = valores abaixo da média da dimensão. A cobertura por **sistema efetivamente testado** (Mineração/Indústria/Medicina/Política do exemplo) exige dados de ação por sistema: P1.22 | refinar na P1.22 |
| B4 | Política-base | o RL é a P1.19; "sem LLM" | `UniformMaskedPolicy` (uniforme entre ações disponíveis **sem alvo**); versão `uniform_masked_v0`; serve só para exercitar o ciclo. Não é estratégia nem heurística de jogo | substituída na P1.19 |
| B5 | Máscara (21 §21.21) | ações disponíveis | Disponibilidade GERAL do próprio registro (`players.registry.available_actions`); a execução revalida tudo. Ação fora da máscara nunca é executada: `POLICY_ILLEGAL_ACTION` | técnica |
| B6 | Identidade do Bot | contas reais, nunca NPC (21 §21.60, cenário) | `Usuario` sem senha utilizável (`bot-<execução>-<n>`) + `Player` criado por `create_player` (mesmos ganchos, inclusive a dotação do cenário) + linha `Bot` só visível a Admin | técnica |
| B7 | Dotação inicial (21 §21.60, cenário) | lançamento explícito de emissão do cenário; ausente recusa | Nada novo: é o gancho do jogador (`ledger.integration`). Cenário ativo sem a linha `player` → `create_bot` recusa (nenhum Bot criado) | — |
| B8 | Nome do arquétipo 2 | `21` §21.6 diz "Magnata"; CLAUDE.md §8 diz "Otimizador" | Chave `magnate` (Otimizador + Riqueza); "Otimizador" é a PERSONALIDADE | nome |
| B9 | Informação do Bot (21 §21.17) | só o que o jogador vê | A observação desta etapa é o estado PRÓPRIO (`players`/`ledger`); informação pública (preços, leis, vagas) entra com cada sistema que a expuser ao jogador; `ALLOWED_KEYS` é conferido por teste | cresce com os sistemas |
| B10 | Arquivos de exportação (21 §21.53) | lista de 11 arquivos | 9 produzidos; `training_metrics` (P1.19) e `economy_daily` (P1.21) listados como pendentes em `run.json`; `anomalies.csv` traz só falhas técnicas registradas (P1.22 cobre a detecção) | pendências declaradas |

## 3. Garantias testadas
Um Bot só é avaliado quando vencido, no máximo UMA ação por avaliação, pelo `execute_action` do registro (Energia, requisitos e cooldowns normais); Bot congelado/removido nunca é
avaliado; o `wake` só antecipa; a política recebe somente observação, máscara e gerador aleatório; o reward nunca existe antes da ação; exceções da política e da execução viram registros
(`POLICY_EXCEPTION`, `EXCEPTION`), nunca são engolidas; criar Bot não cria dinheiro; a mesma seed global reproduz os perfis, as seeds e os primeiros agendamentos.
Concorrência (PG-only, `CROSS_ROW`): dois trabalhadores no mesmo Bot geram uma única avaliação; passadas simultâneas do controlador não duplicam criações.
