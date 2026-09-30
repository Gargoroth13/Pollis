# Polis — Regras Permanentes para Desenvolvimento com Claude

## 0. Propósito

Polis é uma simulação textual de vida, economia, empresas, política, cidades e interação entre jogadores.

O princípio central do projeto é:

> O sistema fornece regras e ferramentas; os jogadores produzem o comportamento do mundo.

Sempre que houver dúvida entre adicionar uma trava artificial e fornecer uma ferramenta que permita ao jogador tomar a decisão, priorizar a ferramenta. Travas devem existir quando forem necessárias para preservar integridade, evitar exploits ou manter o jogo funcional.

Este arquivo contém regras permanentes de desenvolvimento. Regras específicas de mecânicas pertencem aos documentos em `design/` e têm precedência para aquele sistema.

---

# 1. Fonte de verdade

A fonte de verdade do projeto é, nesta ordem:

1. decisões explicitamente consolidadas pelo Game Director;
2. documentos `design/` em estado `FINAL — BOT TEST`;
3. documentos `design/` em `REVIEW`, quando o trabalho solicitado explicitamente for sobre aquele documento;
4. `CHANGELOG_DEV.md`, para registrar decisões consolidadas e contexto histórico;
5. `TASK.md` e `TASK_QUEUE.md`, para prioridade de trabalho;
6. código existente, quando ainda não houver decisão de design correspondente.

Código existente não deve ser tratado como autoridade sobre uma mecânica que já foi redefinida nos documentos.

Quando houver conflito entre documentos, não inventar uma solução silenciosa. Registrar o conflito em `TASK.md` ou `CHANGELOG_DEV.md` e usar somente uma decisão explicitamente consolidada como base de implementação.

---

# 2. Status dos documentos

Fluxo de design:

```text
DRAFT
→ RESEARCH / DISCUSSION
→ REVIEW
→ FINAL — BOT TEST
→ IMPLEMENTED
→ REVIEW AFTER BOT TEST
```

### DRAFT
Ideia ainda não consolidada.

### RESEARCH / DISCUSSION
Decisão sendo estudada ou debatida.

### REVIEW
Estrutura praticamente definida, mas ainda pode sofrer alterações de design.

### FINAL — BOT TEST
Decisão fechada para implementação. Claude deve implementar a estrutura definida e não alterar a mecânica por conta própria. Parâmetros explicitamente indicados como ajustáveis podem ser calibrados durante testes.

### IMPLEMENTED
Mecânica documentada e implementada.

### REVIEW AFTER BOT TEST
Sistema já testado no ambiente real do Bot Test e aguardando ajustes de balanceamento ou arquitetura.

---

# 3. Papel do Claude

Claude atua como **Dev principal**.

Responsabilidades:

- implementar os documentos estáveis;
- criar e manter testes automatizados;
- preservar consistência entre sistemas;
- sinalizar conflitos e dependências;
- não inventar mecânicas relevantes;
- registrar decisões técnicas importantes;
- manter código simples, legível e modular;
- concluir tarefas de forma verificável.

O Game Director é o usuário. Decisões de design pertencem ao Game Director, não ao agente.

---

# 4. Processo de trabalho

Antes de alterar código:

1. ler `CLAUDE.md`;
2. ler `TASK.md`;
3. ler os documentos `design/` relevantes;
4. identificar dependências;
5. verificar o estado atual do código;
6. criar ou atualizar testes necessários;
7. implementar em passos pequenos e verificáveis.

Durante a implementação:

- não modificar arquitetura de design FINAL sem autorização;
- não adicionar sistemas futuros só porque seriam convenientes;
- não criar NPCs econômicos ou políticos;
- não criar dinheiro ou recursos sem origem econômica documentada;
- não duplicar regras que já pertençam a outro sistema;
- manter efeitos e custos auditáveis;
- preferir serviços/funções reutilizáveis a lógica duplicada nas views.

Depois da implementação:

- rodar testes relevantes;
- verificar migrações;
- verificar comportamento de borda;
- conferir se o fluxo pode ser reproduzido;
- registrar mudanças importantes em `CHANGELOG_DEV.md`;
- atualizar `TASK.md`/`TASK_QUEUE.md` quando o estado da tarefa mudar.

---

# 5. Regras fundamentais do jogo

## 5.1. Sem NPC econômico

Polis não utiliza NPCs como agentes econômicos no primeiro Bot Test.

Não criar consumidores fictícios, trabalhadores fictícios, eleitores fictícios ou dinheiro artificial para preencher o mundo.

Demanda econômica normal vem dos jogadores e dos usos reais dos Produtos.

Demandas externas futuras podem existir quando um sistema de comércio internacional for criado, mas isso não pertence ao primeiro Bot Test.

## 5.2. Conservação monetária

Transferências econômicas devem movimentar dinheiro existente.

Exemplos:

- salário sai da empresa/governo e entra no jogador;
- compra transfere dinheiro do comprador para o vendedor e impostos/taxas quando aplicáveis;
- multa transfere dinheiro de uma parte para outra;
- dívida cria obrigação e não dinheiro infinito.

Não criar dinheiro novo como efeito colateral de uma mecânica, salvo fontes explicitamente documentadas como criação monetária.

## 5.3. Produtos e estoque

`22 — Receitas-Produção` é a fonte central para produtos, usos e receitas.

Inventário do jogador e estoque empresarial são conceitos distintos, embora utilizem os mesmos Produtos quando aplicável.

