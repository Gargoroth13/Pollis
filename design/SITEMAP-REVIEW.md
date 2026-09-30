# Polis — Sitemap

**Status: REVIEW**

## 0. Objetivo

Este documento define a estrutura de navegação e a cobertura de interface do Polis.

Os documentos de design dos sistemas (`01` a `22`) definem as regras e mecânicas. O Sitemap define onde o jogador, o público, o Dev e o Admin encontram essas informações e ações na interface.

O Sitemap não deve ser tratado como uma estrutura definitiva de URL. Rotas, componentes e detalhes visuais podem ser alterados durante a implementação sem alterar a lógica dos sistemas.

O objetivo principal é garantir:

- que toda mecânica relevante possua uma interface coerente;
- que o jogador consiga descobrir como chegar a uma função;
- que páginas relacionadas estejam conectadas entre si;
- que ações importantes tenham uma tela ou fluxo claro;
- que Dev/Admin possuam ferramentas suficientes para observar e diagnosticar o servidor;
- que o Bot Test possua observabilidade completa;
- que nenhuma funcionalidade implementada fique escondida apenas no backend.

---

# 1. Princípios de navegação

## 1.1. Uma mecânica deve ser descobrível

O jogador não deve precisar conhecer o nome interno de um sistema para encontrá-lo.

Por exemplo, produtos, produção e empresas devem aparecer em uma estrutura de navegação natural, mesmo que internamente pertençam a aplicativos Django diferentes.

## 1.2. Páginas relacionadas devem possuir ligações diretas

Sempre que um objeto for exibido, quando fizer sentido, a interface deve permitir navegar diretamente para os objetos relacionados.

Exemplos:

- Produto → empresas que produzem/consomem o Produto;
- Empresa → seus Produtos, funcionários, localização e contratos;
- Imóvel → lote, proprietário, residência/empresa e localização;
- Escola → bairro, cursos e alunos quando aplicável;
- Lei → proposta, votação, autor e efeitos;
- Eleição → cargo, território e candidatos;
- Contrato → partes e objeto;
- Conflito → participantes e território;
- Notícia → objeto que originou a notícia.

## 1.3. Ações devem aparecer no contexto correto

Sempre que uma ação normalmente for executada a partir de uma informação já visualizada, a interface deve oferecer a ação naquele contexto.

Exemplo:

> Ao consultar um Produto, o jogador deve conseguir chegar à compra daquele Produto sem precisar descobrir novamente onde o Mercado fica.

## 1.4. Estado e ação devem ser distinguíveis

Uma página deve deixar claro:

- o que está acontecendo agora;
- quais informações são históricas;
- quais ações estão disponíveis;
- quais ações estão bloqueadas e por quê.

## 1.5. Feedback de fórmulas

Indicadores relevantes utilizam a filosofia definida em `20 — Filosofia de Feedback ao Jogador`.

Quando um número for composto ou determinante para uma decisão, a interface deve permitir abrir seu detalhamento.

---

# 2. Estrutura geral da interface do jogador

A interface do jogador possui uma estrutura global consistente, independentemente do sistema atual.

```text
POLIS
├── Início
├── Meu personagem
├── Dia a dia
├── Inventário
├── Trabalho / Carreira
├── Educação
├── Empresas
├── Mercado
├── Imóveis
├── Geografia
├── Política
├── Militar
├── Contratos
├── Notícias
├── Rankings
└── Ajuda / Sistema
```

A navegação pode aparecer como barra lateral, menu superior, menu móvel ou combinação desses elementos. A disposição visual não faz parte deste documento; a estrutura lógica sim.

---

# 3. Autenticação e entrada no jogo

```text
Autenticação
├── Entrar
├── Criar conta
├── Recuperação de acesso
└── Sessão / saída
```

Após autenticar:

```text
Entrada no jogo
↓
Dashboard do jogador
```

O primeiro contato deve conduzir o jogador para uma visão compreensível do seu estado atual e das ações relevantes disponíveis.

