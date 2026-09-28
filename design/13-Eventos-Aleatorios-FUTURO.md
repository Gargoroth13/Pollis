# 13 — Sistema de Eventos Aleatórios

**Status: FUTURO — FASE TARDIA**

## 13.0. Objetivo do sistema

O sistema de Eventos Aleatórios existe para introduzir acontecimentos inesperados no servidor e fazer o mundo reagir sem criar sistemas paralelos de modificadores abstratos.

O princípio central é:

> **Um evento deve alterar uma condição real que já existe no jogo.**

O evento não deve simplesmente aplicar um modificador genérico como "+20% de eficiência". Ele altera estoque, produção, Saúde, QoL, população ou outro estado já utilizado pelos sistemas existentes. Depois disso, os sistemas normais do jogo calculam as consequências.

Exemplo:

> Um acidente reduz o estoque de Ferro de uma Matriz de Mineração.
>
> O evento não aumenta diretamente o preço do Ferro. A redução do estoque é processada pelo sistema econômico, e preço, disponibilidade e custos das empresas reagem normalmente.

---

## 13.1. Princípios

### Eventos alteram estados existentes

Cada evento deve ter como efeito uma alteração concreta em um estado já existente.

Exemplos válidos:

- reduzir estoque de uma empresa;
- reduzir produção de uma operação existente;
- reduzir QoL de uma região;
- aumentar temporariamente uma chance já existente, como a chance de decaimento de Saúde;
- alterar população existente, caso o sistema populacional futuro esteja implementado;
- criar ou modificar uma oportunidade real já prevista por outro sistema.

Não devem existir, como regra geral, modificadores paralelos que outros sistemas precisem consultar apenas para saber se um evento está ativo.

### O evento não calcula toda a consequência

O evento altera o estado inicial. Os sistemas responsáveis calculam o restante.

Exemplo:

> Evento reduz estoque de Aço → mercado registra menor oferta → preço pode subir → empresas que utilizam Aço podem ter custo maior.

O sistema de Eventos não precisa possuir lógica própria para preço ou custo.

---

## 13.2. Estrutura de um evento

Um evento deve possuir, no mínimo:

| Campo | Função |
|---|---|
| Tipo | Identifica o evento |
| Data/hora | Momento em que ocorreu |
| Escopo | Bairro, cidade, Estado ou país, conforme o evento |
| Alvo | Entidade afetada, quando aplicável |
| Intensidade | Magnitude da alteração |
| Duração | Quando o efeito não for instantâneo |
| Estado | Ativo, encerrado ou resolvido |

A implementação pode utilizar um modelo próprio de evento ou integração direta com os sistemas afetados, desde que preserve o histórico e permita auditoria.

---

## 13.3. Geração dos eventos

Os eventos são aleatórios, mas **não completamente irrestritos**.

O servidor deve utilizar uma camada de controle para evitar sequências excessivas ou repetitivas.

### Regras de controle

#### Cooldown global

Após a ocorrência de um evento, deve existir um intervalo mínimo antes que outro evento possa ser gerado.

O valor exato será calibrado em uma fase futura.

#### Cooldown por tipo

Depois que um determinado tipo de evento ocorre, existe um intervalo adicional antes que outro evento do mesmo tipo possa ocorrer novamente.

#### Peso dinâmico

Eventos ocorridos recentemente devem perder peso na seleção durante algum período.

Isso reduz a probabilidade de repetições consecutivas sem tornar a seleção totalmente determinística.

#### Limite de eventos ativos

O servidor deve possuir um limite de eventos simultaneamente ativos, evitando que muitos eventos com duração se acumulem e criem um estado econômico artificialmente caótico.

### Objetivo

O resultado desejado é **aleatoriedade controlada**:

- o jogador não sabe qual evento ocorrerá;
- os eventos não acontecem em sequência excessiva;
- o mesmo evento não domina o servidor repetidamente;
- eventos simultâneos permanecem dentro de uma quantidade razoável.

Os valores de cooldown, pesos, frequência e limite de eventos ativos são parâmetros de balanceamento futuro.

---

## 13.4. Eventos previstos

