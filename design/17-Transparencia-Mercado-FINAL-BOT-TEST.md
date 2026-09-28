# 17 — Transparência de Mercado

**Status: FINAL — BOT TEST**

## 17.0. Objetivo do sistema

O sistema de Transparência de Mercado transforma os dados econômicos já produzidos pelo jogo em informações úteis para os jogadores.

O objetivo não é expor cada transação individual ao jogador comum, mas permitir que ele entenda o estado do mercado, a evolução dos preços, a relação entre produção e consumo e, no caso de empresas, quais componentes mais contribuíram para mudanças nos custos.

O sistema também mantém o histórico bruto necessário para auditoria, debugging, balanceamento e futuras mecânicas econômicas.

---

# 17.1. Escopo do Bot Test

No primeiro Bot Test, os indicadores de mercado serão apresentados como **dados agregados do mercado nacional**.

Não haverá, inicialmente, painéis separados por bairro, cidade, Estado, empresa produtora ou vendedor.

A infraestrutura deve, entretanto, preservar os dados necessários para que filtros e análises territoriais possam ser adicionados futuramente sem redesenhar o histórico de transações.

---

# 17.2. Histórico de transações

Toda venda concluída no mercado deve gerar um registro histórico real da transação.

Cada registro deve conter, no mínimo:

| Dado | Descrição |
|---|---|
| Produto | Produto negociado |
| Quantidade | Quantidade efetivamente vendida |
| Preço unitário | Preço efetivamente pago por unidade |
| Valor total | Valor total da transação |
| Data/hora | Momento em que a transação foi concluída |
| Comprador | Entidade compradora |
| Vendedor | Entidade vendedora |

Comprador e vendedor podem ser jogadores ou empresas, conforme as regras do Mercado e dos sistemas que realizam a transação.

O histórico completo permanece armazenado no servidor durante o Bot Test.

Esses registros brutos existem para uso do sistema, auditoria, debugging e futuras análises. Eles não precisam ser apresentados individualmente ao jogador comum.

---

# 17.3. Preço médio do Produto

O preço médio utilizado na transparência de mercado é uma **média ponderada pela quantidade** das vendas concluídas no período analisado.

```text
preço_médio = soma(preço_unitário × quantidade) / soma(quantidade)
```

Exemplo:

```text
10 unidades a R$ 10
100 unidades a R$ 20

preço médio = (10×10 + 100×20) / 110
             = R$ 19,09
```

Isso impede que uma transação muito pequena tenha o mesmo peso de uma transação grande.

O preço médio exibido na visão principal do Produto utiliza as transações concluídas nas **últimas 24 horas**.

---

# 17.4. Menor e maior preço

Os indicadores de menor e maior preço utilizam somente **vendas efetivamente concluídas**, nunca anúncios ou preços de listagem que não resultaram em venda.

Na visão principal do Produto:

- **Menor preço:** menor preço unitário entre as vendas concluídas nas últimas 24 horas.
- **Maior preço:** maior preço unitário entre as vendas concluídas nas últimas 24 horas.

Isso evita que anúncios extremamente caros ou baratos, sem compradores, distorçam as informações.

---

# 17.5. Estoque disponível

**Estoque total** representa a quantidade do Produto que está atualmente disponível para venda no Mercado nacional.

Não entram nesse número produtos que já estejam reservados ou comprometidos por outra mecânica e, portanto, não possam ser comprados no Mercado naquele momento.

O objetivo do indicador é representar a oferta que o jogador realmente consegue encontrar no Mercado.

---

# 17.6. Produção diária

**Produção diária** representa a quantidade do Produto que foi efetivamente produzida nas últimas 24 horas.

O indicador não representa capacidade teórica de produção.

Exemplo:

```text
Capacidade das empresas: 20.000 unidades/dia
Produção real:           11.800 unidades/dia

Produção diária exibida: 11.800
```

A produção real deve refletir as limitações existentes nos sistemas de produção, incluindo disponibilidade de insumos, trabalhadores, Energia, especialização e demais regras efetivamente aplicadas.

---

# 17.7. Consumo diário

**Consumo diário** representa a quantidade do Produto que foi efetivamente utilizada nas últimas 24 horas.

Comprar ou vender um Produto não significa, por si só, consumi-lo.

Exemplo:

Uma Industrial compra 1.000 unidades de Aço e mantém o material em estoque. Essas 1.000 unidades representam uma compra/demanda de mercado, mas não são consumo até serem efetivamente utilizadas.

O consumo ocorre quando o Produto é retirado de circulação para uma utilização real, como:

- ingrediente de uma receita;
- material operacional;
- consumo por jogador;
- outra utilização definida por um sistema do jogo.

---

# 17.8. Tendência de preço

A tendência padrão do Produto será apresentada como uma variação percentual comparando dois períodos consecutivos de sete dias.

```text
Tendência = ((média dos últimos 7 dias / média dos 7 dias anteriores) - 1) × 100
```

A média utilizada para cada período é a média ponderada pelas quantidades negociadas naquele período.