---

# 4. Dashboard do jogador

A página inicial do jogador é uma visão resumida do estado pessoal e das oportunidades disponíveis.

```text
Dashboard
├── Estado atual
│   ├── Dinheiro
│   ├── Energia
│   ├── Saúde
│   ├── QoL
│   ├── Nutrição
│   └── Localização
│
├── Skills
│   ├── Inteligência
│   ├── Físico
│   └── Carisma
│
├── Situação atual
│   ├── Trabalho
│   ├── Curso
│   ├── Residência
│   ├── Contratos ativos
│   └── Participações políticas/militares relevantes
│
├── Próximas ações relevantes
└── Alertas / pendências
```

O Dashboard não deve substituir as páginas dos sistemas. Ele funciona como ponto de entrada e resumo.

---

# 5. Meu personagem

```text
Meu personagem
├── Perfil
├── Skills
├── QoL
│   └── Detalhamento de fatores
├── Saúde
│   └── Detalhamento
├── Nutrição
├── Finanças pessoais
├── Histórico de carreira
├── Histórico educacional
├── Histórico político
├── Histórico militar
└── Atividade / tempo ativo
```

Quando um indicador composto estiver presente, sua explicação utiliza o padrão de `20`.

---

# 6. Dia a Dia

```text
Dia a dia
├── Estado atual
├── Energia
│   └── Explicação da regeneração
├── Trabalho
├── Estudo
├── Lazer / atividades disponíveis
├── Viagem / transporte
├── Hospital / recuperação
└── Histórico recente de ações
```

A interface deve informar requisitos, custo de Energia, tempo, efeitos e bloqueios relevantes antes de confirmar uma ação.

---

# 7. Inventário

```text
Inventário
├── Meus produtos
├── Quantidades
├── Item ativo / equipado, quando aplicável
├── Usar / consumir
├── Transferir
├── Histórico de operações
└── Detalhe do Produto
```

O detalhe de um Produto deve permitir navegar para sua página de Mercado e, quando aplicável, outros sistemas relacionados.

---

# 8. Trabalho e carreira

A estrutura deve permitir descobrir empregos, consultar requisitos e acompanhar a carreira.

```text
Trabalho / Carreira
├── Emprego atual
│   ├── Cargo
│   ├── Empresa
│   ├── Salário
│   ├── Requisitos
│   ├── Trabalho
│   └── Detalhamento do cálculo salarial
│
├── Vagas
│   ├── Lista de oportunidades
│   ├── Detalhe da vaga
│   └── Candidatura
│
├── Histórico profissional
└── Carreiras / especializações
```

A página não deve criar uma carreira paralela às skills e especializações definidas pelo jogo.

---

# 9. Educação

```text
Educação
├── Escolas
│   ├── Lista
│   ├── Buscar por localização
│   └── Página da escola
│
├── Universidades
│   ├── Lista
│   └── Página da universidade
│
├── Cursos
│   ├── Catálogo
│   ├── Requisitos
│   ├── Duração
│   └── Diploma / especialização obtida
│
├── Curso atual
│   ├── Progresso
│   ├── Energia
│   ├── Qualidade da instituição
│   └── Burnout / estado de estudo
│
└── Histórico educacional
```

A página de cada instituição deve permitir consultar qualidade e informações relevantes da escola/universidade sem criar uma pontuação diferente daquela definida pelo sistema de Educação.

---

# 10. Empresas

```text
Empresas
├── Explorar empresas
│   ├── Lista
│   ├── Filtros
│   └── Página da empresa
│
├── Minhas empresas
│   ├── Lista
│   ├── Criar empresa
│   └── Gerenciar empresa
│
├── Página da empresa
│   ├── Visão geral
│   ├── Proprietário
│   ├── Localização
│   ├── Tipo
│   ├── Estrelas
│   ├── Produção
│   ├── Funcionários
│   ├── Cargos
│   ├── Estoque
│   ├── Custos
│   ├── Qualidade
│   ├── Produto atual
│   ├── Contratos
│   └── Histórico
│
├── Vagas / contratação
├── Produção
└── Gerenciamento administrativo
```

