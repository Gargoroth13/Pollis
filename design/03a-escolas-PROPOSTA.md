# 03a — Escolas: o que foi implementado e o que depende de decisão (proposta)

> **Status:** DRAFT — PROPOSTA (nada aqui vira mecânica antes da decisão do Game Director)
>
> O `03` está em REVIEW e deixa muitos parâmetros e algumas estruturas em aberto (§27-§28). A implementação (P1.06) segue a regra de
> trabalho: **ordem de execução muda com dependências, escopo não encolhe**. Parâmetros numéricos ausentes entram como `[PROV]`
> em tabela auditável (`schools/params.py`); estruturas ausentes ou ambíguas ficam aqui, sem decisão silenciosa (CLAUDE.md §13).

## 1. Etapas de P1.06

| Etapa | Conteúdo | Depende de |
|---|---|---|
| **P1.06a** (esta) | Escola (pública/particular), escola pública de origem por bairro, matrícula inicial e troca no bairro, capacidade (via provedor), materiais com limite por estrela, decaimento, qualidade base diária, ação `change_school`, auditoria | — |
| P1.06b | Funcionários da escola (professores, diretor), salários, trabalho do professor → bônus de qualidade (§10-§12), mensalidade diária e expulsão por inadimplência (§6.1) | decisões 3–6 abaixo; remuneração (`ledger`) |
| P1.06c | Universidade: cursos, requisitos, matrícula única, estudo, abandono, diploma (§17-§23) | decisões 9–11; Estudar (`skills`) |
| P1.06d | Ligações: capacidade ← Imóveis (P1.07, provedor de residências), financiamento público e salário do diretor ← Orçamento (P1.09), compra de materiais ← Mercado (P1.05b), construção de escolas ← Construtora/governo | P1.05b, P1.07, P1.09 |

## 2. O que a P1.06a implementa (e como)

- **Escola pública por bairro**: "normalmente haverá uma única escola por bairro" (§2). Existe uma escola pública de origem por bairro, criada no primeiro uso (não cria dinheiro nem estoque). Escolas adicionais (públicas ou particulares) são permitidas.
- **Matrícula inicial automática** na escola pública do bairro do jogador (§2). Candidatas: só públicas (a particular cobra mensalidade, §6.1). Várias públicas: a primeira, por id, com vaga conhecida sobrando; senão a de origem.
- **Troca de escola** (`change_school`): só para outra escola do **mesmo bairro** da escola atual (§2); recusada se cheia quando a capacidade é conhecida. Histórico contínuo.
- **Capacidade** = residências possíveis do bairro × 1,5 (§4, multiplicador parametrizado). Sem provedor de residências (Imóveis, P1.07) a capacidade é "Sem dados" (nunca 0 nem ilimitada).
- **Materiais** (`school_supplies`, 22): estoque com limite por estrela, trilha imutável, entrada só por compra (o pagamento é ligado em P1.05b), decaimento diário.
- **Qualidade diária** (§7-§12): qualidade do dia = retrato dos materiais do ciclo anterior (1:1, limitado pela estrela) + bônus dos professores (0 até P1.06b). Retrato lido da trilha (antes do início do dia); o decaimento do dia vem depois do retrato.

### Valores `[PROV]` (tabela `schools/params.py`)
| Parâmetro | Valor | Origem |
|---|---|---|
| Multiplicador de capacidade | 1,5 | **definido** no `03` §4 |
| Estrela inicial da escola | 1★ | `[PROV]`, mesmo padrão das empresas (`02` §25.1) |
| Materiais máximos por estrela | 333 / 667 / 1.000 / 1.333 / 1.667 | `[PROV]`: reta pelo único ponto dado (3★ = 1.000, §8) |
| Decaimento | 2% do retrato por dia, arredondado HALF_EVEN | `[PROV]` (§9: "definida posteriormente") |
| Qualidade por material | 1:1 | exemplo do §8 (1.000 materiais ↔ qualidade base 1.000) |

## 3. Decisões necessárias do Game Director

| # | Lacuna | Por que é do GD | Opções / minha proposta |
|---|---|---|---|
| 1 | **Capacidade × moradia inicial**: todo jogador nasce na capital (GD 2026-10-07) e a moradia inicial **não consome** capacidade residencial (`10` §7), mas as vagas da escola dependem das residências do bairro (§4) | Com poucas residências o bairro inicial ficaria sem vagas; hoje a matrícula **inicial nunca é recusada** e o excesso fica visível (`over_capacity`) | (a) manter: matrícula inicial isenta de limite, limite só nas trocas; (b) vagas mínimas para a moradia inicial; (c) outro |
| 2 | **Mapeamento Qualidade da escola → ganho de skill**: `01` §1.3 usa um fator ~1,0 (escola 0,5 / 1,0); `03` §8 usa pontos (até 1.000) | Sem a escala, a qualidade não pode alimentar o Estudar; hoje o fator da escola no Estudar segue neutro (1) | (a) fator = qualidade ÷ qualidade de referência (qual?); (b) tabela por faixas; (c) outra |
| 3 | **Como se funda uma escola particular** (custo, lote institucional, estrelas iniciais) e se `03` §6 cria um tipo de empresa novo ou uma instituição à parte | Não definido em `02`, `03` nem `10`; a fundação de escola por jogador **não** existe ainda | criar como instituição à parte, financiada pela conta do dono (§6: "utiliza seu próprio dinheiro") |
| 4 | **Quem é o diretor da escola pública e como é nomeado**, e quem contrata os demais (§5.1: "define os salários dos demais funcionários") | Sem regra de nomeação | nomeado pelo Prefeito (P1.11) ou eleito entre professores |
| 5 | **Fórmula do professor** (§11): diminishing returns da skill, valor base do trabalho, bônus de especialização | Marcados como "definidos posteriormente" | `[PROV]` inicial na P1.06b, com a curva já existente em `skills` |
| 6 | **Mensalidade** (§6.1): quem fixa, mínimo/máximo por lei, cobrança diária, "expulsão por inadimplência" (volta para qual escola?) | Parâmetros e destino do aluno expulso | aluno volta à escola pública de origem do bairro |
| 7 | **Fase escolar inicial** (§16, ~2 meses): o que acontece ao terminar (sai da escola? Estudar muda?) | O design dá a duração, não a consequência | — |
| 8 | **Estrelas da escola**: progressão (como sobem), análoga à `02a` das empresas | Não definida | reaproveitar o modelo da `02a` quando aprovado |
| 9 | **Lista de cursos** (§14, §28), requisitos, durações, custos e skills de cada um | "Lista completa de cursos" em aberto; só há exemplos (Medicina, Engenharia, Direito) | começar com os três exemplos e durações `[PROV]` |
| 10 | **Estudar na universidade**: ganho de skill/especialização por curso e progresso do curso (§17, §20-§22) | Fórmulas não definidas | progresso por Estudar, usando o mesmo hook de skills |
| 11 | **Diploma**: quais cargos/empresas o exigem (§23) | Cada sistema consumidor define | ponto de consulta `has_diploma(player, course)` |
| 12 | **Trocar de escola particular**: a escola aceita qualquer aluno? há admissão? | Não definido | aceita, sujeito à mensalidade |
| 13 | **Momento do retrato dos materiais** (§9): retrato antes do decaimento do dia | Interpretação do diagrama "Dia D → Dia D+1" | confirmar |
