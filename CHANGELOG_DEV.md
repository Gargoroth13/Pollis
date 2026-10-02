# Polis — CHANGELOG DEV

Registro das decisões importantes de design e desenvolvimento que precisam permanecer visíveis para os agentes.

---

## 2026-10-02 — Skills (P0.05) sobre o `01` (REVIEW)

**Princípio:** o `01` está em REVIEW. Foi implementado **somente o que ele já estabelece**. Onde o documento diz que algo será definido/calibrado, há um parâmetro ou um ponto de extensão **neutro**; nenhum exemplo conceitual virou regra. As regras do `04` (P0.04) não foram alteradas; só ganharam os pontos de integração necessários.

### Decisões do `01` implementadas
1. Exatamente **3 skills** (Inteligência, Físico, Carisma); restrição no banco impede uma quarta.
2. Progressão **infinita**: nenhuma regra faz clamp superior (a coluna tem 26 dígitos inteiros).
3. O jogador **não distribui pontos**: não existe ação de "treinar"; a skill cresce porque a **atividade** foi feita.
4. **Estudar** desenvolve as 3 skills (`01 §1.4`); **Trabalhar** desenvolve a skill que o **cargo** informar (`01 §1.2`); o ganho do Trabalho é **menor** que o do Estudo (validado na configuração).
5. **Múltiplas skills** por atividade, quando ela as declarar.
6. **Requisitos mínimos** de uma ou mais skills, todas exigidas (`01 §1.9`), com detalhamento do que falta.
7. Fórmula de ganho `ganho_base × QoL_base × qualidade_da_escola` (`01 §1.3`), com **detalhamento estruturado** (doc 20), inclusive o diminishing returns como componente.
8. Skill como **multiplicador de produção** e como **base do teto salarial** (`01 §1.6-1.7`): só os pontos de uso/cálculo; ver extensão abaixo.
9. **Especialização do `02 §13`** (FINAL): ganho pelo trabalho, decadência diária, **piso de 50%** do máximo histórico, **recuperação a 1,5×**. Mais um **perfil emergente** descritivo (`01 §1.1`).

### Integração com o P0.04 (sem caminho paralelo)
- Novo `players/hooks.py`: `perform_action` aceita `activity: ActivityContext` e executa hooks **na mesma transação**, **só após o sucesso** da ação, em ordem determinística. Recusas (energia, burnout, hospitalização) **nunca** geram skill; falha em qualquer hook desfaz a ação inteira.
- `create_player` passou a ser atômico e chama hooks de criação (é onde as 3 skills nascem).
- Jogador humano e Bot usam exatamente o mesmo caminho (testado).
- A decadência da Especialização roda no **tick diário** do escopo `player` do P0.04. Único ajuste em teste do P0.04: `kinds_for("player")` deixou de ser exatamente `[TEN_MINUTES]`, porque outros sistemas agora somam outros kinds.