Exemplo:

```text
Últimos 7 dias:       R$ 50,00
7 dias anteriores:    R$ 46,30

Tendência:             +8,00%
```

A tendência representa evolução do preço, não uma previsão futura.

---

# 17.9. Dados sem histórico suficiente

Quando não houver transações suficientes para calcular um indicador, o sistema não deve inventar um valor utilizando o `preco_base` do catálogo.

O indicador deve ser apresentado como **"Sem dados"**.

Isso vale especialmente para produtos novos ou que ainda não tenham sido negociados no período necessário.

O `preco_base` do catálogo não substitui o histórico real de transações para fins de estatística de mercado.

---

# 17.10. Agregação dos dados

O sistema deve manter duas camadas de informação:

### Histórico bruto

Todas as transações concluídas permanecem registradas individualmente.

### Agregados

O sistema mantém ou calcula dados agregados por Produto e por dia para reduzir o custo de consulta das páginas públicas.

Os agregados devem permitir, entre outros:

- preço médio ponderado;
- menor preço;
- maior preço;
- volume negociado;
- estoque;
- produção;
- consumo.

As páginas de jogador não devem precisar consultar milhões de transações brutas para montar um gráfico de 30 dias.

---

# 17.11. Página do Mercado

A página geral do Mercado apresenta uma visão resumida da situação econômica.

Ela pode mostrar, entre outros indicadores:

- produtos com maior alta de preço;
- produtos com maior queda de preço;
- volumes relevantes de negociação;
- outras estatísticas agregadas que já estejam disponíveis sem criar uma nova camada de simulação.

A página geral não substitui a página individual do Produto.

---

# 17.12. Página do Produto

A página individual de cada Produto é o principal ponto de consulta das estatísticas de mercado.

A visão principal deve apresentar, no mínimo:

| Indicador | Período |
|---|---|
| Preço médio | Últimas 24 horas |
| Menor preço | Últimas 24 horas |
| Maior preço | Últimas 24 horas |
| Estoque disponível | Momento atual |
| Produção diária | Últimas 24 horas |
| Consumo diário | Últimas 24 horas |
| Tendência de preço | Últimos 7 dias vs. 7 dias anteriores |

Exemplo conceitual:

```text
Café

Preço médio:       R$ 42
Menor preço:       R$ 31
Maior preço:       R$ 68
Estoque disponível: 14.200
Produção diária:    11.800
Consumo diário:     13.500
Tendência:          +8% (últimos 7 dias)
```

Os valores acima são apenas exemplo de apresentação.

---

# 17.13. Gráficos do Produto

A página do Produto deve possuir gráficos no primeiro Bot Test.

O período visualizado será de **30 dias**, para permitir comparação entre comportamento recente e histórico próximo.

### Gráfico de preço

Mostra a evolução do preço médio do Produto ao longo dos últimos 30 dias.

### Gráfico de oferta e demanda física

Mostra, ao longo dos últimos 30 dias:

- estoque disponível;
- produção diária;
- consumo diário.

O objetivo é permitir que o jogador visualize situações como redução de estoque, aumento de consumo ou queda de produção antes que essas condições sejam compreendidas apenas pelos preços.

Os gráficos utilizam os dados agregados do sistema, não o histórico bruto diretamente.

---

# 17.14. Transparência de custos da Empresa

A página da Empresa deve apresentar uma visão resumida da evolução de seus próprios custos.

Exemplo:

> **Seus custos aumentaram 14% nos últimos 7 dias.**
>
> Principal contribuição: Aço, cujo custo médio aumentou 21%.

A análise pode apresentar os principais componentes de custo separados por categoria, conforme os custos existentes no sistema.

Exemplo:

| Componente | Variação |
|---|---:|
| Aço | +21% |
| Salários | +8% |
| Plástico | +3% |
| Materiais operacionais | +2% |

Os componentes exibidos dependem dos custos efetivamente registrados pela empresa.

---

# 17.15. Interpretação da causa dos custos

A transparência de custos não deve afirmar uma causalidade econômica perfeita quando vários fatores alteraram o custo total simultaneamente.

O sistema deve identificar a **principal contribuição observada** para a variação dos custos.

Exemplo preferível:

> Principal contribuição para o aumento dos custos: Aço (+R$ X).

Em vez de:

> Aço causou exatamente 67,4% do aumento dos custos.

O objetivo inicial é explicar ao jogador qual componente merece sua atenção, sem criar um modelo analítico muito mais complexo do que o necessário.

Futuramente, o detalhamento poderá distinguir, por exemplo, aumento do preço do insumo de aumento da quantidade consumida.

---

# 17.16. Histórico de custos da Empresa

Para permitir a explicação de custos sem consultas pesadas, a Empresa deve possuir registros históricos agregados de seus gastos.

A estrutura deve permitir separar, no mínimo, os custos já existentes no sistema em categorias como:

- matérias-primas e ingredientes;
- materiais operacionais;
- salários;
- impostos e taxas;
- outros custos efetivamente definidos pelos sistemas do jogo.

