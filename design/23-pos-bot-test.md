# 23 — Pós-Bot Test

> Status: IDEIAS FUTURAS / FORA DO BOT TEST
>
> Este documento registra possibilidades de expansão para depois do primeiro Bot Test. As ideias abaixo descrevem direção e estrutura conceitual, mas não congelam balanceamento, fórmulas, quantidades ou requisitos de implementação.

## 1. Objetivo

Expandir o número de atividades econômicas e sociais disponíveis aos jogadores sem transformar cada atividade em um sistema isolado.

As futuras expansões devem, sempre que possível, reutilizar as fundações existentes de:

- empresas;
- produtos e receitas;
- produção;
- inventário;
- mercado e varejo;
- contratos;
- consumo;
- efeitos temporários;
- Qualidade de Vida (QoL);
- energia, skills e trabalho.

A intenção é aumentar a variedade de caminhos de progressão e, ao mesmo tempo, aprofundar as cadeias econômicas entre jogadores e empresas.

---

# 2. Indústria de TCG

## 2.1 Conceito

Empresas de entretenimento podem criar coleções de cartas colecionáveis (TCG).

Uma coleção é um produto intelectual criado por uma empresa e possui uma composição definida de cartas e raridades.

Exemplo:

```text
Coleção: Super Cartas
Empresa publicadora: Empresa X

Comuns (10)
- Soldado
- Voador Terrível
- Recruta
- ...

Incomuns (6)
- Soldado de Elite
- Caçador
- ...

Raras (3)
- Super Soldado
- Mega Pássaro
- ...

Ultra-rara (1)
- General Supremo
```

A composição da coleção deve ser congelada após sua publicação, evitando alterações posteriores que possam manipular a economia da coleção.

## 2.2 Produção

A coleção publicada gera um produto físico comercializável, como um pack.

O pack deve carregar a identidade da coleção e da empresa publicadora.

Fluxo básico:

```text
Empresa criadora
      ↓
Coleção
      ↓
Produção de packs
      ↓
Varejo de entretenimento
      ↓
Jogador
      ↓
Abertura do pack
      ↓
Cartas no inventário
```

As cartas obtidas podem existir como itens individuais, permitindo futura troca ou comercialização entre jogadores.

## 2.3 Licenciamento entre empresas

A criação de uma coleção e sua fabricação não precisam ser realizadas pela mesma empresa.

Uma empresa pode autorizar outra empresa a fabricar seus packs mediante contrato de licenciamento.

Exemplo:

```text
Empresa X
  │
  │ cria "Super Cartas"
  │
  └──────── autorização/licença ────────► Empresa Y
                                             │
                                             │ fabricação
                                             ↓
                                    Packs da coleção
                                             │
                                             └── pagamento de taxa/royalties
                                                 à Empresa X
```

Isso permite separar duas competências:

- criação/publicação de conteúdo;
- capacidade industrial de fabricação.

A Empresa X pode possuir uma coleção valiosa sem ter capacidade produtiva suficiente, enquanto a Empresa Y pode atuar como fabricante terceirizada de várias coleções.

Os contratos devem registrar a autorização e as condições econômicas da fabricação licenciada.

## 2.4 Varejo e eventos

Lojas de entretenimento podem vender packs diretamente aos jogadores.

As lojas também podem sediar eventos relacionados às coleções.

Exemplos conceituais:

- torneios;
- eventos de lançamento;
- encontros;
- atividades relacionadas a uma coleção específica.

No primeiro escopo desta ideia, os eventos podem funcionar principalmente como atividades que geram efeitos temporários, incluindo efeitos de QoL.

A intenção não é criar inicialmente um simulador complexo de regras de TCG. O foco é utilizar o TCG como atividade econômica, social e de entretenimento.

## 2.5 Pontos ainda abertos

Devem ser definidos futuramente:

- quantidade de cartas por coleção;
- quantidade de cartas em cada raridade;
- probabilidades de cada raridade nos packs;
- possibilidade e regras de troca entre jogadores;
- possibilidade de mercado secundário;
- regras dos eventos;
- duração e intensidade dos efeitos dos eventos;
- custos e condições de licenciamento.