### Ambiguidades e interpretações técnicas (reversíveis; **confirmar**)
1. **"Especialização" tem dois sentidos.** `01 §1.1`: concentração que "surge naturalmente" (sem mecânica). `02 §13` (FINAL): valor próprio por atividade/produto. `03 §14` fala em cursos que aumentam "especializações". Implementei o perfil emergente (só leitura) **e** a mecânica do `02 §13`. **Não implementados:** ganho por curso (`03 §14`) e o fator `f(skill, especialização)` da produção, pois dependem de Escolas/Empresas e seus valores não existem.
2. **"QoL_base" (`01 §1.3`) × `04`, que agora distingue QoL Base / Base efetiva / Atual.** Virou configuração `[ABERTO]` `qol_source`: padrão `"base"` (leitura literal, estrutural); alternativa `"base_effective"`. A QoL Atual (buffs temporários) **não** é oferecida, por oscilar o ganho.
3. **"qualidade_da_escola" aparece na fórmula geral**, mas só faz sentido para estudo. Tratada como **fator de entrada** (`ActivityContext.school_quality`), valor 1 quando não se aplica; o sistema de Escolas a fornecerá.
4. **Várias skills em uma atividade:** cada skill recebe o **seu próprio** ganho base inteiro (sem dividir). O `01` não diz. Por skill é parametrizável.
5. **Trabalhar/Lazer sem skill declarada não desenvolve nada.** Quem define a skill relevante é o cargo (Empresas) e a atividade de lazer. Lazer **não tem ganho padrão** (`01 §2` deixa em aberto); pedir skill no Lazer sem informar o ganho é erro explícito, não um valor inventado.
6. **Ganho é por execução da ação** (não por energia nem por dia). Coerente com `03` ("mais energia dedicada → mais ganho diário").
7. **Skills nunca diminuem** (o `01` não define decadência de skill). Só a Especialização decai.
8. **Especialização:** só o **Trabalho** a desenvolve (`02 §13`: "através do trabalho"); a chave é opaca (atividade ou produto). "Dia sem uso" = dia de calendário do jogo (fuso do jogo) sem trabalhar naquela área, decaindo no tick que abre o dia seguinte; o dia do uso e o seguinte não decaem. A **forma** da decadência (pontos por dia) é suposição minha; o `02` só diz "decadência diária baixa".
9. **Teto salarial:** implementado só o **cálculo** (`nível × multiplicador`). O limite é diário com contador de recebido no dia; esse contador pertence ao sistema de pagamento (dinheiro), inexistente.
10. **Requisitos:** só **E** (todas as skills). O `01` não define "OU".
11. **Precisão:** a coluna aceita níveis enormes, mas o **SQLite de desenvolvimento** guarda decimais como ponto flutuante (~15 dígitos significativos). Em PostgreSQL (produção) é exato.
12. Consequência natural do `04`: com Burnout Ativo o Estudo é bloqueado, então não gera skill.

### Decisões abertas do `01`: isoladas, NÃO fechadas
| Decisão aberta | Como ficou |
|---|---|
| Fórmula do diminishing returns | Ponto de extensão `skills.curves.register_progress_curve`; única curva embutida é `"none"` (fator 1). Curva que devolva fator ≤ 0 é rejeitada (pararia a progressão infinita) |
| Fórmula Skill → produção | Ponto de extensão `register_production_curve`; padrão `"none"` (fator 1) |
| Multiplicador salarial definitivo | Parâmetro `salary_cap_multiplier`, `[PROV]` 1,5 (o "atualmente considerado" do `01`) |
| Distribuição de cargos entre INT/FIS/CAR | Não implementada (pertence a Empresas); o cargo informa a skill via `ActivityContext` |
| Quais atividades usam várias skills | `ActivityContext.skills`, definido por quem conhece a atividade |
| Ganhos definitivos de skill | Parâmetros `[PROV]` abaixo |
| Balanceamento de freelance | Não implementado |
| Atividades não especificadas | Sem ganho padrão; ganho explícito por atividade |

### Parâmetros provisórios `[PROV]` (numéricos, sobrescrevíveis por `POLIS_SKILLS_BALANCE`)
| Parâmetro | Valor | Observação |
|---|---|---|
| `initial_level` | 0 | o nível inicial virá do contexto de nascimento (hook `register_initial_level_provider`) |
| `base_gain.study` (cada skill) | 1,0 | `1` é só a unidade de referência; o `01 §1.3` usa "1.0" como exemplo conceitual |
| `base_gain.work` (cada skill) | 0,5 | só respeita "menor que o estudo" |
| `salary_cap_multiplier` | 1,5 | não definitivo (`01 §2`) |
| `specialization_gain_per_work` | 1 | `02 §13` deixa para o balanceamento |
| `specialization_decay_per_day` | 0,1 | idem |

`[02 §13]` (definidos): `specialization_floor_ratio` 0,5 e `specialization_recovery_multiplier` 1,5. `[ABERTO]` (configuração, não regra): `qol_source`, `progress_curve`, `production_curve`.

