# Polis — TASK QUEUE

Fila de implementação e consolidação para o primeiro Bot Test.

Prioridade:

- **P0** = bloqueia o avanço principal;
- **P1** = próxima implementação importante;
- **P2** = melhoria ou sistema posterior;
- **FUTURO** = fora do primeiro Bot Test.

---

# P0 — Antes / junto do início da implementação

## [ ] P0.01 — Auditoria final de documentos em REVIEW

**Sistemas:** `06`, `11`, `19`, Sitemap  
**Objetivo:** eliminar inconsistências remanescentes antes de depender desses documentos na implementação.

Critérios:
- nenhuma regra obsoleta permanece na versão de trabalho;
- decisões do Game Director aparecem consolidadas;
- inconsistências conhecidas são resolvidas ou explicitamente marcadas;
- versões FINAL ficam separadas das versões antigas.

---

## [ ] P0.02 — Auditoria do catálogo `22 — Receitas-Produção`

**Objetivo:** garantir que Produto, usos permitidos e Receitas estejam consistentes com Empresas, Inventário, Mercado e Militar.

Critérios:
- Petróleo pertence a Extrativismo;
- usos de produtos são compatíveis com empresas consumidoras;
- receitas possuem estrela mínima quando aplicável;
- múltiplos ingredientes são suportados;
- catálogo é utilizável como fonte única de seed.

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
Fica para quando o sistema dependente existir: Tratamento (dinheiro), auto-consumo de alimentos (Inventário),
Recuperação Regional (saúde/médicos), bloqueio por Viagem (Geografia).

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

## [x] P0.06 — Geografia  *(concluído em 2026-10-03, sobre o `08` FINAL; aguardando decisão de design aberta)*

Implementar `08 — Geografia`.

Critérios:
- Estado → Cidade → Bairro → Lote;
- capacidade de lotes;
- zonas;
- áreas rurais;
- recursos espaciais conforme documentação;
- testes de integridade territorial.

Entregue: app `geography` (hierarquia com coordenadas, bairros concentrados, lotes e capacidades, zoneamento parametrizável com
ponto de extensão para leis, recursos espaciais, cenário/seed, geração determinística, integridade, comandos `generate_world` e
`check_world`). **Antes do merge:** fechar a composição de lotes por bairro (`08 §4/§6/§11`), registrada em `CHANGELOG_DEV.md`
(2026-10-03). Fora: propriedade/leilão (P1.07), tempo de viagem (`04 §21`).

---

# P1 — Núcleo econômico e interação

## [ ] P1.01 — Produtos, Receitas e usos

Implementar a estrutura central de `22`.

## [ ] P1.02 — Inventário

Implementar `05`.

## [ ] P1.03 — Action Registry

Criar registro compartilhado das ações de jogo, com requisitos, custos, alvos e validação.

## [ ] P1.04 — Empresas

Implementar `02` utilizando `22` como fonte de produtos/receitas.

## [ ] P1.05 — Mercado e transparência

Implementar mercado e estatísticas de `17`.

## [ ] P1.06 — Escolas e universidades

Implementar `03`.

## [ ] P1.07 — Imóveis e zonas

Implementar `10`.

## [ ] P1.08 — Contratos

Implementar `18`.

---

# P1 — Governo e política

## [ ] P1.09 — Orçamento público

Implementar `09`.

## [ ] P1.10 — Processo legislativo

Implementar `07`.

## [ ] P1.11 — Política

Depois da consolidação de `06` e `11`, implementar cargos, eleições, Câmara, administração e sucessão.

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

Depois da limpeza final de `19`, implementar Milícia, Exército, mobilização, prontidão, treinamento, conflito e integração econômica.

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
