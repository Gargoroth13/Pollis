# 21 — Bots para Testes de Beta

**Status: FINAL — BOT TEST**

## 21.0. Objetivo

O sistema de Bots existe exclusivamente como **ferramenta de validação do Polis antes e durante o Beta**. Bots não são conteúdo do jogo final e não representam NPCs econômicos.

Cada Bot é tratado como um jogador artificial sujeito às mesmas regras, limites, custos, informações e consequências que um jogador humano.

O objetivo é permitir que o servidor seja executado por longos períodos com uma população artificial capaz de:

- exercitar os sistemas do jogo;
- descobrir estratégias emergentes;
- revelar gargalos e desequilíbrios;
- encontrar combinações de sistemas que não foram previstas;
- descobrir exploits e estados inválidos;
- identificar sistemas pouco utilizados ou difíceis de descobrir;
- testar eleições, governos, empresas, mercado, educação, militar e demais sistemas em conjunto;
- fornecer dados reproduzíveis para análise posterior;
- permitir inspeção detalhada do comportamento de cada agente.

O Bot deve **jogar o jogo**, não executar scripts de teste artificiais que ignorem as regras normais.

---

# 21.1. Princípio fundamental

O Bot deve possuir as mesmas possibilidades fundamentais de um jogador real.

Ele não recebe:

- Energia infinita;
- dinheiro criado artificialmente;
- acesso a inventário privado de outros jogadores;
- resultados futuros do mercado;
- informações administrativas que não estejam disponíveis ao jogador;
- execução de ações impossíveis;
- bypass de cooldowns, requisitos ou limites;
- acesso direto a modelos internos do jogo durante a tomada de decisão.

A única diferença fundamental é que o agente é controlado por um sistema automatizado de decisão e aprendizado.

Ferramentas internas de Dev/Admin podem observar os Bots e registrar informações adicionais, mas essas informações **não podem ser fornecidas ao Bot como conhecimento de jogo**, salvo quando o mesmo dado seria visível a um jogador.

---

# 21.2. População dos Bots

A população-alvo inicial do Bot Test é de aproximadamente **1.000 Bots ativos**.

## Criação inicial

A taxa padrão de criação será:

> **1 novo Bot por minuto**, até atingir a população-alvo.

1.000 Bots são aproximadamente 16 horas e 40 minutos de criação contínua nessa taxa.

A taxa de criação deve ser configurável para experimentos e testes específicos.

## Population Controller

A população não deve ser tratada como uma distribuição fixa criada uma única vez.

Um controlador de população deve acompanhar quais sistemas, objetivos, carreiras e comportamentos estão sendo efetivamente testados e identificar lacunas de cobertura.

Exemplo:

```text
População: 1.000 / 1.000

Mineração             182
Indústria              41   <-- cobertura baixa
Medicina                7   <-- cobertura muito baixa
Direito                93
Política                 4   <-- cobertura muito baixa
```

O sistema pode então aumentar a criação de perfis que cobrem essas lacunas.

A meta não é manter necessariamente uma proporção fixa entre arquétipos, mas manter uma população que maximize a cobertura útil do teste.

---

# 21.3. Ambiente de execução

O Bot Test utiliza um **único ambiente contínuo**.

O objetivo é ligar o servidor e deixá-lo funcionar por dias, acumulando histórico real da simulação.

Não existe, no primeiro Bot Test, separação obrigatória entre “modo Beta” e “modo Simulation”.

## Velocidade do mundo

A velocidade de teste padrão é:

> **1 dia do jogo = 10 minutos reais.**

Todos os sistemas devem avançar juntos nessa mesma escala temporal.

Isso inclui, conforme aplicável:

- Energia;
- salários;
- produção;
- consumo;
- contratos;
- eleições;
- leis;
- hospitais;
- economia;
- orçamentos;
- eventos;
- demais ciclos temporais do jogo.

A aceleração não deve criar regras especiais para Bots.

Ela apenas altera a relação entre tempo real e tempo do mundo no ambiente de testes.

---

# 21.4. Scheduler individual

Cada Bot possui seu próprio agendamento de decisão.

Bots não devem acordar simultaneamente em grandes blocos artificiais.

Conceitualmente:

```text
Bot precisa de avaliação
        ↓
Scheduler agenda Bot
        ↓
Bot observa estado
        ↓
Bot avalia ações
        ↓
Bot escolhe ação
        ↓
Ação é executada pelo sistema normal
        ↓
Bot define próxima avaliação
```

O intervalo entre avaliações é variável.

O Bot pode ser acordado por:

- chegada do próximo momento planejado;
- conclusão de uma ação relevante;
- mudança relevante em sua situação;
- disponibilidade de uma oportunidade relevante;
- início de eleição ou janela política importante;
- mudança de emprego, empresa ou contrato;
- outra condição que justifique nova avaliação.

O scheduler não deve permitir que um Bot obtenha ações extras além das permitidas pelas mecânicas normais.

---

# 21.5. Arquitetura de comportamento

O sistema deve separar três dimensões principais:

```text
PERSONALIDADE
        +
OBJETIVO
        +
ESPECIALIZAÇÃO
```

Isso evita criar dezenas de Bots completamente diferentes no código.

## Personalidade

Define **como o Bot toma decisões**.

Exemplos:

- Casual;
- Otimizador;
- Conservador;
- Explorador;
- Caótico;
- Social;
- Adversarial.

## Objetivo

Define **o que o Bot pretende alcançar**.

Exemplos:

- Riqueza;
- Presidência;
- Empresas;
- Carreira;
- Militar;
- Educação;
- Imóveis;
- Organizações/interação social.

## Especialização

Define **em qual caminho o Bot concentra seu desenvolvimento**.

Exemplos:

- Mineração;
- Extrativismo;
- Agropecuária;
- Indústria;
- Varejo;
- Construção;
- Medicina;
- Direito;
- outras carreiras existentes no jogo.

Personalidade, objetivo e especialização podem ser combinados livremente.

Exemplo:

```text
Personalidade: Otimizador
Objetivo: Presidência
Especialização: Direito
```

---

# 21.6. Arquétipos iniciais

Os primeiros Bots podem ser criados a partir de 10 arquétipos-base.

Esses arquétipos são combinações iniciais e não devem limitar a arquitetura futura.

| Arquétipo | Personalidade | Objetivo | Característica principal |
|---|---|---|---|
| Casual | Casual | Riqueza | Joga de maneira razoável sem otimização extrema |
| Magnata | Otimizador | Riqueza | Maximiza eficiência e patrimônio |
| Conservador | Conservador | Riqueza | Prioriza segurança e estabilidade |
| Explorador | Explorador | Descoberta | Procura sistemas, atividades e oportunidades |
| Caótico | Caótico | Riqueza | Muda de estratégia e aceita alta variância |
| Empreendedor | Otimizador | Empresas | Prioriza abertura, crescimento e gestão empresarial |
| Político | Otimizador | Presidência | Prioriza progressão e sucesso eleitoral |
| Especialista | Conservador | Carreira | Busca alto domínio em uma carreira específica |
| Social | Social | Organizações | Valoriza relações, contratos e participação coletiva |
| Adversarial | Adversarial | Riqueza | Procura limites, combinações extremas e exploits |

Esses arquétipos não representam “classes” permanentes.

Um Bot pode possuir uma combinação que não exista nessa tabela, desde que os componentes individuais existam.

---

# 21.7. Casual

O Casual representa um jogador razoavelmente funcional que não tenta calcular perfeitamente cada decisão.

Ele deve:

- trabalhar quando precisa de dinheiro;
- estudar quando percebe necessidade de desenvolvimento;
- comprar bens necessários;
- buscar empregos adequados;
- abrir empresa quando parecer viável;
- reagir a acontecimentos importantes.

Ele não deve buscar sistematicamente a estratégia economicamente ótima.

### Tendências

```text
Progresso geral:       alto
QoL:                   alto
Patrimônio:            médio
Exploração:            média
Risco:                 baixo/médio
```

### Exploração

Média.

### Aprendizado

Médio.

---

# 21.8. Otimizador

O Otimizador procura maximizar o resultado associado ao seu objetivo.

Ele deve comparar alternativas disponíveis e preferir decisões com maior retorno esperado, inclusive quando isso exige planejamento de médio ou longo prazo.

Exemplo:

```text
Trabalhar       0,72
Estudar         0,91
Comprar imóvel  0,31
Abrir empresa   0,18
```

A rede pode decidir estudar porque avalia que o benefício futuro supera o ganho imediato do trabalho.

### Tendências

```text
Patrimônio:             muito alto
Renda:                  muito alta
Eficiência:             muito alta
Progresso do objetivo:  alto
Exploração:             baixa/média
```

### Exploração

Baixa a média.

### Aprendizado

Alto.

---

# 21.9. Conservador

O Conservador procura crescimento com baixo risco.

Deve evitar, quando possível:

- endividamento elevado;
- estratégias com alta variância;
- empresas frágeis;
- decisões com possibilidade significativa de perda;
- mudanças frequentes de carreira.

### Tendências

```text
Estabilidade:           muito alta
Sobrevivência:           muito alta
Patrimônio:              alto
QoL:                     alta
Risco:                   fortemente negativo
Dívida:                  fortemente negativa
```

### Exploração

Baixa.

### Aprendizado

Médio, com retenção alta.

---

# 21.10. Explorador

O Explorador existe para descobrir o conteúdo do jogo de maneira ampla.

Ele deve experimentar:

- diferentes empregos;
- escolas e cursos;
- empresas;
- mercado;
- imóveis;
- contratos;
- política;
- organizações;
- sistemas militares, quando elegível.

Seu principal valor para o Bot Test é revelar sistemas que são pouco descobertos por agentes focados em eficiência.

### Tendências

```text
Descoberta:              muito alta
Diversidade de ações:    muito alta
Experiência de sistemas: alta
Progresso geral:         médio
Patrimônio:              médio
```

### Exploração

Muito alta.

### Aprendizado

Alto.

---

# 21.11. Caótico

O Caótico não deve ser simplesmente um Bot aleatório.

Ele possui objetivos reais, mas apresenta grande variabilidade na escolha das estratégias.

Pode abandonar uma estratégia eficiente e experimentar outra.

### Tendências

```text
Experiência:             alta
Novidade:                alta
Mudança de estratégia:   alta
Patrimônio:              médio
Estabilidade:            baixa
```

### Exploração

Muito alta.

### Aprendizado

Alto, com retenção menor que a de perfis conservadores.

---

# 21.12. Empreendedor