### Sugestões para o Game Director (**NÃO implementadas**; só para decisão)
- **Diminishing returns:** o `01` já cita uma fórmula em faixas como não definitiva. Candidatas: (a) faixas por nível; (b) contínua, ex. `1 / (1 + nível / k)`; (c) logarítmica. Qualquer uma deve manter o fator estritamente positivo para preservar a progressão infinita. Sugiro escolher depois de observar a distribuição de níveis nos Bots.
- **Razão Trabalho/Estudo:** com os valores atuais, Estudar custa 10 de Energia e rende 0,5 por skill; Trabalhar custa 20 e rende 0,25 na skill do cargo. Por Energia, estudar rende **4×** mais. Vale confirmar se essa proporção é a intenção antes de calibrar.
- **Ordem de grandeza dos requisitos:** com QoL 0,50 e os ganhos atuais, o exemplo conceitual do `01` (Inteligência ≥ 100) exigiria ~200 estudos, e o Burnout do `04` bloqueia o Estudo após ~34 seguidos (+3 cada). Os níveis "100" e "75" do `01` são só exemplos; os níveis reais dos cargos precisam nascer da calibração.
- **Multiplicador salarial:** manter como parâmetro e avaliar se vira parâmetro de lei (`07`/`11`), como o `01 §1.7` sugere.
- **Freelance:** definir "desenvolvimento mínimo" como razão do ganho do Trabalho antes de implementá-lo.

---

## 2026-10-01 — `04` fechado como FINAL e estado do jogador (P0.04)

### Decisão do Game Director
- `04 — Dia a Dia` foi reescrito e fechado como **FINAL — BOT TEST** (`a62f37f`). O rascunho do P0.04 que eu havia feito sobre a versão REVIEW foi **descartado e refeito**. Principais mudanças de regra: custos de Energia **fixos** (Trabalhar 20, Estudar 10, Lazer 10); regeneração **5 por 10 min** com modificador de QoL de ±10%; Burnout **0–100** com Burnout Ativo (entra em 100, sai em ≤ 50) que bloqueia Trabalho e Estudar; Saúde **+5 − penalidades por ciclo** (pode cair); Saúde Crítica (≤ 20 entra, > 30 sai) e Hospitalização (Saúde = 0); efeitos de QoL **um por categoria**; QoL **sem teto**.

### Motor de tempo
- Novo `TickKind.TEN_MINUTES` (600 s absolutos): o ciclo dos estados contínuos (`04 §2.3, §7.2, §10, §23`). Decisão técnica; roda antes dos demais ticks no mesmo instante.
- Os estados são processados **ciclo a ciclo** (lazy, no acesso) e não por fórmula fechada, porque Saúde, Burnout, Nutrição e Energia dependem uns dos outros (`§23`). Custo medido: ~25 µs por ciclo (144 dias de jogo ≈ 20 mil ciclos ≈ 0,5 s).

### Decisões estruturais confirmadas pelo Game Director (2026-10-01)
1. **Risco de Burnout (`02 §9.2`):** é um **multiplicador** sobre os *ganhos* de Burnout de **Trabalhar e Estudar** (`04 §7.1`), com **piso de 1%** (mínimo 0,01); o Lazer **não** é afetado. Para eliminar a ambiguidade entre os documentos, o texto do `02 §9.2` foi **atualizado** (com exemplo: risco 50% → Trabalhar dá +2,5 em vez de +5).
2. **Efeitos temporários (`04 §4.4`):** a regra de **um único efeito ativo por categoria é GLOBAL**, para efeitos positivos **e** negativos; um novo efeito da mesma categoria sempre substitui o anterior, qualquer que seja o sinal. O texto do `04 §4.4` foi **atualizado** para falar em "efeito temporário" (antes dizia "bônus").
3. **Hospitalização (`04 §14`):** bloqueia **Trabalhar, Estudar e Lazer**. O texto do `04 §14` foi **atualizado** (antes: "ações incompatíveis com internação, incluindo trabalho"). A lista segue configurável (`Balance.hospitalization_blocked_actions`) por causa do Tratamento e de outras ações futuras ainda não definidas; a validação continua exigindo `work`. A duração segue `[PROV]`.

