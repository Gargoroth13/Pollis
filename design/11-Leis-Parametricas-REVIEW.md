# 11 — Leis Paramétricas

**Status: REVIEW**

## 11.0. Função do catálogo

Este documento define o catálogo de regras políticas que podem ser alteradas por meio do sistema legislativo de `07 — Leis`.

Uma lei paramétrica possui um parâmetro **X** que o proponente escolhe dentro dos limites definidos pelo catálogo.

Cada lei possui:

| Campo | Função |
|---|---|
| Parâmetro X | Valor escolhido na proposta |
| Mínimo | Menor valor permitido |
| Máximo | Maior valor permitido |
| Padrão | Valor utilizado no início do jogo |

Os valores mínimo e máximo são limites de design/técnicos. O jogador escolhe livremente qualquer valor válido dentro desse intervalo.

As leis deste catálogo são submetidas ao processo legislativo completo definido em `07 — Leis`.

---

# 11.1. Econômico e empresarial

| Lei | Escopo | Parâmetro X | Mín. | Máx. | Padrão | Efeito | Trade-off |
|---|---|---|---:|---:|---:|---|---|
| Imposto sobre vendas | Federal | % sobre o valor de cada venda | 0% | 50% | 5% | Gera receita para o orçamento público | Aumenta o custo efetivo das transações e pode reduzir margens e elevar preços |
| Imposto de renda | Federal | % sobre salários pagos | 0% | 50% | 5% | Gera receita para o orçamento público | Reduz o salário líquido recebido |
| Salário mínimo | Federal | R$ por dia | R$ 0 | R$ 1.000 | R$ 50 | Define o piso legal de remuneração do trabalho | Pode aumentar custo das empresas e reduzir contratação quando elevado demais |
| Regulação antitruste | Federal | Máximo de empresas do mesmo tipo por proprietário | 1 | 100 | 1 | Limita concentração de empresas do mesmo tipo por jogador/entidade | Restringe expansão de proprietários eficientes |
| Subsídio setorial | Federal | % do valor pago pelo governo em vendas elegíveis | 0% | 75% | 0% | O governo paga parte do valor de produtos ou categorias selecionadas | Exige gasto público e pode distorcer preços/produção |
| Teto de preço de produto | Federal | Preço máximo de venda de um Produto específico | R$ 0 | Limite monetário técnico do sistema | Sem teto | Impede venda do produto selecionado acima do valor definido | Pode reduzir margem e oferta se ficar abaixo do custo/preço de equilíbrio |
| Teto salarial | Federal | R$ máximo por dia de remuneração | R$ 50 | Sem limite político; limitado apenas pelo valor monetário técnico do sistema | Sem teto | Impede remuneração acima do valor legal | Pode impedir empresas de pagar remunerações compatíveis com jogadores de Skill elevada |

### 11.1.1. Teto de preço

O teto de preço referencia diretamente um Produto do catálogo de `22 — Receitas-Produção`.

O parâmetro X é um valor monetário livre. Não existe um teto político fixo de balanceamento para X; o único limite superior é o limite técnico utilizado pelo sistema monetário para representar valores.

Uma proposta não pode definir preço negativo.

---

# 11.2. Fiscal e orçamentário

| Lei | Escopo | Parâmetro X | Mín. | Máx. | Padrão | Efeito | Trade-off |
|---|---|---|---:|---:|---:|---|---|
| Piso de orçamento — Educação | Federal | % mínimo do orçamento destinado à Educação | 5% | 30% | 10% | Garante recurso mínimo para Educação | Reduz a parcela livre do orçamento para outras áreas |
| Piso de orçamento — Saúde | Federal | % mínimo do orçamento destinado à Saúde | 1% | 30% | 10% | Garante recurso mínimo para Saúde | Reduz a parcela livre do orçamento para outras áreas |
| Piso de orçamento — Infraestrutura | Federal | % mínimo do orçamento destinado à Infraestrutura | 1% | 30% | 10% | Garante recurso mínimo para obras e construções públicas | Reduz a parcela livre do orçamento para outras áreas |
| Teto de déficit público | Federal | Déficit máximo permitido como % da receita anual de referência | 0% | 50% | 10% | Limita quanto o governo pode operar em déficit | Pode impedir gastos em situações nas quais o governo gostaria de assumir maior déficit |
| Multiplicador salarial — Presidente | Federal | Multiplicador do salário mínimo | 1× | 50× | 10× | Define remuneração do Presidente | Aumenta gasto público obrigatório quando elevado |
| Multiplicador salarial — Governador | Federal | Multiplicador do salário mínimo | 1× | 40× | 8× | Define remuneração do Governador | Aumenta gasto público obrigatório quando elevado |
| Multiplicador salarial — Prefeito | Federal | Multiplicador do salário mínimo | 1× | 35× | 7× | Define remuneração do Prefeito | Aumenta gasto público obrigatório quando elevado |
| Multiplicador salarial — Deputado | Federal | Multiplicador do salário mínimo | 1× | 35× | 7× | Define remuneração do Deputado | Aumenta gasto público obrigatório quando elevado |