Esses valores não precisam ser definidos antes da necessidade de implementação.

---

# 3. Indústria automobilística

## 3.1 Conceito

Criar uma cadeia econômica na qual empresas especializadas fabricam peças e montadoras combinam essas peças para produzir veículos.

Fluxo básico:

```text
Matérias-primas
      ↓
Fábricas de componentes
      ↓
Peças
      ↓
Montadora
      ↓
Veículo
      ↓
Varejo
      ↓
Jogador
```

## 3.2 Fábricas de componentes

Exemplos de componentes:

- carroceria;
- chassi;
- motor;
- câmbio;
- pneus;
- suspensão;
- sistema de intake;
- outros componentes futuros.

As peças podem possuir diferentes níveis de qualidade e características.

A cadeia industrial cria espaço para empresas especializadas em determinados componentes, em vez de exigir que uma única empresa produza tudo.

## 3.3 Montagem e características do veículo

A montadora utiliza diferentes peças para determinar as características do veículo final.

Possíveis atributos:

```text
Velocidade
Conforto
QoL
Eficiência
Outros atributos futuros
```

As peças não devem funcionar simplesmente como uma progressão linear de "melhor" e "pior". Diferentes configurações podem atender objetivos diferentes.

Exemplo conceitual:

```text
Configuração esportiva
+ velocidade
+ desempenho
ganho menor de QoL

Configuração de luxo
+ conforto
+ QoL
menor velocidade
```

A velocidade do veículo pode influenciar diretamente o tempo necessário para deslocamento.

Isso conecta a indústria automobilística ao sistema de viagens do jogador.

## 3.4 Diferenciação entre veículos

A mesma montadora pode criar diferentes linhas de veículos:

```text
Econômico
Esportivo
Luxo
Off-road
...
```

Cada configuração pode utilizar combinações diferentes de componentes e atender necessidades diferentes dos jogadores.

Isso cria espaço para competição por estratégia de produto, e não apenas por um único atributo de poder.

## 3.5 Mercado secundário

Como possibilidade futura, veículos podem permanecer como bens duráveis e ser revendidos entre jogadores.

Exemplo:

```text
Montadora
   ↓
Varejo
   ↓
Jogador A
   ↓
Jogador B
```

Nesse modelo, o veículo pode manter suas características de fabricação e configuração ao longo da sua vida útil.

Detalhes como desgaste, manutenção e depreciação ficam fora deste documento por enquanto.

## 3.6 Ponto técnico importante

A combinação de múltiplas peças pode produzir um número enorme de configurações.

A implementação futura deve evitar transformar cada combinação possível em um produto cadastrado independente.

O veículo pode precisar ser representado como um produto parametrizado por sua configuração e seus componentes, mantendo a economia administrável mesmo com grande variedade.

---

# 4. Empresa de desenvolvimento de jogos

## 4.1 Conceito

Criar empresas especializadas em desenvolvimento de jogos digitais.

Uma empresa inicia um projeto e seus funcionários trabalham para aumentar a porcentagem de conclusão.

Fluxo básico:

```text
Projeto
  ↓
Desenvolvimento
  ↓
Progresso 0% → 100%
  ↓
Lançamento
  ↓
Jogo como produto
  ↓
Jogador
  ↓
Consumo
  ↓
Efeito de QoL
```

## 4.2 Desenvolvimento

O projeto possui uma barra de progresso.

O trabalho dos funcionários aumenta essa progressão.

A capacidade dos funcionários pode influenciar:

- velocidade de desenvolvimento;
- qualidade final;
- outros atributos futuros do produto.

Exemplo:

```text
Projeto
0%
 ↓
25%
 ↓
50%
 ↓
75%
 ↓
100%
 ↓
Lançamento
```

## 4.3 Qualidade do jogo

A qualidade final do produto pode depender da qualidade da equipe e de outros fatores do desenvolvimento.

Um jogo de maior qualidade pode produzir um efeito de entretenimento mais forte.