### Interpretações de implementação (derivadas do texto do `04`; não contestadas)
1. **Ordem do ciclo (`§23`):** Saúde (lê o estado do *início*) → Burnout → Nutrição → Energia (usa a QoL Base efetiva do *novo* estado). Fica numa única função, `rules.advance_cycle`.
2. **Recuperação de Burnout:** a espera de 1 h conta só a partir do último *Trabalho* (Estudar e Lazer não reiniciam), é inclusiva (≥ 1 h) e quem nunca trabalhou recupera sem espera.
3. Saúde Crítica e Hospitalização são estados independentes (Saúde = 0 implica os dois).
4. A hospitalização termina por **duração** (o `§14` a declara parametrizada), não por limiar de Saúde.

### Decisões de design a fechar
Nenhuma aberta no momento. *(A da hospitalização, `04 §14`, foi fechada em 2026-10-01: ver acima.)* Ao surgir uma, entra aqui com a categoria `[ABERTO]` do código (`players/balance.py`), separada dos `[PROV]` numéricos.

### Parâmetros provisórios `[PROV]` (`04 §27`: calibráveis; valores só para o sistema rodar)
São **numéricos**, e ficam separados das decisões estruturais e da decisão em aberto acima. Todos em `players/balance.py`, sobrescrevíveis por `POLIS_BALANCE`:

| Parâmetro | Valor | O que representa |
|---|---|---|
| `energy_regen_qol_sensitivity` | 1 | QoL → modificador de regeneração (linear em torno de 1,00) |
| `burnout_qol_penalty` | 0,10 | penalidade na QoL Base efetiva em Burnout Ativo |
| `critical_health_qol_debuff` | 0,10 | debuff na QoL Atual em Saúde Crítica |
| `nutrition_decay_per_cycle` | 0,5 | taxa temporal de alteração da Nutrição |
| `health_nutrition_penalty_max` | 8 | penalidade de Saúde por ciclo com Nutrição = 0 (linear) |
| `health_burnout_penalty` | 0 | penalidade de Saúde em Burnout Ativo (0 = ainda não definida) |
| `hospitalization_duration_seconds` | 21600 (6 h) | duração da hospitalização |

### Observações para calibração (parâmetros mantidos como estão)
Por decisão do Game Director (2026-10-01), estas consequências **não** motivam alterar valores antes do Bot Test; os parâmetros seguem provisórios.
- Com QoL Base **0,50** (`§4.1`) e relação linear, **todo jogador começa no teto de −10% de regeneração** (4,5 por ciclo) até que Moradia/Bens elevem a QoL a ≥ 0,90. É consequência direta de `§4.1` + `§2.3`; vale avaliar a relação.
- Sem comer, a Nutrição zera em ~33 h de jogo e a Saúde cai 3 por ciclo até a Hospitalização: com a taxa atual o jogador precisa comer a cada ~1,4 dia de jogo (~14 min reais no Bot Test).

### Dependências ainda não implementadas
- **Tratamento** (`§13`, 10 de Energia + pagamento): depende do sistema de dinheiro.
- **Auto-consumo de alimentos** com Nutrição < 10 (`§16`): depende de Inventário (P1.02) e do catálogo.
- **Recuperação Regional** (`§11`): hook `register_regional_recovery_provider` pronto (vale 0 enquanto não houver saúde regional/médicos).
- **Bloqueio de Trabalho por Viagem** (`§6`, `§20`): depende de Geografia/Viagem; entra em `rules.block_reasons`.
- **Modificadores estruturais de QoL** (`§4.1`): hook `register_qol_base_provider`; cada sistema define o seu.
- **QoL → eficiência** (`§5`): sem consumidor ainda. **Estudar/Escola** (`§8-9`): P0.05+.

---

## 2026-09-30 — Reconstrução do código e fundação temporal

