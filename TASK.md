# Polis — TASK Atual

**Status:** EM EXECUÇÃO  
**Fase:** Transição de Design para Implementação  
**Responsável:** Claude (Dev)  
**Direção:** Game Director

---

# Objetivo atual

Preparar o repositório para iniciar a implementação do **primeiro Bot Test**, preservando as decisões de design consolidadas e evitando que o desenvolvimento avance sobre especificações ainda ambíguas.

O projeto já possui o núcleo de design amplamente consolidado. A prioridade agora é transformar as decisões estáveis em código incrementalmente testável.

---

# Situação dos documentos

## FINAL — BOT TEST

- `01 — Skills`
- `02 — Empresas`
- `03 — Escolas`
- `07 — Leis`
- `08 — Geografia`
- `09 — Orçamento Público`
- `10 — Imóveis e Zonas`
- `12 — Histórico do Mundo`
- `14 — Rankings`
- `17 — Transparência de Mercado`
- `18 — Contratos`
- `20 — Filosofia de Feedback ao Jogador`
- `21 — Bots para Testes de Beta`

## REVIEW / consolidação necessária

- `06 — Política` *(decisões aprovadas consolidadas em 2026-10-14; dependências de execução em 06.36)*
- `11 — Leis Paramétricas` *(idem; teto de déficit sem proposta; zoneamento por lei na P1.07)*
- `19 — Militar` *(volta a REVIEW por decisão do Game Director; dependências de execução em 19.48)*
- `SITEMAP-REVIEW.md`

## FUTURO / não bloquear o núcleo

- `13 — Eventos Aleatórios`
- `15 — Jornalismo`
- `16 — Sociedades e Ações`

## Catálogo central

- `22 — Receitas-Produção`

## Registro monetário

- `24 — Registro Monetário` *(FINAL — BOT TEST; aprovado pelo Game Director em 2026-10-15; implementação na P0.07b)*

O catálogo de `22` deve ser tratado como fonte central de Produtos e Receitas e revisado quanto à consistência antes de depender dele em larga escala.

---

# Correções conhecidas que não podem ser perdidas

## Política

- três cargos executivos: Presidente, Governador e Prefeito;
- Deputados na Câmara nacional;
- um cargo político por jogador;
- mandatos parametrizáveis; padrões: Presidente 6 meses, Governador 6 meses, Prefeito 4 meses, Deputado 6 meses;
- candidatura depende de requisitos definidos em `06` e `11`;
- Governador exige experiência anterior como Prefeito;
- Presidente exige experiência anterior como Governador e diploma de Engenharia, Direito ou Medicina;
- um jogador vota uma vez por eleição aplicável e pode votar em si mesmo;
- empate presidencial gera segundo turno entre empatados; empates dos demais cargos e da última vaga da Câmara usam sorteio auditável com semente registrada;
- leis nacionais no primeiro Bot Test;
- Governadores e Prefeitos podem encaminhar sugestões ao Presidente;
- político pode possuir empresa privada, mas empresa de político não pode receber contrato público;
- político não pode ser empregado de outra empresa enquanto ocupar cargo político;
- salário político é derivado do salário mínimo × multiplicador definido por lei;
- trabalho político real consome Energia e gera ganhos de skill próprios do cargo;
- deposição presidencial por milícia encerra a Câmara e gera nova eleição da Câmara;
- Governadores e Prefeitos permanecem após deposição presidencial;
- Constituição sobrevive a troca/deposição presidencial.

## Leis

- discussão: 3 dias;
- votação da Câmara: 3 dias;
- janela semanal fixa; propostas que entram fora da janela aguardam o próximo ciclo;
- aprovação por maioria absoluta da composição congelada;
- veto presidencial;
- derrubada de veto por 2/3 da Câmara;
- mudança de Presidente durante sanção/veto devolve a proposta à Câmara para nova votação;
- entrada em vigor no próximo weekly tick;
- leis não retroativas;
- propostas sobre o mesmo parâmetro não podem conflitar enquanto uma estiver ativa/em trânsito;
- histórico de versões e votos deve ser auditável.