Empresas podem navegar diretamente para:

- Produtos;
- Mercado;
- localização;
- funcionários;
- contratos;
- imóveis relacionados;
- histórico de custos;
- detalhes das fórmulas relevantes.

---

# 11. Mercado

```text
Mercado
├── Visão geral
├── Produtos
│   ├── Catálogo
│   └── Página do Produto
├── Comprar
├── Vender
├── Minhas ordens / transações, quando aplicável
└── Estatísticas
```

## Página do Produto

```text
Produto
├── Informações básicas
├── Usos permitidos
├── Preço médio
├── Menor preço
├── Maior preço
├── Estoque disponível
├── Produção
├── Consumo
├── Tendência
├── Gráfico de preço — 30 dias
├── Gráfico de oferta / produção / consumo — 30 dias
└── Empresas relacionadas
```

A página utiliza os dados definidos em `17 — Transparência de Mercado`.

O jogador não precisa acessar transações brutas individuais para compreender o mercado.

---

# 12. Imóveis

```text
Imóveis
├── Explorar imóveis
├── Lotes disponíveis
├── Meus imóveis
├── Meus aluguéis
├── Residência atual
├── Comprar lote
├── Comprar imóvel
├── Alugar
└── Página do imóvel
```

## Página do imóvel

```text
Imóvel
├── Localização
├── Tipo
├── Zona / uso
├── Proprietário
├── Ocupação
├── Qualidade
├── QoL associada, quando aplicável
├── Valor
├── Aluguel, quando aplicável
├── Contrato relacionado
└── Histórico
```

A navegação territorial deve permitir chegar do imóvel ao bairro, cidade e Estado.

---

# 13. Geografia

```text
Geografia
├── País
│   └── Estado
│       └── Cidade
│           └── Bairro
│               └── Lotes
│
└── Mapa / visualização territorial
```

Cada nível deve permitir navegar para o próximo e consultar os elementos relevantes do território.

## Página do Bairro

Deve permitir acessar, quando aplicável:

- lotes;
- residências;
- empresas;
- escolas;
- instituições;
- população de jogadores;
- estado territorial relevante.

A página não deve criar sistemas populacionais paralelos aos definidos nos documentos de design.

---

# 14. Política

A política possui páginas públicas e áreas de administração exclusivas de ocupantes de cargo.

```text
Política
├── Governo
│   ├── País
│   ├── Estado
│   └── Cidade
│
├── Eleições
│   ├── Próximas eleições
│   ├── Eleição em andamento
│   ├── Resultado
│   └── Histórico
│
├── Candidaturas
│   ├── Candidaturas disponíveis
│   └── Minha candidatura
│
├── Câmara
│   ├── Composição atual
│   ├── Deputados
│   └── Votações
│
├── Leis
│   ├── Ativas
│   ├── Propostas
│   ├── Em discussão
│   ├── Em votação
│   ├── Aguardando sanção/veto
│   └── Histórico
│
└── Administração do cargo
    ├── Orçamento
    ├── Projetos
    ├── Nomeações
    ├── Decisões administrativas
    └── Pendências
```

A interface de cada cargo deve mostrar somente as ações que aquele cargo pode realizar.

## Eleição

```text
Eleição
├── Cargo
├── Território
├── Calendário
├── Candidatos
├── Perfil dos candidatos
├── Votação
├── Resultado
└── Histórico
```

## Lei

```text
Lei / Proposta
├── Texto
├── Parâmetro X, quando aplicável
├── Limites permitidos
├── Efeitos conhecidos / estimados
├── Autor
├── Discussão
├── Votação da Câmara
├── Sanção / veto
├── Data prevista de entrada em vigor
├── Duração / expiração, quando aplicável
└── Histórico de versões e auditoria pública pertinente
```