Prioriza construção e crescimento de empresas.

Uma trajetória possível é:

```text
trabalhar
→ acumular capital
→ desenvolver competências
→ abrir empresa
→ contratar
→ aumentar estrelas
→ crescer produção
→ expandir operações
```

### Tendências

```text
Crescimento empresarial: muito alto
Estrelas:               muito alto
Funcionários:           alto
Produção:               alto
Patrimônio:             alto
```

### Exploração

Média.

### Aprendizado

Alto.

---

# 21.13. Político

Prioriza progressão e sucesso dentro do sistema político.

Pode sacrificar resultados econômicos imediatos para atingir requisitos ou melhorar suas chances políticas.

Exemplo:

```text
melhorar Carisma
→ obter diploma necessário
→ atingir requisito de candidatura
→ disputar cargo menor
→ cumprir experiência política
→ disputar cargo superior
```

### Tendências

```text
Progresso político:     muito alto
Elegibilidade:          muito alta
Resultado eleitoral:    muito alto
Carisma:                alto
Patrimônio:             médio
```

### Exploração

Média.

### Aprendizado

Alto.

---

# 21.14. Especialista

Concentra seu desenvolvimento em uma carreira específica.

Exemplos:

- Especialista em Mineração;
- Especialista em Medicina;
- Especialista em Direito;
- Especialista em Construção;
- Especialista em Indústria.

O Bot deve preferir decisões que aprofundem sua especialização, desde que compatíveis com suas necessidades e regras do jogo.

### Tendências

```text
Skill da carreira:       muito alta
Especialização:           muito alta
Performance profissional: muito alta
Mudança de carreira:      baixa
Renda:                    alta
```

### Exploração

Baixa.

### Aprendizado

Muito alto dentro do domínio escolhido.

---

# 21.15. Social

O Social testa a capacidade do jogo de gerar interação real entre jogadores.

Pode priorizar:

- contratar outros jogadores;
- negociar;
- criar ou cumprir contratos;
- participar de organizações;
- entrar em milícias;
- participar de oportunidades políticas;
- realizar transações com outros Bots.

Não precisa maximizar a eficiência econômica em todas as decisões.

### Tendências

```text
Interações:              muito altas
Contratos:               altas
Organizações:            altas
Relações:                altas
Patrimônio:              médio
```

### Exploração

Alta.

### Aprendizado

Médio/alto.

---

# 21.16. Adversarial

O Adversarial é um agente especializado em encontrar limites do sistema.

Ele deve tentar descobrir estratégias válidas, porém extremas, que possam revelar:

- exploits econômicos;
- loops de recursos;
- problemas de transição de estados;
- combinações inesperadas de sistemas;
- formas de contornar custos sem violar formalmente uma regra;
- estados impossíveis ou inconsistentes;
- oportunidades de arbitragem exageradas;
- regras conflitantes.

Ele não recebe permissões especiais e não pode trapacear.

### Tendências

```text
Descoberta de comportamento extremo: muito alta
Descoberta de anomalias:             muito alta
Exploração:                           muito alta
Eficiência:                           alta
```

### Exploração

Extremamente alta.

### Aprendizado

Muito alto.

---

# 21.17. Informação disponível ao Bot

O Bot deve conhecer somente aquilo que um jogador conseguiria conhecer pela interface normal do jogo.

## Informação pública

Pode incluir, conforme os sistemas disponibilizem ao jogador:

- preços públicos;
- médias de preço;
- estoque público;
- empresas visíveis;
- vagas e salários visíveis;
- leis;
- eleições;
- candidatos;
- notícias;
- informações de mercado;
- informações públicas de instituições;
- outras informações publicadas pelo jogo.

## Informação própria

Pode conhecer integralmente seu próprio estado, incluindo:

- dinheiro;
- Energia;
- Saúde;
- QoL;
- skills;
- especializações;
- inventário;
- propriedades;
- empresas próprias;
- contratos próprios;
- candidaturas próprias;
- histórico pessoal de ações;
- demais dados que um jogador normalmente possui sobre si mesmo.

## Informação proibida

O Bot não pode receber:

- objetivos secretos de outros Bots;
- score interno de outros Bots;
- dinheiro ou inventário privado de outros jogadores;
- próximas ações de outros agentes;
- estado futuro do mundo;
- resultado futuro de mercados;
- informações internas de Admin/Dev;
- variáveis usadas exclusivamente pelo sistema de teste;
- reward futuro calculado pelo servidor antes da ação.

---

# 21.18. Aprendizado por Reinforcement Learning

O Bot Test utilizará como abordagem principal **Reinforcement Learning híbrido com regras de validação do jogo**.

A intenção é que os Bots aprendam estratégias por experiência, sem precisar receber um roteiro manual completo.

O sistema não utilizará LLM como mecanismo de decisão no primeiro Bot Test.

---

# 21.19. Arquitetura híbrida de RL

O fluxo conceitual é:

```text
Estado real do jogo
        ↓
Observação disponível ao Bot
        ↓
Action Registry
        ↓
Filtro / Action Masking
        ↓
Modelo RL
        ↓
Preferência pelas ações possíveis
        ↓
Personalidade + Objetivo + Especialização
        ↓
Ação escolhida
        ↓
Sistema normal do jogo
        ↓
Resultado
        ↓
Reward
        ↓
Experiência de aprendizado
```