### 11.2.1. Pisos orçamentários

Os pisos de Educação, Saúde e Infraestrutura são mínimos legais. O Executivo continua podendo destinar mais recursos à área, desde que respeite todas as demais regras orçamentárias.

A soma dos pisos legais não pode ultrapassar 100% do orçamento.

### 11.2.2. Infraestrutura

Infraestrutura representa o orçamento destinado a **obras e construções públicas físicas** que não são despesas de funcionamento cotidiano de Educação ou Saúde.

No modelo inicial, a construção física de uma escola, universidade ou hospital é um projeto público de construção e utiliza recursos de Infraestrutura. Depois de construído, o funcionamento da instituição utiliza o orçamento correspondente à sua área, como Educação ou Saúde.

A definição detalhada de quais projetos existem permanece em `09 — Orçamento Público` e `10 — Imóveis e Zonas`.

### 11.2.3. Fórmula salarial dos cargos políticos

A remuneração é calculada por:

```text
salário do cargo = salário mínimo nacional × multiplicador do cargo
```

---

# 11.3. Imobiliário

| Lei | Escopo | Parâmetro X | Mín. | Máx. | Padrão | Efeito | Trade-off |
|---|---|---|---:|---:|---:|---|---|
| IPTU | Federal, aplicado à propriedade municipal | % do valor do imóvel por ano | 0% | 50% | 1% | Gera receita pública sobre imóveis | Aumenta o custo de manter imóveis |
| Teto de posse de imóveis — jogador | Federal | Número máximo de imóveis por jogador | 1 | 50 | 10 | Limita concentração de propriedades por jogador | Restringe investimento e oferta potencial de aluguel |
| Teto de posse de imóveis — empresa | Federal | Número máximo de imóveis por empresa | 1 | 50 | 10 | Limita concentração de propriedades por empresa | Restringe expansão imobiliária empresarial |
| Controle de aluguel | Federal | % máximo de reajuste de aluguel por período de reajuste | 0% | 30% | 10% | Limita aumentos de contratos existentes | Pode reduzir incentivo para manter imóveis destinados a aluguel |

O teto de posse é separado para jogadores e empresas.

O controle de aluguel regula reajustes de contratos existentes. Não determina automaticamente o preço inicial de um novo contrato.

---

# 11.4. Eleitoral e cargos públicos

| Lei | Escopo | Parâmetro X | Mín. | Máx. | Padrão | Efeito |
|---|---|---|---:|---:|---:|---|
| Idade mínima da conta para candidatura | Federal | Dias desde criação da conta | 30 | 300 | 90 | Define há quanto tempo a conta deve existir para candidatura |
| Carisma mínimo para candidatura | Federal | Carisma mínimo | 0 | 100 | 10 | Define o requisito geral de Carisma para candidatura |
| Experiência mínima para Governador | Federal | Número de cargos de Prefeito previamente exercidos | 1 | 10 | 1 | Define a experiência política necessária para Governador |
| Experiência mínima para Presidente | Federal | Número de cargos de Governador previamente exercidos | 1 | 10 | 1 | Define a experiência política necessária para Presidente |
| Limite de reeleições consecutivas | Federal | Número de reeleições permitidas consecutivamente | 1 | 10 | 2 | Controla quantas vezes o jogador pode permanecer consecutivamente no mesmo cargo |
| Duração do mandato — Prefeito | Federal | Meses | 2 | 8 | 4 | Define duração do mandato |
| Duração do mandato — Governador | Federal | Meses | 2 | 8 | 6 | Define duração do mandato |
| Duração do mandato — Presidente | Federal | Meses | 2 | 8 | 6 | Define duração do mandato |
| Duração do mandato — Deputado | Federal | Meses | 2 | 8 | 6 | Define duração do mandato |

### 11.4.1. Diploma presidencial

A exigência de diploma para Presidente é **fixa** e não é uma lei paramétrica.

O candidato a Presidente deve possuir diploma de Engenharia, Direito ou Medicina, conforme `06 — Política`.

### 11.4.2. Experiência política

O padrão exige uma passagem anterior pelo cargo correspondente:

- Governador: pelo menos 1 exercício anterior como Prefeito.
- Presidente: pelo menos 1 exercício anterior como Governador.

Os valores podem ser alterados por lei dentro dos limites do catálogo.

---

# 11.5. Constituição e regras protegidas

A Constituição está acima das leis ordinárias. Leis comuns não podem reduzir ou eliminar as garantias protegidas.

## 11.5.1. Educação

A Educação possui um piso constitucional de **5% do orçamento**.

Por isso, a lei paramétrica de Piso de orçamento — Educação possui mínimo de 5% e não pode ser alterada abaixo desse valor por lei ordinária.

O percentual acima do piso continua sendo decisão política dentro dos limites legais.

## 11.5.2. Moradia

Todo jogador inicia o jogo com acesso a um **apartamento padrão** fornecido como garantia constitucional de moradia.