---

# 15. Orçamento público

O orçamento precisa ser visível dentro das páginas dos respectivos governos.

```text
Orçamento
├── Federal
│   ├── Receita
│   ├── Caixa
│   ├── Gastos
│   ├── Compromissos
│   ├── Projetos
│   ├── Dívida
│   └── Histórico
│
├── Estadual
│   └── mesma estrutura
│
└── Municipal
    └── mesma estrutura
```

Governantes devem conseguir acessar a camada administrativa de seus respectivos níveis.

Outros jogadores devem conseguir consultar os dados que o sistema de transparência torna públicos.

---

# 16. Contratos

```text
Contratos
├── Meus contratos
├── Pendentes de aceite
├── Ativos
├── Inadimplentes
├── Encerrados
├── Criar contrato
└── Página do contrato
```

## Página do contrato

```text
Contrato
├── Partes
├── Tipo
├── Objeto
├── Quantidade
├── Valor
├── Frequência
├── Prazo
├── Condições
├── Multa
├── Status
├── Execuções
└── Histórico
```

A interface deve deixar claro quem possui cada obrigação e se ela foi cumprida.

---

# 17. Militar

```text
Militar
├── Visão geral
├── Exército
│   ├── Estrutura
│   ├── Minha posição
│   ├── Treinamento
│   ├── Prontidão
│   └── Mobilização
│
├── Milícias
│   ├── Explorar milícias
│   ├── Minha milícia
│   ├── Criar milícia
│   ├── Membros
│   ├── Banco
│   ├── Inventário
│   ├── Produção
│   ├── Melhorias
│   └── Ações
│
├── Conflitos
│   ├── Ativos
│   ├── Próximos
│   ├── Histórico
│   └── Página do conflito
│
└── Equipamentos
```

## Página do conflito

Deve permitir acompanhar, conforme a mecânica aplicável:

- território;
- participantes;
- estado da ação;
- pontuação/progresso;
- Supressão, quando aplicável;
- recursos mobilizados;
- prontidão relevante;
- resultado;
- consequências;
- histórico.

A página não deve expor informações militares privadas que um jogador comum não teria acesso.

---

# 18. Notícias / Histórico do Mundo

```text
Notícias
├── Mais recentes
├── Todas
├── Política
├── Economia
├── Conflito
├── Sociedade
├── Marco
└── Arquivo histórico
```

Cada notícia pode apontar para o objeto relacionado quando esse objeto possuir uma página pública.

A página é uma apresentação natural dos acontecimentos, conforme `12 — Histórico do Mundo`, e não um log técnico.

---

# 19. Rankings

```text
Rankings
├── Ao vivo
└── Históricos
```

Cada ranking deve mostrar a métrica que determina a posição.

Exemplos:

```text
Maior produção
→ últimos 14 dias

Maior contribuinte
→ últimos 30 dias

Conta mais antiga
→ tempo desde criação

Maior tempo ativo
→ maior sequência com intervalos inferiores a 72h
```

Rankings históricos devem indicar o recorde e os dados necessários para contextualizá-lo.

---

# 20. Busca global

A interface deve possuir uma busca global para encontrar objetos públicos relevantes.

Categorias esperadas:

```text
Busca
├── Jogadores
├── Empresas
├── Produtos
├── Escolas / Universidades
├── Imóveis
├── Milícias
├── Contratos públicos, quando aplicável
├── Leis
├── Cargos / governos
└── Notícias
```

A busca deve respeitar as permissões de acesso. Dados privados não devem aparecer apenas porque possuem um nome pesquisável.

---

# 21. Notificações

A interface deve possuir um mecanismo geral de notificações para acontecimentos que exigem atenção do jogador.

Exemplos:

- curso concluído;
- contrato aguardando aceite;
- obrigação de contrato vencida;
- eleição aberta;
- candidatura registrada;
- resultado eleitoral;
- mudança relevante em empresa;
- hospitalização / recuperação;
- convocação militar;
- ação política pendente;
- notícia relevante.