O registro diário permite comparar os últimos sete dias com os sete dias anteriores.

---

# 17.17. Navegação entre informações

A transparência deve funcionar como uma camada conectada às páginas existentes, e não como um sistema isolado.

Exemplo:

```text
Empresa
  → custo de Aço aumentou
  → jogador acessa a página de Aço
  → vê preço, estoque, produção, consumo e tendência
```

A página do Produto pode posteriormente direcionar o jogador ao Mercado e às empresas relacionadas, conforme os sistemas existentes permitirem.

---

# 17.18. Informação pública x informação técnica

O jogador comum recebe informações agregadas e interpretáveis.

O servidor mantém o histórico completo das transações e dos registros necessários para cálculo e auditoria.

Não faz parte do Bot Test exibir ao jogador uma lista completa das transações individuais, com comprador, vendedor, horário e quantidade de cada operação.

Esses dados permanecem disponíveis para:

- debugging;
- auditoria;
- balanceamento;
- análise posterior;
- futuras mecânicas econômicas.

---

# 17.19. Desempenho e consultas

A interface pública deve utilizar preferencialmente dados agregados e registros recentes, evitando varrer o histórico bruto completo a cada consulta.

A arquitetura deve seguir a separação:

```text
Transação concluída
→ registro histórico bruto
→ atualização/geração de agregado diário
→ páginas consultam os agregados
```

O Bot Test deve observar o volume real de dados antes de introduzir mecanismos mais complexos de particionamento, retenção ou compressão do histórico.

A prioridade inicial é manter os dados completos e corretos.

---

# 17.20. Relação com o preço base do Produto

O `preco_base` do catálogo continua sendo um parâmetro de referência para os sistemas que utilizarem esse conceito.

Entretanto, estatísticas como preço médio, menor preço, maior preço e tendência devem utilizar **preços efetivamente praticados nas transações**.

A transparência de mercado não deve tratar o `preco_base` como se fosse o preço real de todas as vendas.

---

# 17.21. Relação com outros sistemas

### `02 — Empresas`

Fornece produção, consumo de insumos, custos e estoque empresarial utilizados pelos indicadores.

### `05 — Inventário`

Fornece a camada de armazenamento e uso de Produtos pelos jogadores.

### `09 — Orçamento Público`

Recebe e produz efeitos financeiros de impostos e gastos que podem aparecer nos custos das entidades quando aplicável.

### `10 — Imóveis e Zonas`

Pode futuramente permitir análises territoriais de oferta, produção e consumo.

### `22 — Receitas-Produção`

É a fonte de definição dos Produtos, suas receitas e seus usos.

---

# 17.22. Fora do primeiro Bot Test

Ficam fora do primeiro Bot Test, salvo decisão posterior:

- filtros públicos por bairro, cidade ou Estado;
- ranking detalhado de compradores e vendedores;
- histórico público de cada transação individual;
- previsão automática de preços futuros;
- análise econômica avançada baseada em causalidade estatística;
- painéis econômicos territoriais completos;
- integração internacional/exportação.

Essas extensões podem utilizar a mesma base histórica futuramente.

---

# 17.23. Bot Test

O Bot Test deve verificar, no mínimo:

### Estatísticas de Produto

- cálculo correto de preço médio ponderado;
- menor e maior preço baseados apenas em transações concluídas;
- cálculo correto de estoque disponível;
- produção real das últimas 24 horas;
- consumo real das últimas 24 horas;
- tendência de 7 dias contra os 7 dias anteriores;
- ausência de dados quando não houver histórico suficiente.

### Gráficos

- geração correta da série de 30 dias;
- consistência entre gráficos e agregados;
- comportamento correto quando um período não possui dados.

### Transparência empresarial

- cálculo da variação dos custos;
- identificação da principal contribuição;
- separação correta das categorias de custo;
- consistência entre os custos registrados e a explicação mostrada ao jogador.

### Histórico

- armazenamento completo das transações;
- integridade de quantidade, preço, valor total, comprador, vendedor e timestamp;
- geração correta dos agregados;
- consulta pública utilizando agregados em vez do histórico bruto completo.

### Performance

- teste do crescimento do histórico de transações;
- teste das consultas das páginas de Mercado e Produto;
- verificação de que o cálculo dos indicadores não degrada com o crescimento dos dados.

---

# 17.24. Princípios de design

1. **Informação útil:** mostrar ao jogador aquilo que ajuda a tomar decisões econômicas.
2. **Dados reais:** estatísticas de mercado devem partir de transações e usos efetivamente ocorridos.
3. **Transparência agregada:** o jogador recebe visão econômica sem ser obrigado a interpretar cada transação individual.
4. **Explicabilidade:** empresas devem conseguir entender quais componentes estão pressionando seus custos.
5. **Histórico completo:** o servidor mantém dados suficientes para auditoria e análise futura.
6. **Desempenho:** páginas públicas utilizam agregados sempre que possível.
7. **Extensibilidade:** o histórico deve permitir futuramente análises territoriais e comércio internacional sem redesenho estrutural.
