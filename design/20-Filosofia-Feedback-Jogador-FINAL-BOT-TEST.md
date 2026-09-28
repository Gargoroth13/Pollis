# 20 — Filosofia de Feedback ao Jogador (UI)

**Status: FINAL — BOT TEST**

## 20.1. Princípio geral

Para todo indicador importante do jogo, o jogador não deve receber apenas o valor final.

Ao consultar um indicador, o sistema deve permitir visualizar **como o valor foi formado**, incluindo os fatores relevantes que aumentaram, reduziram ou multiplicaram o resultado.

Exemplo:

```text
QoL: 0,82 → 0,76

Moradia:                    +0,10
População acima do ideal:   −0,10
Nutrição baixa:             −0,04
Saúde baixa:                −0,02
```

O objetivo é que o jogador consiga responder:

> “Por que meu valor está assim?”

sem precisar descobrir a resposta por tentativa e erro.

---

## 20.2. O detalhamento faz parte do resultado da fórmula

Toda fórmula composta utilizada por sistemas do jogo deve retornar não apenas o valor final, mas também um **detalhamento estruturado dos fatores utilizados no cálculo**.

Conceitualmente:

```text
Resultado
├── valor final
└── detalhamento
    ├── fator A
    ├── fator B
    ├── fator C
    └── ...
```

Isso deve ser uma convenção de implementação desde o início.

Não se deve implementar inicialmente:

```python
resultado = calcular()
```

e posteriormente tentar reconstruir a explicação a partir do resultado.

A própria função que calcula o valor deve produzir também os dados necessários para explicá-lo.

---

## 20.3. Diferentes tipos de fórmula

O detalhamento não precisa utilizar sempre o formato `+X / −X`.

O sistema deve representar a estrutura adequada à fórmula.

### Fórmula aditiva

```text
QoL: 0,76

Base:                       0,82
Moradia:                   +0,10
População acima do ideal:  −0,10
Nutrição:                  −0,04
Saúde:                     −0,02
```

### Fórmula multiplicativa

```text
Produção: 1.840 unidades

Produção base:              1.200
Eficiência dos funcionários: ×1,25
Engenheiros:                  ×1,30
Especialização:               ×0,95
```

### Fórmula com limite

```text
Cobertura de armas: 100%

Armas disponíveis:       125%
Limite operacional:       100%
Resultado utilizado:      100%
```

Nesse caso, o jogador consegue perceber que possuir 125% de cobertura não aumenta o resultado porque existe um teto.

### Fórmula condicional

```text
Salário: R$ 180/dia

Salário calculado pela skill: R$ 210
Salário mínimo:               R$ 50
Teto legal:                   R$ 180
Resultado:                    R$ 180
```

O detalhamento precisa mostrar **qual regra restringiu o resultado**.

---

## 20.4. O detalhamento deve explicar o estado atual, não inventar causalidade

O sistema deve mostrar os fatores efetivamente utilizados na fórmula.

Ele não deve afirmar uma causalidade que o modelo não calcula.

Exemplo válido:

```text
Custos da empresa aumentaram 14%.

Aço:                    +R$ 420
Salários:               +R$ 110
Materiais operacionais: +R$ 30
```

Já uma afirmação como:

```text
O aumento do preço do aço causou exatamente 76% da inflação da empresa.
```

só deve aparecer se o sistema realmente possuir essa análise causal.

Isso mantém o feedback compatível com o que o jogo efetivamente simula.

---

## 20.5. Valores e variações

Quando relevante, o detalhamento deve permitir visualizar tanto o **valor atual** quanto a **variação**.

Exemplo:

```text
Produção diária: 1.840

Base:                  1.200
Funcionários:          ×1,25
Engenheiros:           ×1,30
Especialização:        ×0,95

Ontem:                 1.710
Variação:              +130
```

O jogador deve conseguir distinguir:

> “Por que estou com esse valor?”

 de:

> “Por que esse valor mudou?”

São perguntas diferentes e ambas podem ser importantes.

---

## 20.6. Detalhamento hierárquico