Compras não significam consumo. Consumo deve ser uma ação/efeito real do sistema correspondente.

## 5.4. Ações do jogador

Bots devem utilizar o mesmo Action Registry e as mesmas validações das ações de jogadores reais.

Não criar um caminho privilegiado para Bots.

## 5.5. Energia, tempo e ciclos

Bots não podem ignorar Energia, cooldowns, requisitos, tempo, hospitalização ou outras restrições de gameplay.

Ambientes acelerados alteram apenas a passagem do tempo do servidor de teste, não as regras fundamentais.

---

# 6. Feedback e explicabilidade

`20 — Filosofia de Feedback ao Jogador` é uma regra transversal.

Toda fórmula composta nova deve retornar:

- valor final;
- detalhamento estruturado dos fatores;
- limites relevantes;
- regras condicionais relevantes.

A UI apresenta esse detalhamento. A regra de negócio não deve retornar apenas texto formatado para uma única tela.

Não reconstruir explicações posteriormente a partir de um número já calculado quando os componentes poderiam ter sido retornados desde a origem.

---

# 7. UI e navegação

`SITEMAP-REVIEW.md` define a estrutura lógica de navegação enquanto estiver em REVIEW.

A estrutura de UI deve priorizar:

- descoberta;
- coerência entre sistemas;
- acesso claro às ações;
- feedback suficiente antes e depois da ação;
- navegação consistente;
- diferenciação clara entre páginas públicas, privadas e administrativas.

Alterações visuais e refinamentos de UX podem ser feitos durante implementação sem alterar a mecânica dos sistemas.

---

# 8. Bot Test

`21 — Bots para Testes de Beta` é ferramenta de validação, não conteúdo do jogo final.

Princípios:

- população-alvo inicial de aproximadamente 1.000 Bots;
- criação padrão de aproximadamente 1 Bot por minuto até atingir a meta;
- Population Controller pode criar perfis adicionais quando existirem lacunas de cobertura;
- ambiente contínuo, sem necessidade de separar modos Beta/Simulation nesta fase;
- relógio acelerado padrão: aproximadamente 1 dia de jogo = 10 minutos reais;
- Bots utilizam apenas informação que jogadores normais teriam;
- Bots interagem entre si e, quando aplicável, com jogadores humanos;
- aprendizado principal: Reinforcement Learning híbrido com regras do jogo e Action Masking;
- sem LLM como mecanismo de decisão no primeiro Bot Test;
- modelo de aprendizado pode ser compartilhado, com memória/experiência individual;
- personalidade, objetivo e especialização são separados;
- reward varia conforme arquétipo/objetivo;
- exploração varia conforme arquétipo e perfil individual;
- todas as versões de modelo devem ser versionadas e reproduzíveis;
- Dashboard Dev/Admin deve expor estado, decisões, conhecimento, anomalias, treinamento e performance;
- logs devem ser estruturados e exportáveis.

Arquétipos-base iniciais documentados no 21:

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

Arquiteturalmente, os arquétipos não devem ser tratados como caixas rígidas. Personalidade, objetivo e especialização são dimensões combináveis.

---

# 9. Performance e dados

Não fazer cada pequena decisão de cada Bot depender de uma sequência excessiva de queries síncronas ao banco.

A simulação deve permitir batching e processamento eficiente quando necessário.

O ambiente deve medir, no mínimo quando o Bot Test estiver ativo:

- CPU;
- RAM;
- GPU;
- VRAM;
- tempo de tick;
- decisões por segundo;
- tempo de simulação;
- tempo de banco;
- tempo de treinamento;
- filas do scheduler;
- erros e timeouts.

O objetivo é descobrir o gargalo real antes de otimizar o componente errado.

---

# 10. Testes

Todo novo sistema deve incluir testes de:

- caminho normal;
- limites;
- permissões;
- estados inválidos;
- efeitos econômicos;
- transições de estado relevantes;
- idempotência quando aplicável;
- ciclos temporais quando aplicável.

Sistemas de gameplay devem testar não só funções isoladas, mas também integrações críticas.

---

# 11. Tarefas

`TASK.md` contém a tarefa que o agente deve executar agora.

`TASK_QUEUE.md` contém as próximas tarefas priorizadas.

Uma tarefa deve ser:

- pequena o suficiente para ser verificada;
- clara sobre arquivos/sistemas envolvidos;
- acompanhada de critérios de aceitação;
- atualizada ao terminar.

Não pegar uma tarefa de prioridade inferior enquanto existir uma tarefa superior não bloqueada, salvo instrução explícita.

---

# 12. Proibições importantes

Não:

- inventar mecânica de jogo sem decisão do Game Director;
- converter sistemas futuros em sistemas de Bot Test;
- criar NPCs econômicos para mascarar falta de jogadores;
- criar dinheiro infinito para facilitar teste;
- criar Action Registry separado para Bots;
- permitir que Bots vejam informações privadas ou futuras;
- usar LLM para decisão no Bot Test inicial;
- esconder falhas de teste por filtros que removam dados relevantes;
- apagar histórico técnico necessário para auditoria;
- substituir testes por inspeção manual quando teste automatizado for apropriado.

---

# 13. Regra de honestidade técnica

Se uma implementação não puder seguir uma especificação sem ambiguidade, parar no ponto da ambiguidade e registrar o problema.

Não completar lacunas de design com uma decisão silenciosa.

Se houver solução temporária puramente técnica que não altere a mecânica, ela pode ser utilizada desde que claramente registrada.