### Decisão do Game Director
- Todo o jogo implementado antes do design atual é defasado e foi **removido** (apps `empresas`, `financeira`, `geography`, `skills`, `Perfil`, templates). Preservado no histórico do Git. Mantidos: `design/`, documentos operacionais, projeto Django e `Usuario` como `AUTH_USER_MODEL`. Migrations reiniciadas (não há dados de produção a preservar).
- Consequência: a regra antiga "-0,2 QoL por trabalho/estudo" (código) está obsoleta, o `04` a substituiu por Burnout; e a criação de dinheiro por salário sem origem contraria o `CLAUDE.md`.

### Tempo do jogo (decisão do Game Director, 2026-09-30)
- **O tempo do jogo é o tempo real**: segundos, dias e meses de calendário reais (mês de 28–31 dias, anos bissextos). Não é relativo à time zone do usuário: o jogo tem a **sua própria time zone**.
- O jogo funciona por ticks **horários, diários, semanais e mensais**.
- Só a **velocidade** pode ser acelerada, no Bot Test (ex.: 1 dia = 10 min reais). Em produção, velocidade 1×.

### Motor de tempo (P0.03): decisões técnicas assumidas
Não são regras de gameplay; são convenções reversíveis e cobertas por testes:
- Tempo de jogo = segundos Unix do relógio de jogo (a 1× é idêntico ao tempo real). A velocidade padrão é 86400 s reais/dia de jogo; o Bot Test usa 600.
- **Fuso do jogo: `America/Sao_Paulo`** (confirmado pelo Game Director em 2026-09-30), configurável por `POLIS_GAME_TIMEZONE`. Sem horário de verão hoje; o motor aguenta DST (testado com New York e Kolkata).
- Hourly: a cada 3600 s absolutos. Daily: 00:00 local. Weekly: **segunda 00:00 local** (`07`). Monthly: **dia 1, 00:00 local** (confirmado pelo Game Director em 2026-09-30).
- Intervalos são (start, end]: sem perda nem repetição. Não há tick "retroativo" antes de o mundo existir.
- Ordem no mesmo instante: `TickKind` (do menor para o maior período), depois `priority`, depois `name`. Ordem do motor, não de gameplay; as dependências do estado do jogador estão em `04 §23` e vivem em `players/rules.advance_cycle` (ver 2026-10-01).
- Escopo sem handlers avança o ponteiro; handlers registrados depois não reprocessam o passado.
- Consequência da aceleração: com 1 dia = 10 min, um mês de calendário dura de 4h40 a 5h10 reais, e um jogador ausente por 1 dia real "perde" 144 dias de jogo (catch-up em lote).

### Pendências para o Game Director (nenhuma bloqueia o P0.03)
1. **Status divergente entre `TASK.md` e os arquivos de design:** `01` e `03` estão em FINAL no `TASK.md` mas `REVIEW` no cabeçalho do arquivo; `19` está REVIEW no `TASK.md` mas `FINAL — BOT TEST` no arquivo; `05` (REVIEW) não consta na lista. Tratados como REVIEW até decisão. A resolver em P0.01. *(O `04` já foi fechado como FINAL — BOT TEST em 2026-10-01.)*
2. **Índices desatualizados:** `design/README.md` e `implicacoes-tecnicas.md` citam arquivos que não existem mais (`06-politica.md`, `09-financeira.md`, `10-futuro.md`).
3. **Classificação de tick por sistema:** o `04 §23` já define a ordem dos estados do jogador (ver 2026-10-01); para os demais sistemas (leis, orçamento, contratos...) a classificação ainda precisa ser decidida sistema a sistema.
4. **Calendário "Ano N, Mês M" do Histórico do Mundo (`12`)**: é contado a partir do início do mundo ou é o ano de calendário? A tratar em P1.14.

---

## 2026-09-29 — Transição para implementação

### Processo

- O projeto encerra a rodada principal de discussão dos documentos `01–21`.
- `FINAL — BOT TEST` passa a significar especificação fechada para implementação.
- O Sitemap permanece em `REVIEW`, mas já pode orientar a estrutura de UI.
- O desenvolvimento deve começar pelos fundamentos e avançar por dependências.

### Estratégia de implementação