A relação exata entre qualidade, desenvolvimento e efeito deve ser definida posteriormente.

## 4.4 Consumo

Após lançado, o jogo pode ser adquirido e consumido pelo jogador como produto de entretenimento.

O consumo gera um efeito temporário, potencialmente relacionado à QoL.

Como o efeito é temporário, o consumo também gera demanda recorrente:

```text
Desenvolvimento
      ↓
Lançamento
      ↓
Mercado
      ↓
Jogador
      ↓
Consumo
      ↓
Efeito temporário
      ↓
Nova demanda
```

Isso permite que a indústria de jogos participe continuamente da economia em vez de funcionar como uma venda única.

## 4.5 Expansões futuras

O mesmo modelo pode posteriormente ser usado para outros produtos digitais e formas de entretenimento, sem que isso precise ser implementado junto com a primeira versão do sistema.

Possibilidades conceituais:

- filmes;
- música;
- livros;
- revistas;
- outros conteúdos digitais.

A prioridade deve ser validar primeiro um modelo simples de produção → produto → consumo → efeito.

---

# 5. Princípios comuns dessas expansões

## 5.1 Produtos devem ter função no mundo

Novos produtos não precisam existir apenas para gerar dinheiro entre empresas.

Sempre que fizer sentido, o produto pode alterar a vida do jogador.

Exemplos:

```text
TCG
→ entretenimento/social
→ eventos
→ QoL

Carro
→ transporte
→ tempo de viagem
→ QoL

Jogo
→ entretenimento
→ efeito temporário
→ QoL
```

Isso aproxima a economia das atividades cotidianas do jogador.

## 5.2 Especialização econômica

Uma mesma cadeia pode envolver várias empresas com funções diferentes.

Exemplo:

```text
Criador
→ Licenciador
→ Fabricante
→ Distribuidor/Varejo
→ Consumidor
```

Isso cria espaço para especialização, contratos e relações comerciais entre jogadores.

## 5.3 Evitar progressão puramente linear

Sempre que possível, os sistemas devem oferecer escolhas com trade-offs.

Um produto mais caro ou de tier maior não precisa ser simplesmente melhor em todos os atributos.

Exemplos:

```text
Mais velocidade
↔ menor QoL

Mais luxo
↔ menor velocidade

Maior qualidade
↔ maior custo

Maior escala
↔ maior dependência de cadeia produtiva
```

Os trade-offs exatos serão definidos por balanceamento.

## 5.4 Reutilização das fundações

Essas expansões devem preferencialmente utilizar as mesmas estruturas centrais do jogo, evitando criar uma lógica paralela para cada atividade.

Um novo sistema deve procurar encaixar-se na cadeia:

```text
Empresa
→ Receita/Produção
→ Produto
→ Inventário
→ Mercado/Varejo
→ Consumo/uso
→ Efeito
```

Quando necessário, contratos e licenciamento devem conectar empresas diferentes dentro da mesma cadeia.

## 5.5 Balanceamento

Nenhum valor apresentado neste documento deve ser tratado como balanceamento definitivo.

Quantidades, probabilidades, custos, tiers, velocidades, efeitos, duração e fórmulas devem ser definidos por parâmetros e ajustados posteriormente com dados de simulação e testes.

O objetivo deste documento é registrar a direção das futuras expansões, não antecipar valores sem dados.

---

# 6. Possíveis novas cadeias econômicas

Esses conceitos também estabelecem um padrão que pode ser reutilizado em outras expansões:

```text
Matéria-prima
→ componente
→ produto final
→ varejo
→ jogador
```

ou:

```text
Propriedade intelectual
→ licenciamento
→ fabricação
→ varejo
→ consumo
```

ou:

```text
Trabalho especializado
→ desenvolvimento
→ produto digital
→ consumo
→ efeito temporário
```

A expansão pós-Bot Test pode, portanto, ser orientada menos por "criar mais menus" e mais por adicionar novas cadeias pelas quais jogadores podem produzir, negociar, consumir e criar valor dentro da economia de Nova Polis.