As regras do jogo continuam sendo a autoridade.

O RL decide **qual ação tentar**, não altera as regras ou os resultados fundamentais do sistema.

---

# 21.20. Action Registry

O Bot não deve possuir um conjunto de ações independente do jogador.

As ações disponíveis devem ser registradas em uma estrutura compartilhada com o sistema normal do jogo.

Conceitualmente:

```text
Action Registry

- ID
- nome
- categoria
- requisitos
- custo
- cooldown
- alvo permitido
- efeitos
- visibilidade
```

O jogador utiliza essas ações através da UI.

O Bot utiliza as mesmas ações através do mecanismo de decisão automatizada.

Isso evita divergência entre “o que o jogador pode fazer” e “o que o Bot pode fazer”.

---

# 21.21. Action Masking

Nem toda ação do jogo está disponível em qualquer estado.

O sistema deve informar ao modelo quais ações estão legalmente disponíveis.

Exemplo:

```text
Trabalhar         1
Estudar           1
Comprar           1
Abrir empresa     0
Votar             0
```

A rede não pode escolher uma ação marcada como indisponível.

O Action Masking não remove regras do jogo; apenas evita que o modelo desperdice aprendizado tentando executar estados impossíveis.

---

# 21.22. Reward

Cada tipo de Bot deve utilizar uma composição de recompensas diferente.

O reward deve representar dois aspectos:

### Reward objetivo

Mede o progresso em direção ao objetivo do Bot.

### Reward comportamental

Representa a forma como a personalidade prefere atingir esse objetivo.

Conceitualmente:

```text
Reward total =
    progresso do objetivo × peso
  + progresso econômico × peso
  + QoL × peso
  + progresso de carreira × peso
  + descoberta × peso
  + estabilidade × peso
  + outros fatores × peso
```

Os pesos são configuráveis por personalidade e objetivo.

Não deve existir necessariamente um único reward universal para todos os Bots.

---

# 21.23. Reward por personalidade

O reward deve produzir diferenças comportamentais reais.

## Otimizador

Prioriza:

- retorno econômico;
- eficiência;
- progresso de objetivo;
- resultado futuro;
- utilização eficiente de recursos.

Penaliza principalmente desperdício e decisões claramente dominadas.

## Conservador

Prioriza:

- estabilidade;
- sobrevivência;
- patrimônio;
- QoL;
- previsibilidade.

Penaliza fortemente risco excessivo e endividamento.

## Explorador

Prioriza:

- descoberta;
- diversidade de experiências;
- utilização de sistemas novos;
- aprendizagem de novas mecânicas.

## Caótico

Prioriza:

- novidade;
- mudança de estratégia;
- experimentação;
- variabilidade.

Pode manter um reward objetivo de riqueza ou outro objetivo, mas sua estrutura comportamental incentiva maior variabilidade.

## Social

Prioriza:

- interação;
- contratos;
- organizações;
- relações e oportunidades derivadas de outros jogadores.

## Adversarial

Prioriza:

- descobrir estratégias extremas;
- encontrar comportamentos anômalos;
- explorar limites de sistemas dentro das regras;
- testar situações pouco exploradas.

---

# 21.24. Reward por objetivo

A personalidade define como o Bot prefere agir. O objetivo define **o que representa sucesso**.

Exemplos:

### Riqueza

Pode valorizar:

- patrimônio líquido;
- renda;
- crescimento de patrimônio;
- retorno sobre recursos.

### Presidência

Pode valorizar:

- elegibilidade;
- progresso de carreira política;
- sucesso eleitoral;
- requisitos de cargos superiores;
- desenvolvimento de atributos relevantes.

### Empresas

Pode valorizar:

- fundação de empresas;
- estrelas;
- empregados;
- produção;
- crescimento empresarial.

### Carreira

Pode valorizar:

- skill relevante;
- especialização;
- qualidade profissional;
- renda da carreira;
- progressão para cargos superiores.

### Militar

Pode valorizar:

- progressão militar;
- experiência;
- especialização militar;
- prontidão;
- participação em operações.

### Educação

Pode valorizar:

- skill;
- qualidade do ensino utilizado;
- cursos;
- diplomas;
- progressão acadêmica.

### Imóveis

Pode valorizar:

- quantidade de propriedades;
- qualidade;
- patrimônio imobiliário;
- renda de aluguel quando aplicável.

---

# 21.25. Exploração

O comportamento exploratório deve variar por arquétipo.

A exploração representa a disposição do Bot de testar ações ou estratégias cuja expectativa atual seja inferior à melhor alternativa conhecida.

Distribuição conceitual:

```text
Conservador    baixa
Otimizador     baixa/média
Casual         média
Social         média/alta
Explorador     alta
Caótico        muito alta
Adversarial    extremamente alta
```

Exploração não deve significar escolher aleatoriamente qualquer ação.

Ela deve representar experimentação dentro do conjunto de ações possíveis.

---

# 21.26. Aprendizado individual

O aprendizado deve ocorrer em dois níveis:

### Modelo compartilhado

Aprende padrões gerais sobre como o ambiente de Polis funciona.

### Estado individual

Cada Bot mantém sua própria memória, experiência e preferências aprendidas.

Conceitualmente:

```text
                 Modelo RL compartilhado
                         │
        ┌────────────────┼────────────────┐
        ↓                ↓                ↓
      Bot 1            Bot 2            Bot 3
        │                │                │
     memória          memória          memória
     experiência      experiência      experiência
     objetivo         objetivo         objetivo
     personalidade    personalidade    personalidade
```

Isso permite que 1.000 Bots usem o mesmo modelo-base sem se tornarem cópias exatas.

---

# 21.27. Plasticidade e retenção individual

Cada Bot pode possuir parâmetros individuais para representar diferenças de aprendizado.

Exemplos conceituais:

- plasticidade;
- retenção;
- persistência de estratégia;
- tendência de exploração;
- velocidade de adaptação.

### Conservador

Plasticidade menor, retenção alta.

### Explorador

Plasticidade alta, retenção média.

### Otimizador

Plasticidade alta, retenção alta.

### Caótico

Plasticidade alta, retenção relativamente baixa.

Esses parâmetros devem influenciar a adaptação do agente sem criar uma rede neural independente por Bot.

---

# 21.28. Memória individual

O Bot pode registrar fatos e experiências próprios, por exemplo:

```text
Comprei Aço a R$ 42.
Vendi a R$ 60.
A operação foi positiva.
```

ou:

```text
A empresa que abri ficou deficitária.
```

ou:

```text
Estudar determinado curso melhorou significativamente minha capacidade de atingir meu objetivo.
```

A memória individual deve ser compacta e orientada a decisões futuras.

Não é necessário armazenar uma cópia completa de todos os dados do mundo dentro do Bot.

---

# 21.29. Aprendizado ao longo da população

Experiências geradas pelos Bots podem ser acumuladas e utilizadas para novos ciclos de treinamento do modelo compartilhado.

Conceitualmente:

```text
Bots jogam
    ↓
Experiências acumuladas
    ↓
Treinamento RL
    ↓
Novo checkpoint
    ↓
Novo modelo disponível
    ↓
Bots continuam jogando
```

O modelo deve poder evoluir conforme aumenta a experiência coletada.

---

# 21.30. Modelos compartilhados e checkpoints

Cada versão do modelo deve possuir um identificador único.

Exemplo:

```text
NN-001
NN-002
NN-003
NN-004
```

Modelos anteriores não devem ser sobrescritos.

Cada decisão importante deve registrar qual versão do modelo foi utilizada.

Isso permite comparar comportamento entre versões e retornar a uma versão anterior em caso de regressão.

---

# 21.31. Treinamento em lotes

O modelo não precisa ser treinado após cada ação individual.

Experiências podem ser agrupadas em batches e processadas periodicamente.

Exemplo conceitual:

```text
100.000 experiências
        ↓
Treinamento
        ↓
Novo checkpoint
```

Os números reais de batch e frequência de treinamento são parâmetros técnicos e devem ser calibrados com os testes de performance e qualidade do agente.

---

# 21.32. Avaliação de novos modelos

Um novo modelo não deve substituir automaticamente o modelo ativo sem avaliação.

A avaliação deve comparar métricas por arquétipo e por sistema.

Exemplo:

```text
NN-005

Riqueza              +8%
Política            +12%
Descoberta           +5%
Falências            +24%   ← atenção
Ações inválidas       0%
QoL média             -2%
```

Não existe necessariamente um único modelo “melhor” para todos os comportamentos.

O sistema deve detectar melhorias e regressões separadamente.

---

# 21.33. Promoção de modelo

Modelos podem possuir estados como:

```text
Experimental
      ↓
Avaliado
      ↓
Aprovado
      ↓
Ativo
```

A decisão de promoção deve utilizar métricas objetivas e permitir rollback.

Modelos antigos devem permanecer disponíveis para reprodução de comportamentos e comparação.

---

# 21.34. Conhecimento do Bot

O sistema deve manter uma métrica operacional de quanto cada Bot demonstra conhecer sobre os sistemas do jogo.

Não é necessário tentar medir “conhecimento interno” da rede neural diretamente.

A métrica deve ser baseada em comportamento observável.

---

# 21.35. Níveis de conhecimento

Uma habilidade ou sistema pode ser classificado conceitualmente em:

### Descoberto

O Bot já teve contato ou experimentou a mecânica.

### Compreendido

O Bot demonstra reconhecer situações em que a mecânica é útil.

### Dominado

O Bot consegue utilizar a mecânica de maneira consistente e adequada em múltiplos estados.

Esses estados não precisam representar notas escolares; são categorias operacionais para o Dashboard e para testes.

---

# 21.36. Conhecimento por sistema

O Dashboard pode exibir uma matriz como:

```text
Economia        84%
Empresas        71%
Mercado         92%
Educação        44%
Política        17%
Militar          0%
Contratos       35%
Imóveis         61%
```

Os valores são baseados em desempenho em cenários e experiências relevantes, não em uma variável arbitrária definida apenas para preencher a tela.

---

# 21.37. Testes de competência

Para medir conhecimento, o sistema pode apresentar ao Bot estados comuns do jogo e avaliar sua escolha sem revelar o resultado esperado.

Exemplo:

```text
Estado:
Dinheiro = R$ 20.000
Energia = 80%
Skill X = 50
...

Ações disponíveis:
A
B
C
D
```

O sistema calcula as consequências possíveis internamente para fins de avaliação, mas o Bot recebe apenas a informação que um jogador teria.