O apartamento padrão:

- não possui bônus ou penalidade de QoL;
- é neutro em relação às demais características de imóveis;
- não possui custo de aquisição ou manutenção;
- não conta para a capacidade populacional da cidade;
- não pode ser utilizado para criar população artificial por meio de múltiplas contas;
- funciona como residência inicial básica do jogador.

A garantia é sistêmica e não depende de uma lei ordinária para existir.

---

# 11.6. Projetos temporários e campanhas

Projetos temporários e campanhas são **pautas políticas temporárias**. Eles utilizam o mesmo processo político de uma lei:

1. proposta;
2. discussão;
3. votação da Câmara por 3 dias;
4. sanção ou veto presidencial;
5. derrubada de veto pela Câmara quando aplicável;
6. entrada em vigor na próxima weekly tick.

A diferença é que o projeto possui duração definida e expira automaticamente ao final do período.

### 11.6.1. Quem pode propor

Qualquer ocupante de cargo político pode apresentar um projeto temporário.

A área escolhida para o projeto respeita a jurisdição administrativa do cargo:

| Cargo | Alcance disponível |
|---|---|
| Prefeito | Bairros da própria cidade |
| Governador | Cidades do próprio Estado |
| Presidente | Estados do país |
| Deputado | Alcance nacional |

Prefeitos, Governadores e Deputados encaminham a proposta pelo processo legislativo federal conforme as regras de `07 — Leis`. A competência territorial não transforma o projeto em lei municipal ou estadual.

### 11.6.2. Campanhas disponíveis no Bot Test

| Projeto | Parâmetro X | Mín. | Máx. | Padrão | Efeito |
|---|---|---:|---:|---:|---|
| Boom de investimento setorial | % de aumento de produção/fabricação | 5% | 100% | 10% | Aumenta temporariamente a produção das empresas elegíveis no território |
| Campanha educacional | % de aumento de qualidade de ensino | 5% | 100% | 10% | Aumenta temporariamente a qualidade das escolas e universidades elegíveis |
| Campanha de saúde pública | % de redução do tempo de internação | 5% | 100% | 10% | Reduz temporariamente o tempo de internação nas instituições elegíveis |

As campanhas podem selecionar o alcance territorial permitido pelo cargo proponente.

### 11.6.3. Duração

| Parâmetro | Mín. | Máx. | Padrão |
|---|---:|---:|---:|
| Duração do projeto | 7 dias | 90 dias | 7 dias |

Quanto maior a duração, maior o custo total do projeto.

### 11.6.4. Custo

O custo base segue a estrutura:

```text
custo = custo_base_por_unidade × número_de_unidades × (duração_em_dias / 30)
```

O custo-base inicial é de **R$ 10.000 por unidade territorial a cada 30 dias**.

O alcance depende da jurisdição do proponente.

### 11.6.5. Custo da intensidade

O custo cresce de forma não linear conforme o percentual de efeito X aumenta.

Para a primeira versão, a intensidade utiliza um fator exponencial simples:

```text
fator_intensidade = 2 ^ (X / 50)
```

O custo final é:

```text
custo_final = custo_base_por_unidade × número_de_unidades × (duração_em_dias / 30) × fator_intensidade
```

O objetivo é tornar campanhas de intensidade muito alta significativamente mais caras sem criar um novo recurso ou sistema.

### 11.6.6. Repetição

Depois de expirado, um projeto pode ser proposto novamente pelo processo político normal, desde que suas regras de conflito e orçamento sejam respeitadas.

---

# 11.7. Fora do primeiro Bot Test

As seguintes possibilidades ficam fora do catálogo operacional do primeiro Bot Test para evitar que o sistema legislativo exija mecânicas ainda não definidas:

- reserva obrigatória da Financeira;
- teto de juros de cartão de crédito;
- fiscalização trabalhista de EPI/uniforme;
- vale-transporte obrigatório;
- incentivo a P&D tecnológico;
- estoque mínimo de emergência para varejo;
- resgate emergencial de empresas;
- programas de bolsa de educação;
- programa de saúde pública individualizado;
- taxa ou incentivo de migração;
- regras políticas avançadas de leilões;
- regras ambientais de extração;
- mudanças estruturais do sistema eleitoral.

Essas ideias podem ser reavaliadas depois do Bot Test quando os sistemas correspondentes existirem.

---

# 11.8. Princípios do catálogo

1. Toda lei paramétrica possui X, mínimo, máximo e padrão.
2. O jogador pode escolher qualquer X válido dentro dos limites.
3. Leis que alteram sistemas inexistentes não entram no Bot Test.
4. Regras estruturais que já pertencem ao sistema base não são duplicadas como leis paramétricas.
5. Projetos temporários passam pelo mesmo processo político das leis, mas possuem expiração automática.
6. Constituição permanece acima das leis ordinárias.
7. O catálogo é a fonte de quais parâmetros políticos podem ser alterados; jogadores não criam novos tipos de lei livremente.
