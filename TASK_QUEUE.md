# Polis — TASK QUEUE

Fila de implementação e consolidação para o primeiro Bot Test.

Prioridade:

- **P0** = bloqueia o avanço principal;
- **P1** = próxima implementação importante;
- **P2** = melhoria ou sistema posterior;
- **FUTURO** = fora do primeiro Bot Test.

---

# P0 — Antes / junto do início da implementação

## [x] P0.01 — Auditoria final de documentos em REVIEW  *(consolidação documental concluída em 2026-10-14, PR #8, mergeado em `main`)*

> **Estado (2026-10-14):** as decisões aprovadas do Game Director (D1–D25, Q1–Q12 e confirmações) foram documentadas em PR único (branch `dev/p0.01-consolidacao-documental`). `06`, `11` e `19` seguem em **REVIEW** apenas por dependências de execução registradas em `06` 06.36, `11` (teto de déficit sem proposta; zoneamento por lei, P1.07) e `19` 19.48. Isso não bloqueia a P0.02. Decisões e dependências: `CHANGELOG_DEV.md` ("P0.01 — consolidação documental").

**Sistemas:** `06`, `11`, `19`, Sitemap  
**Objetivo:** eliminar inconsistências remanescentes antes de depender desses documentos na implementação.

Critérios:
- nenhuma regra obsoleta permanece na versão de trabalho;
- decisões do Game Director aparecem consolidadas;
- inconsistências conhecidas são resolvidas ou explicitamente marcadas;
- versões FINAL ficam separadas das versões antigas.

---

## [x] P0.02 — Auditoria do catálogo `22 — Receitas-Produção`  *(concluída em 2026-10-15; PR sobre o #8; resultado em `CHANGELOG_DEV.md`)*

**Objetivo:** garantir que Produto, usos permitidos e Receitas estejam consistentes com Empresas, Inventário, Mercado e Militar.

Critérios:
- Petróleo pertence a Extrativismo;
- usos de produtos são compatíveis com empresas consumidoras;
- receitas possuem estrela mínima quando aplicável;
- múltiplos ingredientes são suportados;
- catálogo é utilizável como fonte única de seed.

**Decisões do Game Director a aplicar (2026-10-14):**
- Valores numéricos `[PROV]` autorizados (Nutrição/QoL dos alimentos, preço-base e taxa de correio, rendimento, estrelas e rendimentos de Matriz, hospitalização por severidade, custos de milícia, multiplicadores militares) em tabela auditável com fonte de verdade; base de receita: 1 unidade de cada ingrediente produz 1 unidade do produto.
- Receitas militares do Exército (Industrial, 2★ `[PROV]`): Armas Militares = Aço + Madeira + Plástico; Armaduras Militares = Aço + Plástico; Kits de Primeiros Socorros do Exército = Lã + Materiais hospitalares. Nomes: Armas Improvisadas, Armaduras Improvisadas e Kit Médico Improvisado (milícia), distintos dos produtos do Exército, com identidades estáveis próprias.
- Pão é alimento consumível, com perfil `[PROV]`.
- Cinco categorias principais únicas (Alimento, Material, Equipamento, Durável, Militar); consumível, permanente, militar e uso em receita ficam em campos/tags separados.
- Sem produto Acabamentos: a Construtora usa Tábuas e Vidro diretamente.
- Usos comerciais declarados no catálogo, nunca inferidos: Varejo vende bens finais; matérias-primas e intermediários circulam entre empresas; Exército por contrato federal; Requisições Especiais da milícia (`19`); produtos exclusivos do Exército não vão ao Varejo; sem canal de venda direta entre inventários pessoais.
- Integrar as categorias do subsídio setorial (D16) ao catálogo e suas permissões.
- Materiais operacionais (`02` §10/§20) ficam fora da primeira implementação de Empresas.

---

## [x] P0.07 — Registro monetário (ledger)  *(P0.07a aprovada; P0.07b implementada em 2026-10-16; ambas mergeadas em `main`, PRs #10 e #11)*