A competência pode ser estimada verificando se o Bot toma decisões consistentes e favoráveis para seu objetivo.

---

# 21.38. Tempo de descoberta

Além do conhecimento, o sistema deve registrar quanto tempo um Bot leva para descobrir determinada mecânica.

Exemplo:

```text
Mecânica: Contratos

Primeiro contato:      Dia 17
Primeiro uso:          Dia 19
Primeiro uso adequado: Dia 24
Uso consistente:       Dia 38
```

Isso ajuda a distinguir falta de conhecimento de baixa descoberta de conteúdo.

---

# 21.39. Sistema de identificação de lacunas

O Bot Test deve detectar automaticamente áreas pouco cobertas pelos agentes.

Podem ser lacunas de:

- carreira;
- sistema;
- mecânica;
- objetivo;
- empresa;
- produto;
- política;
- região;
- interação;
- estágio de progressão.

Exemplo:

```text
LACUNA DE COBERTURA

Medicina

1.000 Bots ativos
4% tiveram experiência
0 chegaram ao nível avançado
```

Outro exemplo:

```text
LACUNA DE CONHECIMENTO

Contratos

312 Bots tiveram contato
84 tentaram utilizar
17 utilizaram corretamente
Tempo médio até descoberta: 96 dias
```

O sistema deve distinguir:

> poucos Bots tentaram

de:

> muitos tentaram e não aprenderam.

---

# 21.40. Cobertura de teste

O sistema deve acompanhar pelo menos:

- quantidade de Bots por arquétipo;
- quantidade por objetivo;
- quantidade por especialização;
- quantidade por carreira;
- quantidade que experimentou cada sistema;
- quantidade que atingiu cada estágio relevante;
- quantidade que participou de cada tipo de interação;
- quantidade que chegou a cargos políticos;
- quantidade que criou empresas;
- quantidade que chegou a empresas de alta estrela;
- quantidade que utilizou contratos;
- quantidade que participou de sistemas militares;
- demais métricas importantes conforme os sistemas forem implementados.

---

# 21.41. Interação entre Bots

Bots devem interagir normalmente entre si.

Um Bot pode, conforme as regras normais do jogo:

- empregar outro Bot;
- trabalhar para outro Bot;
- comprar de outro Bot;
- vender para outro Bot;
- negociar contratos;
- alugar ou alugar para outro jogador, quando aplicável;
- votar;
- candidatar-se;
- participar de organizações;
- entrar em milícias;
- participar de conflitos;
- interagir com empresas pertencentes a outros Bots.

Isso é essencial para testar sistemas emergentes.

Bots não devem receber prioridade especial em mercados ou sistemas sociais.

---

# 21.42. Relação entre jogadores humanos e Bots

Bots e jogadores humanos devem coexistir no mesmo ambiente de teste sempre que o cenário permitir.

Um jogador não deve conseguir identificar mecanicamente que determinado agente é Bot por informações que o jogo normalmente não exibiria.

O sistema administrativo/Dev, entretanto, deve sempre conseguir identificar a origem do agente para fins de teste.

---

# 21.43. Dashboard geral

O sistema deve possuir um Dashboard de Bot Test completo.

A visão geral deve apresentar, no mínimo:

```text
BOTS

Ativos:                  1.000
Executando ações:           83
Aguardando:                714
Hospitalizados:             21
Sem ação possível:          12
Em eleições:                34

QoL média:                 0,71
Patrimônio médio:       R$ 82k
Produção diária:        124.000
```

Também deve apresentar:

- distribuição por arquétipo;
- distribuição por objetivo;
- distribuição por especialização;
- cobertura de sistemas;
- cobertura de carreiras;
- anomalias recentes;
- falências;
- concentração econômica;
- participação política;
- utilização de produtos;
- saúde da simulação;
- performance do servidor.

---

# 21.44. Dashboard de arquétipos

Deve permitir analisar o comportamento agregado de cada perfil.

Exemplo:

```text
Otimizadores: 231

Patrimônio médio
QoL média
Taxa de abertura de empresas
Taxa de falência
Tempo médio até primeira empresa
Carreira predominante
Ações predominantes
Exploração média
Reward médio
```

Isso permite comparar perfis sem precisar abrir cada Bot individualmente.

---

# 21.45. Dashboard individual do Bot

Cada Bot deve possuir uma página própria de inspeção.

A página deve mostrar, no mínimo:

```text
BOT #1842

Personalidade: Otimizador
Objetivo: Presidência
Especialização: Direito
Modelo: NN-034
Experiência: 38.412 decisões

Dinheiro: R$ 18.420
Energia: 63%
QoL: 0,81
Inteligência: 142
Carisma: 97

Objetivo atual:
Tornar-se Governador

Subobjetivo:
Aumentar Carisma

Próxima ação:
Estudar Direito

Próxima avaliação:
17 minutos
```

A página deve também apresentar:

- plano atual;
- progresso do objetivo;
- histórico de carreira;
- empresas;
- propriedades;
- contratos;
- eleições;
- interações;
- conhecimento por sistema;
- memória relevante;
- reward acumulado;
- exploração;
- histórico de ações;
- anomalias associadas ao Bot;
- versão do modelo utilizada.

---

# 21.46. Plano e intenção do Bot

O Dashboard individual deve separar:

```text
OBJETIVO DE VIDA
→ OBJETIVO DE LONGO PRAZO
→ OBJETIVO ATUAL
→ SUBOBJETIVO
→ PRÓXIMA AÇÃO
```

Exemplo:

```text
Objetivo de vida:
Tornar-se Presidente

Objetivo de longo prazo:
Chegar à Presidência

Objetivo atual:
Tornar-se Governador

Subobjetivo:
Cumprir requisito de candidatura

Próxima ação:
Estudar
```

O Dashboard deve indicar os fatores objetivos que levam à próxima decisão.

---

# 21.47. Dashboard de decisão

Cada decisão relevante deve ser inspecionável.

Exemplo:

```text
DECISÃO #381294

Estado observado:
Dinheiro = R$18.420
Energia = 63%
Carisma = 97

Ações consideradas:

Estudar Direito       0,82
Trabalhar             0,71
Comprar imóvel        0,33
Abrir empresa         0,12
Comprar Aço           0,09

Ação escolhida:
Estudar Direito

Exploração:
18%

Confiança:
82%
```

A interface deve mostrar dados de decisão e avaliação, não inventar uma narrativa de “pensamento interno” do Bot.

---

# 21.48. Replay

Toda decisão importante deve ser potencialmente reproduzível.

A execução deve registrar informações suficientes para reproduzir um comportamento, incluindo quando aplicável:

- versão do jogo;
- versão do modelo;
- seed;
- estado relevante;
- observação recebida pelo Bot;
- ações válidas;
- ação escolhida;
- parâmetros da decisão;
- reward;
- resultado.

O Dashboard deve permitir iniciar um replay quando os dados necessários estiverem disponíveis.

---

# 21.49. Seed e reprodutibilidade

Cada Bot deve possuir um contexto aleatório reproduzível.

Uma decisão deve poder ser associada a:

```text
Bot
+ versão do jogo
+ versão do modelo
+ seed
+ estado
```

A reprodutibilidade não precisa significar que toda a execução histórica seja necessariamente reencenada para cada consulta, mas os dados necessários para investigar comportamentos anormais devem ser preservados.

---

# 21.50. Detecção de anomalias

O sistema deve identificar automaticamente comportamentos potencialmente anormais.

Exemplos:

```text
NO_PROGRESSION
Bot sem progresso relevante durante longo período.

MARKET_CONCENTRATION
Grande parte de um produto concentrada em poucas empresas.

BANKRUPTCY_CHAIN
Falências em cadeia acima do comportamento esperado.

REPEATED_ACTION
Bot repetindo ações improdutivas por período excessivo.

CAREER_GAP
Carreira praticamente não utilizada pela população.

POLITICAL_GAP
Pouquíssimos Bots disputam ou ocupam cargos.
```

A anomalia é um sinal de investigação, não uma conclusão automática de que existe um bug.

---

# 21.51. Separação entre Bot ruim e sistema ruim

O Dashboard deve permitir distinguir pelo menos quatro situações:

### Falta de oportunidade

O sistema não permite ou não oferece caminho viável.

### Falta de descoberta

A mecânica existe, mas poucos Bots sequer tentam utilizá-la.

### Falha de aprendizado

Bots tentam utilizar a mecânica, mas não melhoram com a experiência.

### Estratégia válida porém ruim

O Bot compreende a mecânica, mas seu objetivo/personalidade faz com que ele não a priorize.

Essa distinção é importante para não interpretar qualquer comportamento incomum como bug.

---

# 21.52. Performance do ambiente

O Dashboard deve medir o custo computacional do Bot Test.

No mínimo:

- CPU;
- RAM;
- GPU;
- VRAM;
- tempo de tick;
- decisões por segundo;
- tempo gasto no processamento da simulação;
- tempo gasto no banco de dados;
- tempo gasto no treinamento;
- filas do scheduler;
- erros e timeouts.

Exemplo:

```text
Bots ativos:                 1.000
CPU:                           61%
RAM:                         11,4 GB
GPU:                           47%
VRAM:                          3,8 GB
Tick médio:                  184 ms
Decisões/minuto:            4.823
```

A finalidade é identificar o gargalo real do ambiente antes de otimizar componentes incorretos.

---

# 21.53. Persistência e logs

O Bot Test deve produzir logs estruturados e exportáveis.

Não deve existir dependência de screenshots para analisar o comportamento.

O sistema deve permitir exportar um relatório completo de uma execução.

Formato sugerido:

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

A implementação pode alterar a divisão dos arquivos conforme necessidades de performance, mas os dados equivalentes devem permanecer acessíveis.

---

# 21.54. Informações mínimas da execução

Cada execução do Bot Test deve possuir identificador único e registrar, quando aplicável:

- ID da execução;
- data/hora de início;
- data/hora de término;
- versão do jogo;
- versão do modelo;
- configuração do Bot Test;
- população-alvo;
- velocidade do relógio;
- seed global, quando aplicável;
- quantidade de Bots criados;
- quantidade de Bots removidos;
- métricas agregadas;
- eventos e anomalias relevantes.

---

# 21.55. Log de ações

O histórico de ações deve registrar informação suficiente para analisar a execução das decisões.

Exemplo conceitual:

```json
{
  "timestamp": "...",
  "bot_id": 1842,
  "action": "work",
  "success": true,
  "energy_before": 71,
  "energy_after": 51,
  "money_before": 1820,
  "money_after": 1870
}
```