## Leis Paramétricas

- vendas: 0–50%, padrão 5%;
- renda: 0–50%, padrão 5%;
- salário mínimo: R$0–R$1.000, padrão R$50;
- antitruste: 1–100, padrão 1;
- subsídio setorial: 0–75%, padrão 0;
- teto salarial: mínimo R$50, sem teto máximo político;
- educação: piso legal a ser consolidado na versão FINAL do documento;
- saúde: piso legal 1–30%, padrão 10%;
- infraestrutura: piso legal 1–30%, padrão 10%;
- déficit público: 0–50%, padrão 10%;
- multiplicadores salariais: Presidente 1–50 padrão 10; Governador 1–40 padrão 8; Prefeito 1–35 padrão 7; Deputado 1–35 padrão 7;
- IPTU: 0–50%, padrão 1%;
- teto de posse: 1–50, padrão 10, separado por jogador/empresa;
- controle de aluguel: 0–30%, padrão 10%, aplicado ao reajuste do contrato existente;
- idade mínima da conta para candidatura: 30–300 dias, padrão 90;
- Carisma mínimo: 0–100, padrão 10;
- experiência anterior para Governador e Presidente permanece parametrizável conforme `11`;
- limite de mandatos consecutivos: 1–10, padrão 2 (dois contadores: consecutivos x concluídos);
- duração de mandato: 2–8 meses, com padrões específicos por cargo;
- campanhas temporárias entram no processo legislativo completo e possuem duração/custo/intensidade parametrizados conforme `11`.

## Militar

- não existe cooldown entre Exército e Milícia;
- jogador pode entrar/sair de ambos conforme regras normais;
- Milícia e Exército usam produtos/recursos reais;
- conflito não cria equipamentos ou dinheiro do nada;
- resultado gera hospitalização/desgaste conforme regras do sistema;
- deposição presidencial usa a vitória correspondente conforme `19`.

## Feedback

- fórmulas compostas retornam valor + detalhamento estruturado;
- limites e condições devem aparecer no feedback quando relevantes.

## Bots

- RL híbrido;
- apenas informação que jogador teria;
- Action Registry compartilhado;
- Action Masking;
- recompensa por tipo/objetivo;
- exploração por tipo/perfil;
- memória individual;
- modelo compartilhado versionado;
- população-alvo inicial ≈ 1.000;
- criação padrão ≈ 1 Bot/minuto até a meta, com Population Controller para preencher lacunas;
- ambiente único contínuo;
- relógio padrão ≈ 1 dia de jogo / 10 minutos reais;
- logs e relatório exportáveis;
- dashboards completos;
- identificação automática de lacunas de cobertura.

---

# Tarefa de implementação imediata

## Fase 1 — Fundação do motor do jogo

Implementar ou consolidar as fundações necessárias para que os sistemas FINAL possam evoluir sem duplicação:

1. ciclo temporal e processamento lazy/scheduled;
2. Energia, regeneração, QoL, Saúde e estados básicos do jogador;
3. skills e progressão;
4. geografia Estado → Cidade → Bairro → Lote;
5. Produto, Receita, inventário e estoque empresarial;
6. Action Registry compartilhado;
7. estrutura de auditoria/eventos de domínio;
8. padrão de feedback estruturado definido em `20`;
9. base de testes de integração.

Não implementar ainda os sistemas FUTURO apenas por conveniência.

---

## Progresso da Fase 1