- Não esperar todos os sistemas futuros para começar a codificar.
- Não implementar sistemas FUTURO apenas para “completar” o jogo.
- Priorizar fundações reutilizáveis, testes e integrações.

---

## 2026-09-29 — Feedback

- `20 — Filosofia de Feedback ao Jogador` foi fechado como `FINAL — BOT TEST`.
- Fórmulas compostas devem retornar valor e detalhamento estruturado.
- O detalhamento pode representar soma, multiplicação, limites ou condições.
- Feedback não deve inventar causalidade que o modelo não calcula.
- A separação entre cálculo e apresentação é obrigatória.

---

## 2026-09-29 — Bots

- `21 — Bots para Testes de Beta` foi fechado como `FINAL — BOT TEST`.
- Bot Test é ferramenta de validação, não mecânica de jogo.
- Ambiente único contínuo.
- População-alvo inicial: aproximadamente 1.000 Bots.
- Criação padrão: aproximadamente 1 Bot por minuto até a meta.
- Population Controller pode preencher lacunas de cobertura.
- Relógio acelerado padrão: aproximadamente 1 dia de jogo = 10 minutos reais.
- Bots usam somente informações que jogadores normais teriam.
- Bots interagem entre si e com jogadores humanos quando aplicável.
- Abordagem de aprendizado: RL híbrido com regras de validação e Action Masking.
- LLM não é mecanismo de decisão do primeiro Bot Test.
- Modelo neural pode ser compartilhado entre Bots, com memória/experiência individual.
- Personalidade, objetivo e especialização são dimensões separadas.
- Reward varia por arquétipo/objetivo.
- Exploração varia por arquétipo e individualmente.
- Checkpoints do modelo são versionados e reproduzíveis.
- Métricas de conhecimento devem ser baseadas em desempenho demonstrado.
- Dashboard deve permitir inspeção geral, por arquétipo e individual.
- Dashboard deve mostrar objetivo, plano, próxima ação, decisões e conhecimento.
- Sistema deve detectar lacunas de cobertura e anomalias automaticamente.
- Logs devem ser exportáveis para análise externa.
- Performance deve medir CPU, RAM, GPU, VRAM, ticks, scheduler, banco e treinamento.

### Arquétipos-base

1. Casual
2. Otimizador
3. Conservador
4. Explorador
5. Caótico
6. Empreendedor
7. Político
8. Especialista
9. Social
10. Adversarial

A arquitetura não deve transformar esses 10 nomes em classes rígidas. Eles representam combinações-base; personalidade, objetivo e especialização devem permanecer combináveis.

---

## 2026-09-28 — Rankings

- Janela de produção do ranking: 14 dias.
- Ranking de contribuinte: impostos efetivamente pagos nos últimos 30 dias.
- Influência política permanece fora do Bot Test até existir métrica objetiva.
- Melhor escola/universidade utiliza qualidade atual.
- Conta mais antiga utiliza tempo desde criação.
- Maior tempo ativo utiliza sequência de ações válidas com intervalos inferiores a 72 horas.
- O antigo “Presidente com maior aprovação” tornou-se “Presidente com maior percentual de votos”, baseado no resultado efetivo da eleição.

---

## 2026-09-28 — Transparência de mercado

- Página de Produto deve usar transações reais e agregados.
- Preço médio é ponderado por quantidade.
- Estatísticas públicas utilizam agregados para desempenho.
- Histórico bruto continua disponível para auditoria/Dev.
- Gráficos de produto fazem parte do Bot Test.
- Custos de empresa devem mostrar componentes e principais contribuições sem inventar causalidade.

---

## 2026-09-27 — Contratos

- Partes de contratos podem ser jogadores ou empresas.
- Contratos de trabalho foram removidos da especificação de Contratos e permanecem nas regras de emprego/empresa.
- Empréstimos diretos entre jogadores podem existir como contrato.
- Execução é automática segundo os termos.
- Multas transferem dinheiro entre partes; não criam dinheiro.
- Contrato aceito fica congelado para aquela obrigação salvo mecanismo específico futuro.

---