Os eventos abaixo representam conteúdo planejado para fases posteriores. Os parâmetros de chance, intensidade, duração e frequência ainda não estão definidos.

| Evento | Alteração real | Consequência esperada |
|---|---|---|
| Acidente em mina | Reduz ou zera o estoque de uma Matriz de Mineração específica | Menor oferta do recurso pode afetar produção e preços |
| Desastre natural | Reduz QoL de um território e pode destruir parte de estoques existentes | Piora das condições locais e possíveis efeitos econômicos indiretos |
| Pandemia | Aumenta temporariamente a chance de decaimento de Saúde em uma região | Mais internações, menor disponibilidade de jogadores para trabalhar e possíveis efeitos na produção |
| Descoberta de recurso | Disponibiliza uma nova ocorrência física de recurso ou amplia capacidade de uma ocorrência existente | Maior oferta de matéria-prima pode reduzir preços |
| Falência forçada de empresa importante | Força o encerramento de uma empresa elegível | Trabalhadores ficam sem emprego e estoque da empresa deixa de estar disponível no mercado |
| Escassez | Reduz o estoque disponível de um Produto específico | Menor oferta pode elevar o preço e pressionar empresas que dependem do produto |
| Migração | Altera a população de um território em uma grande mudança única | Pode alterar a faixa populacional e seus efeitos territoriais |
| Crise bancária | Altera negativamente o estado de solvência das Financeiras | Pode afetar crédito e desencadear respostas de outros sistemas |

### Evento removido: Boom Econômico

O conceito de aumentar artificialmente a demanda por meio de compradores fictícios foi removido.

O Polis não utiliza NPCs como agentes econômicos. A demanda econômica normal é gerada pelos próprios jogadores e pelos usos reais dos produtos no jogo.

Portanto, um evento não deve criar compradores fictícios ou dinheiro novo apenas para aumentar a demanda.

Uma futura demanda externa real poderá ser criada pelo sistema de comércio internacional/exportação, quando esse sistema existir.

---

## 13.5. Acidente em mina

O acidente deve agir diretamente sobre o estoque de uma Matriz de Mineração.

Exemplo:

> A Mina Aurora sofre um acidente e perde 70% do estoque disponível de Ferro.

O evento não altera diretamente o preço do Ferro.

O mercado e as empresas reagem ao novo estoque por suas próprias regras.

A implementação inicial deve preferir alterações de estoque a regras paralelas de eficiência.

---

## 13.6. Desastre natural

O desastre natural pode afetar diretamente um território e combinar mais de uma alteração real já suportada pelos sistemas existentes.

Exemplos:

- reduzir QoL local;
- destruir parte do estoque de empresas do território;
- futuramente afetar outras estruturas caso exista um estado de destruição aplicável.

O evento não deve simplesmente aplicar um multiplicador global de eficiência.

---

## 13.7. Pandemia

A pandemia deve utilizar o sistema de Saúde já existente.

O evento aumenta temporariamente a chance de decaimento de Saúde em uma região.

O restante da cadeia pertence ao sistema normal:

> mais jogadores com Saúde baixa ou em recuperação → mais internações → menos jogadores disponíveis para outras atividades → possível redução da produção.

O evento não deve implementar uma segunda versão paralela do sistema de Saúde.

---

## 13.8. Descoberta de recurso

A descoberta de recurso é um evento de maior complexidade e depende da infraestrutura definida em `08 — Geografia`.

Pode:

- abrir uma nova ocorrência física de recurso em uma zona Rural elegível; ou
- aumentar o teto produtivo de uma ocorrência existente.

O evento deve alterar a disponibilidade real do recurso no mapa, não simplesmente conceder um bônus abstrato de produção.

---

## 13.9. Falência forçada de empresa importante

O evento pode forçar a entrada de uma empresa elegível em estado de falência.

A falência deve ser processada pelo sistema de Empresas.

O sistema de Eventos apenas dispara a condição excepcional.

O sistema `12 — Histórico do Mundo` pode então transformar a ocorrência em notícia pública quando apropriado.

Empresas consideradas historicamente relevantes para notícias utilizam o mesmo critério de estrela definido no `12`.

---

## 13.10. Escassez