Notificações não substituem o Histórico do Mundo nem os históricos próprios de cada sistema.

---

# 22. Dev / Admin

As telas Dev/Admin são independentes da navegação normal do jogador.

```text
Dev / Admin
├── Dashboard geral
├── Jogadores
│   ├── Lista
│   ├── Busca
│   └── Perfil administrativo
│
├── Economia
│   ├── Dinheiro
│   ├── Fluxos
│   ├── Produtos
│   └── Indicadores
│
├── Empresas
├── Escolas / Universidades
├── Imóveis
├── Geografia
├── Política
├── Leis
├── Orçamento
├── Contratos
├── Militar
├── Notícias
├── Rankings
├── Fórmulas / Feedback
├── Jobs / Scheduler
├── Eventos futuros
├── Auditoria
├── Logs
├── Performance
└── Bot Test
```

---

# 23. Dev/Admin — Dashboard geral

A visão geral deve permitir verificar rapidamente a saúde do servidor.

```text
Dashboard Dev
├── Usuários
├── Empresas
├── Dinheiro em circulação
├── Produção
├── Consumo
├── Mercado
├── QoL média
├── Saúde média
├── Política
├── Militar
├── Jobs pendentes
├── Erros recentes
├── Tempo de tick
├── CPU
├── RAM
├── Banco de dados
└── Alertas
```

---

# 24. Dev/Admin — Auditoria

```text
Auditoria
├── Ações de jogador
├── Ações administrativas
├── Alterações de dados
├── Transações
├── Leis
├── Eleições
├── Contratos
├── Operações militares
└── Eventos do sistema
```

Toda ferramenta administrativa deve deixar claro quando uma alteração foi realizada por Dev/Admin e não pelo fluxo normal do jogo.

---

# 25. Dev/Admin — Fórmulas e Feedback

A ferramenta deve permitir consultar o detalhamento estruturado retornado pelas fórmulas.

```text
Fórmulas
├── Buscar indicador
├── Ver fórmula
├── Ver entradas
├── Ver resultado
├── Ver detalhamento
└── Ver origem dos dados
```

Esta área existe principalmente para validar a regra arquitetural de `20 — Filosofia de Feedback ao Jogador`.

---

# 26. Dev/Admin — Jobs e Scheduler

```text
Scheduler
├── Jobs pendentes
├── Jobs executando
├── Jobs concluídos
├── Jobs com erro
├── Próximas execuções
├── Tarefas recorrentes
└── Histórico
```

Deve ser possível identificar atrasos, falhas e filas acumuladas.

---

# 27. Bot Test

O Bot Test deve possuir uma área própria e completa.

```text
Bot Test
├── Overview
├── População
├── Arquétipos
├── Objetivos
├── Especializações
├── Bots
├── Decisões
├── Conhecimento
├── Memórias
├── Modelos RL
├── Treinamento
├── Anomalias
├── Cobertura de testes
├── Economia dos Bots
├── Performance
├── Replays
├── Logs
└── Exportação
```

---

# 28. Bot Test — Overview

```text
Bot Test Overview
├── Bots ativos
├── Meta populacional
├── Bots em ação
├── Bots aguardando
├── Bots sem ação
├── Hospitalizados
├── Em eleição
├── QoL média
├── Patrimônio médio
├── Produção
├── Taxa de falência
├── Anomalias
├── Cobertura de sistemas
└── Performance
```

---

# 29. Bot Test — Bots

```text
Bots
├── Lista geral
├── Filtros
│   ├── Personalidade
│   ├── Objetivo
│   ├── Especialização
│   ├── Estado
│   ├── Modelo
│   └── Conhecimento
└── Página individual
```

## Página individual