Pré-requisito transversal: não existe sistema de dinheiro em nenhum documento nem na fila. Posição: depois de P0.01 e P0.02, antes de P1.02. Duas fases:

- **P0.07a — Documento de design** — **aprovado em 2026-10-15** como `design/24-Registro-Monetario-FINAL-BOT-TEST.md` (PR #10); teto de déficit decidido (`24` §24.16, implementação na P1.09/P1.12);
- **P0.07b — Implementação** — **implementada em 2026-10-16** na branch `dev/p0.07b-ledger` (app `ledger`; PR #11 mergeado em `main`). Decisões técnicas em `24` §24.19.1 e `CHANGELOG_DEV.md`.

**Decisões do Game Director já aprovadas (2026-10-14):**
- **Origem do dinheiro:** dotação inicial explícita e auditável por conta (humana ou Bot) conforme parâmetro do cenário; lançamento de emissão com natureza, origem, destino e referência ao cenário. Como Bots são criados continuamente até a população-alvo, é uma fonte de emissão durante a formação da população, não uma emissão única. Emissão total e contas contempladas aparecem nas métricas financeiras. Zero é válido se escolhido explicitamente; valor ausente faz o cenário recusar a inicialização e registrar a pendência. Sem emissão periódica discricionária pela União; despesas, títulos e transferências não criam dinheiro.
- **Destino das cobranças:** viagem, taxa de correio e fundação de empresa → caixa federal; leilão de lote público → caixa do Município do lote; fundação e melhorias de milícia → sumidouro explícito; custos de campanhas → caixa federal como pagador, destino final no sumidouro; tratamento → conta do hospital ou do prestador definido em `04` §13 (já definido; o ledger integra esse pagamento, sem reabrir o destino).
- **Sumidouro:** conta contábil identificada, indisponível para gastos normais, com saldo na conservação contábil e excluído do dinheiro em circulação; lançamentos nunca são apagados.

**O P0.07a deve incorporar:**
- sistema de contas para jogadores, empresas, União, Estados, Municípios, milícias, contas de retenção e sumidouro;
- transferências atômicas e idempotentes; log auditável; conservação monetária com origem e destino explícitos; sem saldo negativo; precisão em centavos; detalhamento `Explained` (`20`);
- obrigações pendentes separadas do caixa;
- **dois contadores salariais diários** (`C_S` e `C_T`), natureza do lançamento e dia de competência (`11` 11.1.0), com cálculo determinístico independente da ordem dos serviços;
- retenções de contrato (Requisição Especial, fornecimento ao Exército) e retenção de arrecadação durante ações de milícia (`09` §45, `19`);
- dotações de cenário (contas, caixas de governo, estoques iniciais);
- relação com títulos e dívida pública: P1.09 não cria dinheiro por emissão de dívida e declara a origem dos recursos;
- teto de déficit público: proposta após esta arquitetura.

**Em aberto:** apenas os valores de dotação inicial por cenário (configuração, não bloqueia o P0.07a/b).

---

## [x] P0.03 — Fundação temporal  *(concluído em 2026-09-30, branch `dev/fase1-fundacao`)*

Implementar o motor de tempo, ticks e processamento lazy conforme `04 — Dia a Dia`.

Critérios:
- tick determinístico;
- processamento por acesso/ação/ciclo conforme necessário;
- testes de avanço temporal;
- nenhuma mecânica depende de polling excessivo.

Entregue: `core.timeline`, `core.clock`, `core.ticks`, comandos `world_clock` / `advance_world`.
Tempo = calendário real no fuso do jogo, com ticks horário/diário/semanal/mensal; velocidade acelerável (Bot Test).
Fora deste bloco (entra quando um sistema precisar): eventos agendados pontuais (Scheduled Event).

---

## [x] P0.04 — Player state + Energy/QoL/Health/Nutrition  *(concluído em 2026-10-01, sobre o `04` FINAL)*

Implementar o estado base do jogador e as regras fundamentais de `04`.

Critérios:
- Energia;
- QoL;
- Saúde;
- Nutrição;
- burnout;
- estados críticos com histerese quando aplicável;
- testes das transições.

Entregue: app `players` (`Player`, `QolEffect`, `rules`, `services`, `qol`, `balance`), `core.breakdown` (detalhamento
estruturado do doc 20) e `TickKind.TEN_MINUTES`. Parâmetros `[PROV]` e interpretações: `CHANGELOG_DEV.md` (2026-10-01).
Fica para quando o sistema dependente existir: Tratamento (dinheiro), auto-consumo de alimentos (P1.02a, depende do Inventário),
Recuperação Regional (saúde/médicos). *(O bloqueio por Viagem foi implementado no P0.06.1.)*

---

## [x] P0.05 — Skills  *(concluído em 2026-10-02, sobre o `01` em REVIEW)*

Implementar `01 — Skills`.

Critérios:
- Inteligência, Físico e Carisma;
- progressão sem teto artificial;
- ganho por trabalho/estudo conforme documentação;
- especialização;
- requisitos baseados em skill;
- testes.

Entregue: app `skills` (3 skills, ganho por atividade com detalhamento, requisitos, Especialização do `02 §13`, perfil
emergente), `players/hooks.py` (integração sem caminho paralelo). Decisões abertas do `01` isoladas como pontos de extensão,
não fechadas: ver `CHANGELOG_DEV.md` (2026-10-02). Depende de outros sistemas: cargo/skill relevante (Empresas), qualidade da
escola e cursos (Escolas), teto salarial diário (dinheiro), nível inicial (criação do jogador).

---

## [x] P0.06 — Geografia  *(concluído em 2026-10-03, sobre o `08` FINAL; decisões do Game Director aplicadas)*

Implementar `08 — Geografia`.

Critérios:
- Estado → Cidade → Bairro → Lote;
- capacidade de lotes;
- zonas;
- áreas rurais;
- recursos espaciais conforme documentação;
- testes de integridade territorial.

- ## [x] P0.06.1 — Localização do jogador e viagem básica  *(concluído em 2026-10-06; revisado em 2026-10-07 com as decisões do Game Director)*

**Objetivo:** complementar a Geografia com a localização física do jogador e implementar o núcleo mínimo de viagem necessário para que outros sistemas possam depender de localização.

**Escopo:**

* Vincular cada jogador a um `Lote` como sua localização atual.
* Definir a localização inicial do jogador (decisão do GD: pode ser a capital; moradia inicial garantida, básica, neutra em QoL, sem consumir capacidade).
* Permitir iniciar uma viagem para outro `Lote`.
* Calcular a distância entre origem e destino usando a métrica de distância definida pela Geografia.
* Calcular o tempo-base de viagem usando `distância × minutos_por_unidade`, com `15` minutos por unidade como parâmetro padrão atual.
* Calcular o custo monetário da viagem, parametrizado pela distância (`custo_por_unidade`, valor de calibração do Bot Test), com ponto de extensão para modificadores futuros de veículos.
* Registrar o estado de viagem do jogador (`em_viagem` ou equivalente).
* Impedir ações que exigem presença (Trabalho e Estudo; Lazer e Tratamento não) enquanto o jogador estiver viajando. Nenhum estado do jogador impede iniciar a viagem.
* Concluir a viagem de acordo com o sistema de tempo/ticks existente e atualizar a localização do jogador para o lote de destino.
* Garantir que a viagem respeite os mesmos princípios de atomicidade, determinismo e uso do sistema de tempo já estabelecidos.
* Criar testes para localização inicial, início de viagem, cálculo de distância, duração, conclusão da viagem e bloqueio de ações durante viagem.

**Entregue:** app `travel` (`PlayerLocation`, `Journey`, serviços, handler de chegada, integridade) e pontos de integração aditivos em `players.hooks`. Decisões do Game Director e interpretações técnicas: `CHANGELOG_DEV.md` (2026-10-06, revisão de 2026-10-07).

**Fora do escopo:**

* Veículos e seus modificadores de velocidade.
* Transporte público.
* Compra, venda ou aluguel de imóveis.
* Sistema imobiliário completo.
* Regras avançadas de transporte.
* Qualquer mecânica de `10 — Imóveis e Zonas` que não seja necessária para estabelecer a localização do jogador.
* Reduções de tempo de viagem provenientes de veículos ou outros sistemas futuros.
* Combustível, manutenção e transporte completo.

**Dependências:**

* **P0.03 — Fundação temporal** (motor de tempo/ticks, `core`). *(O arquivo `03` do `design/` é Escolas, não o sistema de tempo.)*
* `04 — Jogador e ações`
* `08 — Geografia`

**Resultado esperado:**
Ao final desta task, todo jogador possui uma localização física válida dentro do mundo e pode se deslocar entre lotes utilizando uma viagem baseada na distância geográfica. Sistemas futuros podem utilizar a localização do jogador sem precisar implementar novamente essa fundação.

**Observação:** `15 minutos por unidade de distância` é um parâmetro inicial de calibração do Bot Test, não um valor definitivo de balanceamento.


Entregue: app `geography` (hierarquia com coordenadas, bairros concentrados, lotes e capacidades, zoneamento parametrizável com
ponto de extensão para leis, recursos espaciais, cenário/seed, geração determinística, integridade, comandos `generate_world` e
`check_world`), mais o tempo-base de viagem (`distância × minutos_por_unidade`, 15 inicial). Decisões do Game Director em
`CHANGELOG_DEV.md` (2026-10-03). Fora: propriedade/leilão (P1.07), veículos e modificadores de viagem (sistema de viagem).

---

# P1 — Núcleo econômico e interação

## [x] P1.01 — Produtos, Receitas e usos  *(implementado em 2026-10-11; PR #6 mergeado em `main`)*

Implementar a estrutura central de `22`.

**Entregue:** app `catalog` (`Product`, `Recipe`, `RecipeInput`, `FoodProfile`; ids estáveis; `sync_catalog`/`check_catalog`; consultas derivadas; integridade com erro x pendência de design). O `22` atual é **incompleto**: só entrou o que ele declara; lacunas e pendências em `CHANGELOG_DEV.md` (2026-10-11). Valores não especificados (quantidades, rendimento, Nutrição, intensidade de QoL, estrelas das Matrizes) ficam `NULL`, **distintos de zero**, e quem os usa recusa com `UNSPECIFIED_DESIGN_VALUE`.

## [x] P1.02 — Inventário  *(implementado em 2026-10-18, branch `dev/p1.02-inventario`; PR #12 aberto; aguarda revisão e autorização do GD)*

**Depende de P0.07.**

> **Pendências herdadas do P1.01:** as quatro (`GAP_FOOD_VALUES_UNDEFINED`, `GAP_FOOD_PROFILE_BREAD_UNDECLARED`, `GAP_INVENTORY_CATEGORIES_UNDEFINED`, `GAP_BASE_PRICE_UNDEFINED`) foram resolvidas na P0.02; nenhuma bloqueou. **Entregue:** posse, trilha imutável, `consume`, `send_item` (Correio), `audit_inventory`. **Fora deste PR (segue no Bot Test, etapas próprias):** Auto-consumo (P1.02a, abaixo; regra já definida em `04` §16, sem decisão pendente), Mercado de Jogadores (P1.05), Varejo/compra (P1.04), estado ativo (Roupas/Imóveis/Veículos).

Implementar `05`.

## [x] P1.02a — Auto-consumo de alimentos  *(implementado em 2026-10-19, branch `dev/p1.02a-auto-consumo`, PR empilhado sobre o #12; aguarda revisão e autorização do GD; obrigatório no primeiro Bot Test; regra em `design/04` §16)*

Implementar o §16 integralmente: o jogador habilita o Auto-consumo no Inventário e escolhe um alimento preferido; quando `Nutrição < 10`, durante o processamento lazy, o sistema consome automaticamente (1º alimento preferido, se houver; 2º o alimento disponível de menor ganho de Nutrição), repete enquanto Nutrição < 10 e houver alimento elegível, para ao atingir/ultrapassar 10, não faz nada sem alimento elegível, usa exatamente as regras do consumo manual (sem bônus) e o efeito de Comida substitui o anterior. Sem verificação contínua por jogador.

**Entregue** (`CHANGELOG_DEV.md`, 2026-10-19): configuração persistida e ação no registro; hook de acesso sem recursão sobre o núcleo `consume_locked`; trilha/auditoria; testes (inclui PostgreSQL). Critérios: preferência/habilitação persistidas e expostas pelo Action Registry; integração com `players.services._catch_up()` **sem recursão** (`_catch_up` → hook → consumo → `sync_player` → `_catch_up`); mesma regra de negócio do `consume()` sobre o jogador já travado; desempate determinístico entre ganhos iguais (detalhe técnico registrado; só vai ao GD se afetar o gameplay de forma material); testes: preferido, alternativa de menor ganho, consumo repetido, parada, sem elegível, integridade de inventário/Nutrição/auditoria, não-recursão, concorrência no PostgreSQL.

---

## [x] P1.03 — Action Registry  *(implementado em 2026-10-12; PR #7 mergeado em `main`)*

Criar registro compartilhado das ações de jogo, com requisitos, custos, alvos e validação.

**Entregue:** `players/registry.py` e `travel/registration.py`: ações `work`, `study`, `leisure`, `travel` com descritor do `21 §20` (categoria/visibilidade `UNSPECIFIED`, cooldown `NONE`), `check_action`/`available_actions`/`execute_action`, preview com `Explained`, alvo (Viajar) distinguindo disponibilidade geral de validação de destino, parâmetros internos protegidos. Disponibilidade e execução compartilham `action_refusal`/`travel_refusal`; o serviço dono revalida. Decisões e pendências em `CHANGELOG_DEV.md` (2026-10-12).

> **Pendências para blocos futuros:** Empresas (P1.04) e Escolas devem plugar bloqueios/contexto de atividade pelos mecanismos existentes (provedores de bloqueio, `ActivityContext`, hooks), sem caminho de execução separado; Máscara de Ações (`21 §21`) é o **P1.19**; categoria/visibilidade/cooldown dependem de decisão do GD.

## [~] P1.04 — Empresas  *(dividida em fatias de execução; P1.04a implementada em 2026-10-19; o restante segue no Bot Test)*

**Depende de P0.07.** Decisões aprovadas (2026-10-14): o Dono recebe salário associado ao cargo, pago pela conta da empresa e sujeito a `S` e `T`; sem retirada de lucro, dividendos ou distribuição passiva; propriedade não equivale a receber dinheiro; sem exceção às regras de `06.23`. Materiais operacionais ficam fora desta primeira implementação (limitação conhecida; nenhum insumo oculto é cobrado).

> **Herdado do P1.03:** Trabalho sem emprego continua permitido hoje (P0.04). Empresas deve acrescentar emprego/contexto de atividade via provedor de bloqueio e `ActivityContext`, usando o Action Registry existente (sem caminho paralelo). Decisão do GD (2026-10-12) em `CHANGELOG_DEV.md`.

> **Pendências herdadas do P1.01 (decisões do GD antes de implementar; consultar antes de escolher `[PROV]`):** `GAP_FINISHINGS_UNDEFINED`, `GAP_OPERATIONAL_MATERIALS_UNDEFINED`, `GAP_MATRIZ_STARS_UNDEFINED`, `GAP_PRODUCTION_QUANTITIES_UNDEFINED`, `GAP_COMMERCIAL_USES_UNDECLARED`. A produção deve consultar `catalog.services.check_production_ready` e **recusar** enquanto houver `UNSPECIFIED_DESIGN_VALUE`. Ver `CHANGELOG_DEV.md` (2026-10-11).

**Decisão do GD (2026-10-15):** os produtos militares do Exército são produzidos por empresas **Industrial / Produção** (usar `catalog.services.producer_sector_of`); permanecem distintos dos produtos improvisados da milícia.

Implementar `02` utilizando `22` como fonte de produtos/receitas. **Fatias** (ordem de execução; nenhuma sai do escopo do primeiro Bot Test):

- **[x] P1.04a — Núcleo** (branch `dev/p1.04a-empresas-nucleo`, PR empilhado sobre o #14; `CHANGELOG_DEV.md`, 2026-10-19): tipos, fundação com custo (`02` §17), conta da empresa, cargo Dono (`02` §16), aporte de capital, `audit_companies`.
- **[x] P1.04b — Cargos, mural e salários** (branch `dev/p1.04b-cargos-mural`, PR empilhado sobre o #15; `CHANGELOG_DEV.md`, 2026-10-20): vagas e mural público com requisitos, candidatura/aprovação só pelo Dono, um emprego (Dono não conta), salário por ação de Trabalhar e folha diária do Dono pelo registro de remuneração (`PENDING`, quitação mais antiga primeiro), provedor de atividade e limites W/S/T. Decisões do GD (2026-10-19) em `02` §25.
- **[x] P1.04c — Produção e estoque** (branch `dev/p1.04c-producao-estoque`, PR empilhado sobre o #16; `CHANGELOG_DEV.md`, 2026-10-20): estoque empresarial com trilha imutável e capacidade por estrela, `set_production` (um produto por vez, setup e cooldown), Trabalho do funcionário produz (skill/especialização, qualidade média com teto de estrela, insumos), bloqueio antes de gastar Energia, invariantes 8–10. Custo fixo da troca (`24` sem natureza), terreno da Matriz (P1.07) e materiais operacionais registrados como lacunas/integrações.
- **[x] P1.04d — Suporte** (branch `dev/p1.04d-suporte`, PR empilhado sobre o #17; `CHANGELOG_DEV.md`, 2026-10-20): Engenheiro (bônus diário de produção), Advogado (multiplicador de risco de Burnout de Trabalhar/Estudar, piso 1%, via `register_burnout_risk_provider`), vagas por estrela, invariante 11. Valores `[PROV]` e lacunas no CHANGELOG.
- **[x] P1.04e — Varejo e Construtora** (branch `dev/p1.04e-varejo-construtora`, PR empilhado sobre o #18; `CHANGELOG_DEV.md`, 2026-10-21): permissões de compra pelos usos do catálogo (`trade`), capacidade de venda × estoque (`retail.fulfill_sale`), obra ativa por vez com progresso por Trabalhar e ponto de conclusão para P1.07 (`construction`), invariantes 12–13. Lote/contrato da obra, cancelamento e materiais registrados como lacunas.
- **[ ] P1.04f — Progressão de estrelas** (`02` §25.1; `design/02a`): ação "Melhorar empresa" paga pelo caixa da empresa com custo crescente por estrela, registro imutável e auditoria. **Só depois** de o GD responder as lacunas 1–4 da proposta (natureza/destino do pagamento, estrelas não diminuem, base do custo, faixa máxima).
- **Localização/ocupação** (`10` §29): integra com **P1.07**; consumo operacional (`02` §10): materiais operacionais seguem como limitação conhecida da primeira implementação de Empresas (Q10), a retomar na sua fase de integração.

**Decisões do GD (2026-10-19):** estrelas começam em 1★ `[PROV]` e sobem por melhorias pagas pelo caixa (proposta em `design/02a`); salários sem caixa usam `PENDING`; só o Dono aprova candidatos. **Dependência registrada:** a lei antitruste de `11` §11.1 (máximo de empresas do mesmo tipo por proprietário, padrão 1) precisa de um ponto de recusa em `found_company` quando P1.12 existir.


## [~] P1.05 — Mercado e transparência

**Depende de P0.07.**

- **[x] P1.05a — Transparência de Mercado** (branch `dev/p1.05a-transparencia-mercado`, PR empilhado sobre o #19; `CHANGELOG_DEV.md`, 2026-10-22): app `market` com histórico imutável (`record_sale`, ponto único de integração), agregados diários, estatísticas, custos da empresa e auditoria (`17`).
- **[ ] P1.05b — Mecanismo do Mercado** (Varejo/preço, Mercado de Jogadores, compra entre empresas, taxas, oferta): **bloqueada por decisão do GD** — lacunas 1–6 em `design/17a-mercado-PROPOSTA.md` (não definido em nenhum documento; `05` §22). Ao decidir: ligar pagamento + `record_sale` + estoque na mesma transação e registrar o provedor de oferta.

> **Pendências herdadas do P1.01:** `GAP_BASE_PRICE_UNDEFINED`, `GAP_PRODUCTION_QUANTITIES_UNDEFINED`, `GAP_COMMERCIAL_USES_UNDECLARED` (`CHANGELOG_DEV.md`, 2026-10-11).

Implementar mercado e estatísticas de `17`.

## [~] P1.06 — Escolas e universidades

**Depende de P0.07 se houver custos.** Proposta e lacunas: `design/03a-escolas-PROPOSTA.md`.

- **[x] P1.06a — Núcleo de Escolas** (branch `dev/p1.06a-escolas-nucleo`, PR empilhado sobre o #20; `CHANGELOG_DEV.md`, 2026-10-22): escola pública por bairro, matrícula inicial e troca no bairro, capacidade por provedor, materiais/decaimento/qualidade diária, auditoria.
- **[ ] P1.06b — Funcionários, professores e mensalidade** (`03` §5.1, §6.1, §10-§12, §24): cargos de escola, salários (remuneração do ledger), trabalho do professor → bônus de qualidade, mensalidade diária e expulsão. Decisões 3–6 da `03a` (valores ausentes entram como `[PROV]`).
- **[ ] P1.06c — Universidade e diplomas** (`03` §17-§23): cursos, requisitos, matrícula única, estudo, abandono, diploma. Decisões 9–11 da `03a`.
- **[ ] P1.06d — Ligações**: capacidade ← Imóveis (P1.07), financiamento público ← Orçamento (P1.09), compra de materiais ← Mercado (P1.05b), construção de escolas.

## [ ] P1.07 — Imóveis e zonas

> **Herdado do P0.06/P0.06.1:** a localização do jogador (lote atual) e a viagem já existem (`travel`). Este bloco precisa do vínculo de **residência/moradia** (`05` "Residência ativa"), distinto da localização, de que dependem moradia/QoL estrutural. Ver `CHANGELOG_DEV.md` (2026-10-06).

> **Pendência herdada do P1.01:** `GAP_FINISHINGS_UNDEFINED` (Acabamentos da Construtora; `CHANGELOG_DEV.md`, 2026-10-11).

Implementar `10`.

## [~] P1.08 — Contratos

**Depende de P0.07.** Adendo de partes militares (milícia anônima; governo federal comprador): `18` 18.14.

Implementar `18`.

- **[x] P1.08a — Motor, Fornecimento e Empréstimo** (branch `dev/p1.08a-contratos`, PR empilhado sobre o #21; `CHANGELOG_DEV.md`, 2026-10-23; lacunas em `design/18a`).
- **[ ] P1.08b — Aluguel** (handler; chega com P1.07) e contratos de obra da Construtora.
- **[ ] P1.08c — Governamental** (handler; chega com P1.09).
- **[ ] P1.08d — Fluxos militares A e B** (`18` 18.14; chega com P1.17).

---

# P1 — Governo e política

## [ ] P1.09 — Orçamento público

**Depende de P0.07.** Não pode criar dinheiro por emissão de dívida; deve declarar a origem dos recursos. Pisos setoriais só no orçamento municipal, base de 30 dias para os três pisos (`11` 11.2.1); teto de déficit sem proposta até o P0.07a. Atribuição territorial da arrecadação e retenção: `09` §45.

Implementar `09`.

## [ ] P1.10 — Processo legislativo

Implementar `07`.

## [ ] P1.11 — Política

**Depende de P0.07** (salários). Depois da consolidação de `06` e `11`, implementar cargos, eleições, Câmara, administração e sucessão.

Ações, validações e telas pendentes registradas pela consolidação P0.01 (sem implementação ainda): indicar/alterar substituto com histórico; eleição extraordinária por substituto inelegível/indisponível; vacância até a posse com prazos suspensos; sorteio auditável por semente; dois contadores (mandatos consecutivos x concluídos); crédito de serviço anterior por cenário; exceção de posse por deposição. Risco R-BT-01: o cenário inicial não pode deixar territórios inoperantes (contas reais de bots com residências; sem NPC e sem exceção de elegibilidade).

## [ ] P1.12 — Leis paramétricas

Depois de `11` FINAL, implementar o motor de parâmetros legais.

---

# P1 — Camadas de informação

## [ ] P1.13 — Feedback estruturado

Implementar o padrão arquitetural de `20` para fórmulas compostas.

## [ ] P1.14 — Histórico do Mundo

Implementar `12`.

## [ ] P1.15 — Rankings

Implementar `14`.

## [ ] P1.16 — Sitemap / UI shell

Usar `SITEMAP-REVIEW.md` para construir a navegação principal sem bloquear ajustes de UX posteriores.

---

# P1 — Militar

## [ ] P1.17 — Militar

**Depende de P0.07 e da P0.02** (produtos militares). Decisões aprovadas: multiplicadores de patente fixos `[PROV]` (Militar 1×, Capitão 2×, General 4×, Marechal 6×; não são leis); combate não reduz Saúde nesta versão; fallback da QoL nacional (último snapshot válido; sem snapshot, multiplicador 1). Dependências de execução em `19` 19.48. Implementar Milícia, Exército, mobilização, prontidão, treinamento, conflito e integração econômica.

---

# P1 — Bot Test

## [ ] P1.18 — Bot Test: infraestrutura

Implementar a infraestrutura não dependente do modelo neural:

- entidade Bot;
- identidade administrativa;
- Population Controller;
- scheduler individual;
- seeds;
- registros de ações/decisões;
- armazenamento de experiência;
- exportação de execução;
- Dashboard técnico básico.

## [ ] P1.19 — Bot Test: modelo híbrido RL

Implementar o agente de RL híbrido:

- observação limitada ao conhecimento de jogador;
- Action Registry;
- Action Masking;
- reward configurável por perfil;
- exploração configurável;
- memória individual;
- modelo compartilhado;
- checkpoints versionados.

## [ ] P1.20 — Bot Test: 10 arquétipos

Implementar combinações-base de:

- Casual;
- Otimizador;
- Conservador;
- Explorador;
- Caótico;
- Empreendedor;
- Político;
- Especialista;
- Social;
- Adversarial.

Arquitetura deve separar personalidade, objetivo e especialização.

## [ ] P1.21 — Bot Test: dashboards completos

Implementar:

- dashboard geral;
- dashboard por arquétipo;
- dashboard por objetivo;
- dashboard por especialização;
- dashboard individual;
- plano/intenção;
- decisão;
- conhecimento;
- replay;
- anomalias;
- cobertura de testes;
- performance;
- treinamento;
- exportação.

## [ ] P1.22 — Bot Test: detecção de lacunas

Implementar detecção de:

- sistemas pouco experimentados;
- carreiras pouco utilizadas;
- objetivos pouco representados;
- etapas não alcançadas;
- concentração econômica;
- falências em cadeia;
- repetição improdutiva;
- falha de aprendizado;
- falta de oportunidade.

---

# P2 — Pós-estabilização do Bot Test

## [ ] P2.01 — Revisão After Bot Test

Usar resultados reais dos Bots para revisar balanceamento, UX e gargalos arquiteturais.

## [ ] P2.02 — Melhorias avançadas de UX

Aprimorar navegação, visualização, filtros e dashboards conforme uso observado.

## [ ] P2.03 — Melhorias do modelo RL

Ajustar arquitetura, recompensa, exploração e memória com base nos dados reais.

---

# FUTURO — Não implementar no primeiro Bot Test

- `13 — Eventos Aleatórios` completo;
- `15 — Jornalismo` como sistema de mídia dos jogadores;
- `16 — Sociedades e Ações` / Bolsa;
- comércio internacional/exportação;
- NPCs econômicos;
- sistemas judiciais completos;
- outras extensões explicitamente marcadas como FUTURO nos documentos.