| Item | Estado |
|---|---|
| 1. ciclo temporal, lazy | **feito** (P0.03): ticks horário/diário/semanal/mensal em calendário real, `catch_up` por entidade, `advance_world`. Scheduled events pontuais: pendentes |
| 2. Energia/QoL/Saúde/Jogador | **feito** (P0.04), sobre o `04` FINAL: Energia, QoL Base/efetiva/Atual, Burnout Ativo, Saúde Crítica, Hospitalização, Nutrição. Pendente: Tratamento (depende de outro sistema); auto-consumo de alimentos = P1.02a (obrigatório no Bot Test; regra em `04` §16) |
| 3. Skills | **feito** (P0.05), sobre o `01` (REVIEW): 3 skills, ganho por atividade, requisitos, Especialização (`02 §13`); decisões abertas do `01` isoladas |
| 4. Geografia | **feito** (P0.06), sobre o `08`: Estado→Cidade→Bairro→Lote, zoneamento, recursos, integridade. Composição de lotes (leitura A), distância euclidiana e tempo-base de viagem (15 min/unidade, calibrável) fechados pelo Game Director |
| 4b. Localização e viagem | **feito** (P0.06.1): lote atual do jogador, localização inicial, viagem entre lotes (tempo `distância × minutos_por_unidade`, 15 inicial; custo monetário `distância × custo_por_unidade`, 10 provisório), início na capital, bloqueio por presença (Trabalho/Estudo sim; Lazer/Tratamento não), chegada pelo sistema de tempo. Decisões do Game Director registradas (2026-10-07); custo ainda não é cobrado: não existe sistema de dinheiro (ponto de integração pronto) |
| 5a. Catálogo de Produtos e Receitas | **feito** (P1.01) e **atualizado na P0.02** (2026-10-15, PR sobre o #8): 73 produtos, 44 receitas (inclui Exército), 8 alimentos (inclui Pão); categoria única + tags + canais comerciais declarados; valores `[PROV]` em tabela auditável (`catalog/provisional.py`, `manage.py list_provisional`); `22` §3/§4 geradas e conferidas por teste; lacunas restantes: `GAP_OPERATIONAL_MATERIALS_UNDEFINED`, `GAP_VEHICLE_RELATION_UNDEFINED` (produtor do Exército = Industrial/Produção, decidido pelo GD em 2026-10-15) (`CHANGELOG_DEV.md`, 2026-10-15) |
| 6. Action Registry | **feito** (P1.03): ações `work`, `study`, `leisure`, `travel` com descritor do `21 §20`, consulta (`check_action`, `available_actions`) e execução (`execute_action`) sobre as mesmas validações dos serviços; sem Masking (P1.19). Decisões e pendências em `CHANGELOG_DEV.md` (2026-10-12) |
| 0. P0.01 consolidação documental | **concluída e integrada** (PR #8, mergeado em `main`; 2026-10-14): decisões aprovadas documentadas; `06`/`11`/`19` seguem em REVIEW só por dependências de execução; P0.07 (registro monetário) criado na fila; próximos: P0.02, P0.07a, P0.07b |
| 0b. P0.02 catálogo `22` | **concluída e integrada** (PR #9, mergeado em `main`; 2026-10-15) |
| 0c. P0.07a registro monetário | **aprovada e integrada** (2026-10-15, PR #10 mergeado em `main`): `24` FINAL — BOT TEST; teto de déficit decidido (implementação P1.09/P1.12) |
| 0d. P0.07b registro monetário (código) | **implementada e integrada** (2026-10-16, PR #11 mergeado em `main`): app `ledger` com contas, lançamentos imutáveis, reservas, retenções genéricas, roteamento tributário, obrigações pendentes, contadores `C_S`/`C_T`/`C_P` com liquidação estável, dotações, sumidouro, integração da viagem, `audit_ledger`/`ledger_metrics`; 941 testes OK (PostgreSQL 16 completo; SQLite com 13 pulados que exigem PostgreSQL); emissão só pela via de dotação, validada contra o cenário ativo e auditada (invariante 18); configuração de dotações e ativação de cenários serializadas com a emissão sob um protocolo único de bloqueio (mutação: todos os cenários em ordem de pk como primeiro bloqueio; emissão: contas e depois um cenário; sem ciclo); ativar cenário só por `activate_scenario` (o ORM recusa a transição para ativo); linha de dotação imutável depois da primeira dotação, inclusive contra o ORM (`GRANT_LINE_LOCKED`, `GRANT_HISTORY_INCONSISTENT`). Próxima: P1.02 (Inventário) |
| 0e. P1.02 inventário | **implementado** (2026-10-18, branch `dev/p1.02-inventario`, PR #12 aberto sobre `main`; aguarda revisão e autorização do GD para merge): app `inventory` com posse, trilha imutável, ações `consume` e `send_item` (Correio com taxa pelo ledger), `audit_inventory`; `[PROV]`: taxa 10%, mínimo R$ 1,00, efeito de alimento 3600 s; 998 testes OK (PostgreSQL e SQLite); fora do escopo: Mercado, Varejo, estado ativo; Auto-consumo (`04` §16, obrigatório no Bot Test; sem decisão pendente) = P1.02a, abaixo (`CHANGELOG_DEV.md`, 2026-10-18) |
| 0f. P1.02a auto-consumo | **implementada** (2026-10-19, branch `dev/p1.02a-auto-consumo`, PR empilhado sobre o #12; aguarda revisão e autorização do GD): configuração + ação `auto_consumption`, hook de acesso sem recursão sobre o mesmo núcleo do consumo manual, trilha e invariante de auditoria; 1034 testes OK (PostgreSQL e SQLite); próxima: P1.04 Empresas (`CHANGELOG_DEV.md`, 2026-10-19) |
| 0g. P1.04a empresas (núcleo) | **implementada** (2026-10-19, branch `dev/p1.04a-empresas-nucleo`, PR empilhado sobre o #14; aguarda revisão e autorização do GD): app `companies` com fundação (custos do `02` §17), conta da empresa, cargo Dono, aporte de capital, `audit_companies`; 1059 testes OK (PostgreSQL e SQLite); restante de P1.04 em fatias b–e (`TASK_QUEUE.md`); lacunas de design resolvidas pelo GD em 2026-10-19 (estrelas: proposta em `design/02a`; salário: `PENDING`; mural: só o Dono) |
| 0h. P1.04b cargos, mural e salários | **implementada** (2026-10-20, branch `dev/p1.04b-cargos-mural`, PR empilhado sobre o #15; aguarda revisão e autorização do GD): `companies/jobs.py` (vagas, mural, candidatura, aprovação só pelo Dono, um emprego, saída), `companies/payroll.py` (salário por ação de Trabalhar, folha diária do Dono, `PENDING` + quitação, limites W/S/T), provedor de atividade em `players.hooks`, 8 ações no registro, invariantes 4–7 em `audit_companies`; 1116 testes OK (PostgreSQL e SQLite); próxima: P1.04c produção/estoque |
| 0i. P1.04c produção e estoque | **implementada** (2026-10-20, branch `dev/p1.04c-producao-estoque`, PR empilhado sobre o #16; aguarda revisão e autorização do GD): `companies/stock.py` e `companies/production.py` (estoque empresarial, `set_production`, produção no Trabalho, qualidade com teto de estrela), invariantes 8–10; 1148 testes OK (PostgreSQL e SQLite); próxima: P1.04d Engenheiro/Advogado |
| 5b, 7–9 | não iniciados

O código anterior ao design atual foi removido por decisão do Game Director (2026-09-30); `design/` é a única base.

---

# Critérios de aceitação da fase 1

- o jogador pode ser criado e possui estado inicial consistente;
- tempo do servidor pode avançar de forma determinística;
- Energia/QoL/saúde possuem testes;
- skills podem crescer segundo as regras documentadas;
- geografia básica funciona e possui relacionamentos corretos;
- Produtos/Receitas possuem fonte central;
- inventário/estoque não confundem posse com consumo;
- existe Action Registry reutilizável;
- ações inválidas são bloqueadas pelo mesmo mecanismo para jogador e Bot;
- uma fórmula composta consegue retornar valor + detalhamento;
- eventos importantes deixam registros auditáveis;
- testes automatizados cobrem os fluxos principais.

---

# Regra para o agente

Antes de iniciar qualquer tarefa dessa fase, conferir os documentos de design relacionados.

Se encontrar conflito entre código antigo e design consolidado, adaptar o código ao design documentado.

Se encontrar conflito entre dois documentos de design, não escolher silenciosamente: registrar a pendência em `CHANGELOG_DEV.md` e continuar apenas nas partes não afetadas.