O formato exato pode variar, mas o log deve permitir reconstruir a consequência da ação.

---

# 21.56. Log de decisões

Além do resultado da ação, deve ser possível consultar a decisão que levou a ela.

Informações relevantes:

- estado observado;
- ações disponíveis;
- ação escolhida;
- score ou probabilidade;
- exploração aplicada;
- modelo utilizado;
- objetivo ativo;
- reward posterior;
- resultado.

Esse registro é especialmente importante para Bots Adversariais e para investigação de comportamentos inesperados.

---

# 21.57. Exportação para análise externa

O relatório exportado deve poder ser enviado para ferramentas externas de análise.

O formato deve priorizar:

- CSV para tabelas agregadas;
- JSON para configurações e registros estruturados;
- JSONL para grandes volumes de eventos sequenciais.

O objetivo é permitir posteriormente o envio de uma execução completa para análise manual, inclusive por ferramentas de IA.

---

# 21.58. Interação com a arquitetura do Polis

O sistema de Bots não deve reimplementar as regras dos sistemas existentes.

Ele deve consumir os mesmos serviços e ações utilizados pelo jogo.

Exemplos:

```text
01 — Skills
→ fornece estado e progressão das skills

02 — Empresas
→ fornece empresas, empregos, produção e custos

03 — Escolas
→ fornece cursos, qualidade e progressão educacional

04 — Dia a Dia
→ fornece Energia, QoL e ciclos temporais

05 — Inventário
→ fornece estoque e consumo

06 — Política
→ fornece cargos, eleições e ações políticas

07 — Leis
→ fornece regras legislativas

09 — Orçamento Público
→ fornece estado fiscal

10 — Imóveis e Zonas
→ fornece propriedades e ocupação

17 — Transparência de Mercado
→ fornece informações públicas de mercado

18 — Contratos
→ fornece contratos e obrigações

19 — Militar
→ fornece estado e ações militares

20 — Feedback
→ orienta a explicabilidade das decisões
```

O Bot deve funcionar como um consumidor desses sistemas, não como uma segunda implementação deles.

---

# 21.59. Sem LLM no primeiro Bot Test

LLMs não são necessárias para a primeira versão.

O sistema inicial utilizará:

- regras do jogo;
- heurísticas auxiliares;
- Action Registry;
- Action Masking;
- personalidade;
- objetivo;
- especialização;
- memória individual;
- Reinforcement Learning.

Uma futura utilização de LLM pode ser avaliada separadamente para comportamentos mais abertos, comunicação ou geração de estratégias, mas não faz parte do primeiro Bot Test.

---

# 21.60. Segurança do Bot Test

Os Bots não devem possuir caminhos especiais que permitam criar recursos ou dinheiro fora das regras.

Ferramentas administrativas devem existir apenas fora do agente e servir para:

- observar;
- congelar;
- reiniciar;
- inspecionar;
- exportar;
- reproduzir;
- comparar.

A separação entre **poder de teste do Admin** e **poder do Bot** deve ser preservada.

---

# 21.61. Objetivo final do sistema

O Bot Test deve permitir responder perguntas como:

> O mercado funciona depois de centenas de ciclos?

> Existem carreiras economicamente inviáveis?

> Existem empresas que quebram em cadeia?

> Existe concentração excessiva de produção?

> Os jogadores artificiais descobrem contratos?

> A política realmente produz disputa?

> Existem caminhos de progressão que ninguém utiliza?

> O sistema de educação é descoberto e utilizado?

> Existem loops econômicos?

> O jogo mantém interesse para estratégias diferentes?

> O servidor continua saudável com 1.000 jogadores artificiais?

> Um Bot novo consegue aprender o jogo através da experiência?

> Um Bot veterano se comporta de maneira diferente de um novato?

Essas perguntas, e não simplesmente a existência dos Bots, são o objetivo do sistema.

---

# 21.62. Critérios de sucesso do Bot Test

O sistema será considerado funcional quando conseguir:

1. manter uma população próxima da meta configurada;
2. executar Bots utilizando somente ações permitidas pelo jogo;
3. gerar experiências de RL de forma contínua;
4. treinar e versionar modelos;
5. manter memórias individuais;
6. distinguir personalidades e objetivos;
7. permitir interação entre Bots;
8. detectar lacunas de cobertura;
9. detectar anomalias econômicas e sistêmicas;
10. permitir inspeção individual completa;
11. medir performance computacional;
12. exportar logs e relatórios;
13. reproduzir comportamentos importantes através de seed e contexto apropriados;
14. permitir comparar versões do modelo;
15. funcionar continuamente no ambiente acelerado definido para o Bot Test.

---

# 21.63. Filosofia do Bot Test

O Bot Test não existe para provar que os Bots são bons jogadores.

Ele existe para descobrir **onde o Polis não funciona como esperado**.

Um Bot que encontra uma estratégia estranha, uma carreira pouco utilizada, uma concentração econômica extrema ou uma maneira inesperada de ganhar dinheiro não deve ser automaticamente considerado “ruim”.

Esses comportamentos são dados de teste.

A função do sistema é trazer esses comportamentos para o Dashboard, preservar os dados necessários e permitir que o Game Director investigue a causa.

O Bot deve ser tratado como um instrumento de exploração do próprio design do Polis.