```text
Bot
├── Identidade técnica
│   ├── ID
│   ├── Arquétipo
│   ├── Personalidade
│   ├── Objetivo
│   ├── Especialização
│   ├── Modelo RL
│   └── Seed
│
├── Estado atual
├── Objetivo de vida
├── Objetivo de longo prazo
├── Objetivo atual
├── Subobjetivo
├── Próxima ação
├── Ações consideradas
├── Reward
├── Exploração
├── Memória
├── Conhecimento
├── Histórico de carreira
├── Histórico econômico
├── Histórico político
├── Histórico militar
├── Histórico de interações
├── Anomalias
├── Performance individual
└── Replay
```

---

# 30. Bot Test — Decisões

```text
Decisões
├── Últimas decisões
├── Filtros por Bot
├── Filtros por ação
├── Filtros por arquétipo
├── Resultados
└── Detalhe da decisão
```

O detalhe deve mostrar dados estruturados, não narrativa fictícia de pensamento.

```text
Estado observado
↓
Ações válidas
↓
Scores / preferências
↓
Exploração
↓
Ação escolhida
↓
Resultado
↓
Reward
```

---

# 31. Bot Test — Conhecimento

```text
Conhecimento
├── Visão geral
├── Por sistema
├── Por arquétipo
├── Por Bot
├── Descoberta
├── Compreensão
└── Domínio
```

Também deve permitir observar:

- primeiro contato com um sistema;
- primeira tentativa;
- primeiro uso correto;
- uso consistente;
- tempo até descoberta.

---

# 32. Bot Test — Modelos RL

```text
Modelos
├── Ativo
├── Experimentais
├── Histórico
├── Comparação
├── Checkpoints
└── Detalhe do modelo
```

## Detalhe do modelo

```text
Modelo
├── Versão
├── Data
├── Modelo pai
├── Bots utilizando
├── Experiências
├── Métricas de treinamento
├── Reward por arquétipo
├── Taxa de sucesso
├── Exploração
├── Anomalias associadas
└── Status
```

---

# 33. Bot Test — Anomalias e lacunas

```text
Anomalias
├── Recentes
├── Severidade
├── Econômicas
├── Políticas
├── Carreiras
├── Mercado
├── Progressão
├── Performance
└── Histórico
```

```text
Cobertura
├── Sistemas
├── Carreiras
├── Produtos
├── Empresas
├── Educação
├── Política
├── Militar
└── Interações
```

A ferramenta deve diferenciar:

- falta de oportunidade;
- falta de descoberta;
- falha de aprendizado;
- estratégia válida porém pouco utilizada.

---

# 34. Bot Test — Performance

```text
Performance
├── CPU
├── RAM
├── GPU
├── VRAM
├── Tick
├── Decisões por segundo
├── Scheduler
├── Banco de dados
├── Simulação
├── Treinamento
├── Filas
├── Erros
└── Timeouts
```

Deve existir histórico para observar degradação de desempenho ao longo da execução.

---

# 35. Bot Test — Replay

```text
Replay
├── Buscar por Bot
├── Buscar por evento
├── Buscar por anomalia
├── Linha do tempo
├── Estado
├── Decisão
├── Resultado
└── Contexto do modelo
```

O replay deve utilizar os dados de execução, versão do jogo, versão do modelo e seed/contexto necessários para reproduzir o comportamento quando tecnicamente possível.

---

# 36. Bot Test — Exportação

```text
Exportação
├── Execução atual
├── Intervalo de datas
├── Bot específico
├── Arquétipo
├── Anomalias
├── Performance
├── Treinamento
└── Relatório completo
```

O relatório deve permitir exportar dados estruturados para análise externa.

Formato conceitual:

```text
bot_test_YYYY-MM-DD.zip
├── run.json
├── bots.csv
├── bot_states.csv
├── actions.jsonl
├── decisions.jsonl
├── anomalies.csv
├── economy_daily.csv
├── population_daily.csv
├── system_performance.csv
├── training_metrics.csv
└── summary.json
```

