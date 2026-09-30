# Polis — CHANGELOG DEV

Registro das decisões importantes de design e desenvolvimento que precisam permanecer visíveis para os agentes.

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
- **Fuso do jogo: `POLIS_GAME_TIMEZONE`, padrão `America/Sao_Paulo`** (o `TIME_ZONE` já existente do projeto). *O Game Director não nomeou o fuso; confirmar.* Sem horário de verão hoje; o motor aguenta DST (testado com New York e Kolkata).
- Hourly: a cada 3600 s absolutos. Daily: 00:00 local. Weekly: **segunda 00:00 local** (`07`). Monthly: **dia 1, 00:00 local** (*o horário exato do tick mensal é suposição minha, análoga ao semanal*).
- Intervalos são (start, end]: sem perda nem repetição. Não há tick "retroativo" antes de o mundo existir.
- Ordem no mesmo instante: `TickKind` (horário, diário, semanal, mensal), depois `priority`, depois `name`. **Provisória**: o `04 §27` ainda lista a ordem como questão em aberto.
- Escopo sem handlers avança o ponteiro; handlers registrados depois não reprocessam o passado.
- Consequência da aceleração: com 1 dia = 10 min, um mês de calendário dura de 4h40 a 5h10 reais, e um jogador ausente por 1 dia real "perde" 144 dias de jogo (catch-up em lote).

### Pendências para o Game Director (nenhuma bloqueia o P0.03)
1. **Status divergente entre `TASK.md` e os arquivos de design:** `01` e `03` estão em FINAL no `TASK.md` mas `REVIEW` no cabeçalho do arquivo; `19` está REVIEW no `TASK.md` mas `FINAL — BOT TEST` no arquivo; `04` e `05` (REVIEW) não constam na lista. Tratado como REVIEW até decisão. A resolver em P0.01.
2. **Índices desatualizados:** `design/README.md` e `implicacoes-tecnicas.md` citam arquivos que não existem mais (`06-politica.md`, `09-financeira.md`, `10-futuro.md`).
3. **Ordem de processamento e classificação de tick por sistema** (`04 §27`): o motor aceita qualquer classificação, mas ela ainda precisa ser decidida sistema a sistema.
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