Fórmulas complexas podem possuir vários níveis.

Exemplo:

```text
Força Militar: 1.240

Força Humana: 620
  Número de combatentes:       20
  Físico médio:                80
  Especialização militar:     ×0,775

Equipamento:
  Cobertura de armas:          100%
  Cobertura de armadura:       100%

Outros modificadores:
  Prontidão:                  ×1,00
```

Ao clicar em um componente, o jogador pode abrir níveis adicionais de detalhe.

Isso evita uma tela gigantesca mostrando todos os detalhes simultaneamente.

---

## 20.7. Separação entre cálculo e apresentação

O detalhamento produzido pela fórmula deve ser um **dado estruturado do sistema**, e não texto pronto escrito especificamente para uma tela.

A UI decide como apresentar a informação.

Isso permite utilizar o mesmo cálculo em:

- página do jogador;
- empresa;
- política;
- militar;
- mercado;
- notificações;
- histórico;
- ferramentas de administração.

O texto apresentado ao jogador pode variar, mas os dados que explicam o cálculo permanecem os mesmos.

---

## 20.8. Arredondamento

O cálculo deve utilizar os valores reais definidos pelo sistema.

O arredondamento apresentado na UI não pode alterar o resultado efetivo da fórmula.

Exemplo:

```text
Valor interno: 0,763847

UI:
QoL: 0,76
```

Os componentes exibidos também podem ser arredondados para leitura, desde que a soma visual não gere uma inconsistência relevante.

Quando necessário, a UI deve indicar valores aproximados.

---

## 20.9. Atualização do feedback

Quando um indicador puder mudar automaticamente com o tempo, o detalhamento deve utilizar os valores atuais do sistema.

O jogador não deve precisar executar uma ação apenas para atualizar artificialmente a explicação.

Exemplo:

```text
QoL: 0,76

Última atualização: 12:00

Moradia:        +0,10
Saúde:          −0,02
Nutrição:       −0,04
```

O momento da atualização é especialmente importante para indicadores baseados em ciclos, médias ou dados históricos.

---

## 20.10. Feedback explicável como regra transversal

Esta filosofia deve ser aplicada aos principais indicadores compostos do jogo, incluindo, entre outros:

- QoL;
- saúde;
- produção;
- qualidade de empresas;
- custos;
- salários;
- capacidade de empresas;
- força militar;
- prontidão;
- resultados econômicos;
- efeitos de leis;
- efeitos de campanhas;
- rankings derivados de múltiplos dados.

Não é necessário criar uma explicação complexa para cada número trivial da interface.

O foco é nos valores que influenciam decisões do jogador ou que podem gerar dúvida sobre o estado do jogo.

---

## 20.11. Regra para novas fórmulas

Sempre que um novo sistema criar uma fórmula composta, sua implementação deve incluir simultaneamente:

1. cálculo do valor;
2. detalhamento dos fatores;
3. identificação de limites e regras condicionais relevantes;
4. dados necessários para apresentação na UI.

Uma fórmula composta não deve entrar no sistema somente com seu valor final.

---

## 20.12. Objetivo de design

O jogador deve ser capaz de compreender as consequências das próprias ações através do próprio jogo.

A interface não deve exigir que o jogador conheça o código, descubra fórmulas por experimentação ou dependa de documentação externa para entender por que um indicador mudou.

A regra geral é:

> **O jogo deve mostrar não apenas o resultado, mas os fatores que produziram esse resultado.**

---

## 20.13. Regra arquitetural

O detalhamento dos cálculos deve ser tratado como parte da arquitetura dos sistemas do jogo, e não como um recurso exclusivamente visual.

Ao criar ou alterar uma fórmula composta, o desenvolvimento deve preservar a capacidade de explicar o resultado ao jogador.

O feedback deve nascer junto com o cálculo, evitando um retrofit posterior em que seria necessário reconstruir os fatores a partir de um valor já calculado.

Essa regra vale para os sistemas do Bot Test e deve permanecer como padrão para as futuras implementações do projeto.