A estrutura física dos arquivos pode mudar durante a implementação, desde que as informações permaneçam exportáveis.

---

# 37. Fluxos principais de navegação

## 37.1. Criar personagem e começar a jogar

```text
Cadastro
↓
Entrada
↓
Dashboard
↓
Perfil / Dia a dia
↓
Primeira ação
```

## 37.2. Conseguir emprego

```text
Dashboard
↓
Trabalho / Carreira
↓
Vagas
↓
Detalhe da vaga
↓
Candidatura
↓
Emprego
↓
Trabalho
```

## 37.3. Estudar

```text
Educação
↓
Escola / Universidade
↓
Curso
↓
Requisitos
↓
Matrícula
↓
Curso atual
↓
Conclusão / Diploma
```

## 37.4. Criar empresa

```text
Empresas
↓
Criar empresa
↓
Tipo
↓
Localização / lote
↓
Produto / produção
↓
Criação
↓
Gerenciamento
```

## 37.5. Comprar no mercado

```text
Mercado
↓
Produto
↓
Estatísticas
↓
Comprar
↓
Inventário
```

## 37.6. Comprar imóvel

```text
Imóveis
↓
Lotes / imóveis disponíveis
↓
Detalhe
↓
Compra
↓
Imóvel
↓
Residência / uso
```

## 37.7. Participar de eleição

```text
Política
↓
Eleições
↓
Eleição
↓
Candidatos
↓
Votação
↓
Resultado
```

## 37.8. Propor / acompanhar lei

```text
Política
↓
Leis
↓
Nova proposta / proposta existente
↓
Discussão
↓
Votação
↓
Sanção / veto
↓
Entrada em vigor
```

## 37.9. Contrato

```text
Contratos
↓
Criar / receber
↓
Revisar termos
↓
Aceitar
↓
Ativo
↓
Execuções
↓
Encerramento
```

## 37.10. Militar

```text
Militar
↓
Exército / Milícia
↓
Treinamento / organização
↓
Mobilização
↓
Conflito
↓
Resultado
```

---

# 38. Fluxos de descoberta

A UI deve possuir múltiplos caminhos para encontrar a mesma informação quando isso for natural.

Exemplo para um Produto:

```text
Mercado → Produto

ou

Inventário → Produto

ou

Empresa → Produção → Produto

ou

Notícia → Produto
```

Isso reduz a dependência de uma única árvore de menus.

---

# 39. Permissões de interface

As telas devem respeitar três conceitos principais:

```text
Público
→ qualquer jogador pode consultar

Privado
→ somente o proprietário / participante pode consultar

Administrativo
→ somente Dev/Admin autorizado
```

Uma mesma entidade pode possuir partes públicas e privadas.

Exemplo:

```text
Empresa pública
├── nome / tipo / estrelas / localização → público
├── funcionários → conforme regra pública
└── dados financeiros privados → proprietário / acesso autorizado
```

A UI nunca deve funcionar como mecanismo de autorização. As permissões devem ser verificadas pelo backend.

---

# 40. Responsividade e reutilização de componentes

O design visual não precisa ser finalizado no Sitemap.

Entretanto, a implementação deve favorecer componentes reutilizáveis para:

- cards de entidade;
- tabelas;
- gráficos;
- indicadores;
- detalhamento de fórmulas;
- histórico;
- alertas;
- modais de confirmação;
- filtros;
- paginação;
- navegação contextual.

Isso permite corrigir a UX depois sem redesenhar cada página individualmente.

---

# 41. Matriz de cobertura por documento