O evento de escassez reduz diretamente o estoque disponível de um Produto específico.

Não altera diretamente preço ou custo.

O mercado reage à nova oferta por suas regras normais.

A implementação pode utilizar a mesma infraestrutura de alteração de estoque dos demais eventos, mantendo o evento como uma origem diferente da alteração.

---

## 13.11. Migração

O evento de migração permanece planejado para uma fase futura.

Quando existir população de NPC apenas como população territorial, o evento poderá alterar essa população de uma cidade ou região de uma só vez.

A consequência sobre a faixa populacional e QoL deve ser calculada pelo sistema territorial existente.

Migração real de jogadores continua sendo uma ação dos próprios jogadores e não uma consequência artificial do evento.

---

## 13.12. Crise bancária

A crise bancária depende da existência completa do sistema de Financeiras.

O evento deve alterar diretamente uma condição já existente de solvência ou capacidade financeira.

O sistema bancário deverá produzir as consequências econômicas posteriores.

Não existe, nesta etapa, uma regra fechada para intervenção governamental automática.

---

## 13.13. Integração com outros sistemas

### `08 — Geografia`

Fornece territórios, Matrizes, recursos e ocorrências espaciais que podem ser afetados por eventos.

### `09 — Orçamento Público`

Pode sofrer consequências econômicas indiretas de eventos, mas o sistema de Eventos não deve criar dinheiro público sem uma regra econômica correspondente.

### `12 — Histórico do Mundo`

Eventos relevantes podem gerar notícias automaticamente em linguagem jornalística.

Exemplo:

> **Acidente reduz estoque de Ferro em 18%**
>
> Um acidente em uma operação de mineração reduziu significativamente a oferta nacional de Ferro.

O `12` é responsável pela apresentação pública da notícia; o `13` é responsável apenas pelo evento e sua alteração real.

### `17 — Transparência de Mercado`

As consequências de eventos sobre estoque, produção, consumo e preços aparecem nos indicadores econômicos quando esses dados realmente mudarem.

### `22 — Receitas-Produção`

Fornece os Produtos e usos que determinam quais alterações econômicas são relevantes para cada evento.

### Sistemas futuros

Eventos futuros podem integrar-se a sistemas de comércio internacional, Financeiras e outros sistemas ainda não existentes.

---

## 13.14. Histórico e auditoria

Todo evento disparado deve ser registrado para o servidor e para ferramentas de Dev/Admin.

O registro deve permitir identificar:

- tipo do evento;
- data/hora;
- alvo;
- alteração aplicada;
- intensidade;
- duração, quando aplicável;
- resultado final.

O histórico técnico não precisa ser exibido ao jogador em sua forma bruta.

A informação pública deve ser apresentada pelo `12 — Histórico do Mundo` quando o evento for considerado noticiável.

---

## 13.15. Escopo do Bot Test

O sistema de Eventos Aleatórios completo **não faz parte do primeiro Bot Test**.

Não é necessário implementar, nesta etapa:

- catálogo completo de eventos;
- cálculo definitivo de probabilidades;
- cooldowns finais;
- sistema de pesos definitivo;
- eventos com Financeiras;
- eventos com população futura;
- descoberta dinâmica de recursos;
- eventos econômicos que dependam de demanda externa.

A prioridade do primeiro Bot Test permanece sendo testar os sistemas estruturais do Polis antes de adicionar eventos aleatórios que alterem o estado do servidor.

---

## 13.16. Princípios de design

1. **Aleatoriedade controlada:** eventos devem ser imprevisíveis sem produzir spam ou repetição excessiva.
2. **Causa e efeito reais:** eventos alteram estados existentes e deixam os sistemas normais produzirem as consequências.
3. **Sem demanda fictícia:** eventos não criam consumidores ou dinheiro artificialmente para movimentar o mercado.
4. **Integração:** o sistema de Eventos não deve duplicar regras de Economia, Saúde, Geografia ou outros sistemas.
5. **Auditabilidade:** todo evento deve possuir registro técnico suficiente para Dev/Admin e histórico.
6. **Escopo progressivo:** o sistema completo pode ser expandido depois que o núcleo do jogo estiver funcionando.