## 2026-09-26 — Sociedades e Ações

- Sociedades e ações são endgame/futuro.
- Empresas normais continuam com proprietário único no início.
- Empresas de 4★ ou mais podem futuramente ser fracionadas em ações.
- Emissão primária capta capital para a empresa.
- Mercado secundário transfere dinheiro entre investidores.
- Bolsa, dividendos e voto acionário detalhado ficam fora do primeiro Bot Test.

---

## 2026-09-25 — Eventos Aleatórios

- Eventos continuam FUTURO.
- Evento deve alterar condição real existente, não aplicar apenas buff abstrato.
- Não criar consumidores fictícios ou dinheiro novo.
- Boom econômico baseado em NPCs foi removido.
- Eventos futuros podem usar estoque, QoL, saúde, recursos e estados reais existentes.

---

## 2026-09-24 — Geografia / Economia

- Hierarquia territorial: Estado → Cidade → Bairro → Lote.
- Bairro/cidade possuem estrutura espacial; capital é referência histórica em `(0,0)`.
- Lotes possuem capacidades por tipo.
- Áreas rurais suportam Matriz de Agropecuária, Extrativismo e Mineração.
- Petróleo deve pertencer a **Extrativismo**; referências antigas que coloquem petróleo em Mineração não são autoridade.
- Ocorrências minerais são espacialmente correlacionadas, não apenas sorteios independentes por lote.

---

## 2026-09 — Política / Leis

### Estrutura política

- Presidente, Governador e Prefeito são os executivos.
- Câmara dos Deputados é nacional no primeiro Bot Test.
- Um jogador não ocupa mais de um cargo político simultaneamente.
- Governador exige experiência anterior como Prefeito.
- Presidente exige experiência anterior como Governador e diploma de Engenharia, Direito ou Medicina.
- Político pode possuir empresas privadas, mas essas empresas não recebem contratos públicos enquanto ele ocupar cargo.
- Político não é empregado de outra empresa durante o mandato.

### Processo legislativo

- Discussão: 3 dias.
- Votação: 3 dias.
- Processo segue calendário semanal fixo.
- Câmara usa maioria absoluta da composição congelada.
- Presidente pode sancionar ou vetar.
- Veto pode ser derrubado por 2/3.
- Mudança do Presidente antes de sanção/veto retorna a proposta à Câmara.
- Lei entra em vigor no próximo weekly tick.
- Leis não retroagem.
- Constituição limita leis ordinárias.

### Deposição

- Milícia pode depor Presidente segundo `19`.
- Líder da milícia assume com novo mandato completo conforme parâmetro aplicável.
- Governadores e Prefeitos permanecem.
- Câmara é encerrada e nova eleição é realizada.
- Constituição e leis existentes não são apagadas automaticamente.

---

## 2026-09 — Militar

- Não existe cooldown para trocar Exército e Milícia.
- Entrada e saída devem respeitar apenas os requisitos normais do sistema.
- Milícias utilizam estoque e Produtos reais.
- Conflitos consomem recursos e podem gerar hospitalização.
- Exército é financiado por orçamento público.

---

## 2026-09 — Economia / Empresas

- Uma empresa produtiva possui um Produto/linha de produção atual por vez, com regras de mudança documentadas em `02`.
- Produto → usos permitidos → empresas capazes de consumir o produto é a cadeia de compatibilidade econômica.
- Compras de insumos são limitadas pelas regras reais de receita/operação.
- Engenheiros aumentam eficiência por ação de trabalho, com limite por estrela.
- Advogados reduzem risco de burnout.
- Construção possui um projeto ativo por vez.
- Acabamentos usam Tábuas + Vidro.
- Propriedade normal da empresa não depende de sociedade por ações no Bot Test.

---

# Próximo marco

**Implementação do núcleo do Bot Test:** tempo → estado do jogador → skills → geografia → produtos/inventário → Action Registry → empresas/mercado → UI → política/militar → Bots.

O objetivo é manter cada etapa pequena, testável e reversível sem reabrir decisões de design já marcadas como FINAL.