| Documento | Principais telas / áreas |
|---|---|
| `01 — Skills` | Perfil, Skills, trabalho, carreira, educação |
| `02 — Empresas` | Empresas, página da empresa, produção, contratação, custos |
| `03 — Escolas` | Educação, escola, universidade, cursos |
| `04 — Dia a Dia` | Dashboard, energia, trabalho, estudo, saúde, transporte |
| `05 — Inventário` | Inventário, produto, uso, transferência |
| `06 — Política` | Governo, eleições, candidaturas, Câmara, administração |
| `07 — Leis` | Leis, propostas, discussão, votação, sanção/veto, histórico |
| `08 — Geografia` | País, Estado, cidade, bairro, lote, mapa |
| `09 — Orçamento Público` | Orçamento federal/estadual/municipal, projetos, dívida, histórico |
| `10 — Imóveis e Zonas` | Imóveis, lotes, residência, aluguel, uso |
| `11 — Leis Paramétricas` | Parâmetros, pré-visualização de efeitos, leis correspondentes |
| `12 — Histórico do Mundo` | Notícias e arquivo histórico |
| `13 — Eventos` | Não faz parte do primeiro Bot Test; apenas espaço reservado |
| `14 — Rankings` | Rankings ao vivo e históricos |
| `15 — Jornalismo` | Futuro; espaço reservado |
| `16 — Sociedades e Ações` | Futuro; espaço reservado |
| `17 — Transparência de Mercado` | Mercado, produto, gráficos, custos |
| `18 — Contratos` | Contratos e execução |
| `19 — Militar` | Exército, milícia, treinamento, conflito |
| `20 — Feedback` | Camada transversal em indicadores e detalhamentos |
| `21 — Bots` | Dashboards e ferramentas Dev/Admin |
| `22 — Receitas-Produção` | Produto, receitas, produção e navegação relacionada |

---

# 42. Cobertura e lacunas de UI

A implementação deve acompanhar o estado de cada tela.

Conceitualmente:

```text
Planejada
↓
Implementada
↓
Acessível pela navegação
↓
Testada
↓
Revisada
```

O sistema Dev/Admin deve poder identificar, durante o desenvolvimento, telas ou fluxos que:

- existem no backend mas não possuem interface;
- possuem interface mas não possuem caminho de navegação;
- possuem caminho de navegação mas não possuem ação funcional;
- possuem ação funcional mas não possuem feedback suficiente;
- possuem informações importantes sem detalhamento adequado.

---

# 43. Relação com o Feedback (`20`)

O Sitemap não deve duplicar as regras de explicação de cada fórmula.

Em vez disso, os componentes de interface devem consumir o detalhamento estruturado definido em `20`.

Assim, uma mesma estrutura de detalhamento pode aparecer em:

- Perfil;
- Empresa;
- Mercado;
- Política;
- Militar;
- Orçamento;
- Rankings;
- Dashboard de Bots;
- ferramentas Dev/Admin.

---

# 44. Fora do escopo

O Sitemap não define:

- identidade visual final;
- paleta de cores;
- tipografia;
- layout em pixels;
- framework frontend específico;
- HTML final;
- design system completo;
- responsividade detalhada por dispositivo;
- implementação de API;
- estrutura interna dos modelos Django.

Esses assuntos podem ser definidos durante a implementação.

---

# 45. Critério de conclusão

O Sitemap poderá passar para `FINAL — BOT TEST` quando:

1. todos os sistemas do Bot Test possuírem cobertura de interface;
2. todos os fluxos principais possuírem caminhos de navegação;
3. as permissões público/privado/administrativo estiverem claras;
4. as páginas Dev/Admin necessárias estiverem previstas;
5. o Bot Test possuir observabilidade suficiente para inspeção individual e agregada;
6. não existirem mecânicas relevantes sem local definido na interface;
7. a estrutura puder ser entregue ao Dev sem exigir que ele invente páginas essenciais para completar os sistemas.

---

# 46. Princípio final

O Sitemap existe para garantir que o Polis não seja apenas um conjunto de sistemas funcionando no backend.

Cada mecânica importante deve possuir um caminho compreensível para o jogador descobrir, utilizar e entender o sistema.

A interface pode mudar durante o desenvolvimento.

A prioridade é preservar a **coerência de navegação, descobribilidade, feedback e cobertura**.
