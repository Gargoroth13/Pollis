# 11 — Leis Paramétricas

> **Consolidação P0.01 (2026-10-14).** Decisões aprovadas do Game Director registradas em `CHANGELOG_DEV.md` ("P0.01 — consolidação documental"). Este documento permanece em **REVIEW** por dependências posteriores: o teto de déficit público ainda não tem proposta (após P0.07a) e a mecânica de zoneamento por lei depende da P1.07. Itens `[ABERTO]` não devem ser implementados.

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
| Teto salarial (`T`) | Federal | R$ máximo por dia de remuneração | R$ 50 | Sem limite político; limitado apenas pelo valor monetário técnico do sistema | Sem teto | Impede remuneração acima do valor legal | Pode impedir empresas de pagar remunerações compatíveis com jogadores de Skill elevada |

### 11.1.0. Teto salarial e limite diário de recebimento

Esta é a **definição única** do limite diário de remuneração. Nenhum sistema pode implementar interpretação própria (`01 — Skills` §1.7 remete a esta seção).

Definições:

- `W` = salário mínimo vigente;
- `S` = limite pessoal por habilidade = `1.5 × skill relevante` (parâmetro `[PROV]` em `skills/balance.py`; Inteligência/Físico/Carisma conforme o trabalho, **Físico** para militares);
- `T` = teto salarial legal (`T = ∞` quando não há teto legal).

Validações de proposta de `T`:

- `T < W` é **inválido**;
- `T` menor que o **maior salário político vigente** é **inválido** (coerência, não limite adicional).

**Dois contadores diários separados**, por jogador:

| Contador | Conta | Limite |
|---|---|---|
| `C_S` | remunerações de trabalho, soldo e salário do cargo Dono, sujeitos ao limite por habilidade | `max(W, S)` |
| `C_T` | **toda** remuneração salarial sujeita ao teto legal: a de `C_S` **mais** os salários políticos | `T` |

- Salário político **não consome `S`**, mas **consome `T`**.
- **Não consomem nenhum dos dois:** doações, vendas, reembolsos, transferências, dotações, indenizações e recebimento de dívidas. (Lucros e distribuições também não consomem, mas não existem no primeiro Bot Test.) O registro monetário (P0.07) precisa de uma **natureza** em cada lançamento para distinguir.
- O teto `T` vale para o **total diário** do jogador, não isoladamente por empregador ou sistema de pagamento.

**Cálculo determinístico e independente da ordem dos serviços.** A remuneração política prevista em lei é **preservada até o limite legal** e a não política se ajusta ao que sobra:

```text
P_dia      = remuneração política devida no dia (0 se não ocupa cargo)
cap_S      = max(W, S)
sobra_S    = cap_S − C_S
sobra_T    = T − C_T − (P_dia ainda não lançada em C_T)      # T = ∞ → sem limite
pago_não_político = max(0, min(devido, sobra_S, sobra_T))
```

- A parcela política do dia é **reservada** em `sobra_T` desde o início do dia, de modo que o resultado para a remuneração não política **não depende da ordem** em que os serviços executam os pagamentos.
- Entre remunerações não políticas do mesmo jogador, vale a ordem do registro monetário (sequência do lançamento; desempate por identificador da obrigação).
- Sem remuneração política, a fórmula equivale a `recebível/dia = max(W, min(S, T))`, pois `T ≥ W`.
- O piso `W` prevalece sobre um limite por habilidade inferior (`cap_S = max(W, S)`), mas **não cria dinheiro** e **não permite ultrapassar `T`**.
- **Soldo militar:** `devido = W × m_patente`, aplicando o limite por Físico (`S`) e a capacidade restante de `T` pela mesma fórmula. O excedente acima do recebível **não é pago e não vira obrigação pendente**.
- **Multiplicadores de patente** (parâmetros fixos do sistema, **não leis**, `[PROV]` e calibráveis): Militar 1×, Capitão 2×, General 4×, Marechal 6×. Não há validação automática de que uma patente fique abaixo de um cargo político, pois a correspondência entre patentes e cargos não está definida e os multiplicadores políticos mudam por lei.
- **Dia de competência** `[interpretação técnica, a detalhar no P0.07a]`: cada remuneração conta no contador do dia em que foi devida (competência), e não do dia em que uma obrigação pendente venha a ser paga.

### 11.1.0.1. Travamento de acoplamento

Estendendo a regra de `07 — Leis` (07.17), o grupo de parâmetros

> `{W, T, multiplicador Presidente, multiplicador Governador, multiplicador Prefeito, multiplicador Deputado}`

tem **travamento de acoplamento explícito e determinístico**: não pode haver duas propostas ativas/em trânsito sobre parâmetros do grupo ao mesmo tempo, porque a validade de uma depende do valor das outras.

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

**Base de cálculo (decisão do Game Director).** O piso incide sobre as **receitas recebidas pelo Município no período de 30 dias** (arrecadação própria + transferências efetivamente recebidas). A verificação ocorre na **confirmação da distribuição do orçamento**, e o resultado é explicado por `Explained` (`20`).

- Nesta fase os pisos se aplicam **apenas ao orçamento municipal**.
- União e Estados **não possuem pisos setoriais** até a arquitetura definir a distribuição por categoria.
- A mesma base de 30 dias vale para os **três** pisos (Educação, Saúde e Infraestrutura). O piso constitucional de Educação é 5%; Saúde e Infraestrutura mantêm os mínimos legais deste catálogo.

**Teto de déficit público: `[ABERTO]`.** Depende de registro monetário, obrigações e dívida (P0.07a). Uma proposta de teto de déficit será apresentada depois da arquitetura monetária. O parâmetro permanece no catálogo, mas **não deve ser implementado** antes disso.

### 11.2.2. Infraestrutura

Infraestrutura representa o orçamento destinado a **obras e construções públicas físicas** que não são despesas de funcionamento cotidiano de Educação ou Saúde.

No modelo inicial, a construção física de uma escola, universidade ou hospital é um projeto público de construção e utiliza recursos de Infraestrutura. Depois de construído, o funcionamento da instituição utiliza o orçamento correspondente à sua área, como Educação ou Saúde.

A definição detalhada de quais projetos existem permanece em `09 — Orçamento Público` e `10 — Imóveis e Zonas`.

### 11.2.3. Fórmula salarial dos cargos políticos

A remuneração é calculada por:

```text
salário do cargo = salário mínimo nacional × multiplicador do cargo
```

Pagadores: **União** paga Presidente e Deputados; **Estado** paga o Governador; **Município** paga o Prefeito. O salário acumula diariamente; sem caixa, vira **obrigação pendente** (sem saldo negativo e sem criação de dinheiro); o substituto acumula a partir da sua posse. Ver 11.1.0 para a relação com o teto salarial `T`.

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
| Carisma mínimo para candidatura (parâmetro **único** para todos os cargos) | Federal | Carisma mínimo | 0 | 100 | 10 | Define o requisito geral de Carisma para candidatura |
| Experiência mínima para Governador | Federal | Número de mandatos de Prefeito previamente **concluídos** | 1 | 10 | 1 | Define a experiência política necessária para Governador |
| Experiência mínima para Presidente | Federal | Número de mandatos de Governador previamente **concluídos** | 1 | 10 | 1 | Define a experiência política necessária para Presidente |
| Limite de mandatos consecutivos | Federal | Número máximo de mandatos consecutivos no mesmo cargo | 1 | 10 | 2 | Controla quantos mandatos o jogador pode ocupar consecutivamente no mesmo cargo |
| Duração do mandato — Prefeito | Federal | Meses | 2 | 8 | 4 | Define duração do mandato |
| Duração do mandato — Governador | Federal | Meses | 2 | 8 | 6 | Define duração do mandato |
| Duração do mandato — Presidente | Federal | Meses | 2 | 8 | 6 | Define duração do mandato |
| Duração do mandato — Deputado | Federal | Meses | 2 | 8 | 6 | Define duração do mandato |

### 11.4.1. Diploma presidencial

A exigência de diploma para Presidente é **fixa** e não é uma lei paramétrica.

O candidato a Presidente deve possuir diploma de Engenharia, Direito ou Medicina, conforme `06 — Política`.

### 11.4.2. Experiência política

"Exercer" um cargo significa **posse efetiva + conclusão de um mandato estatutário completo** (`06 — Política` 06.3). O padrão exige:

- Governador: pelo menos 1 mandato concluído como Prefeito.
- Presidente: pelo menos 1 mandato concluído como Governador.

Renúncia, AFK, deposição e serviço parcial como substituto não geram crédito ordinário; o cenário de teste pode conceder crédito explícito a contas designadas. Os valores podem ser alterados por lei dentro dos limites do catálogo.

### 11.4.3. Mandatos consecutivos e mandatos concluídos

São dois contadores distintos:

- **mandatos consecutivos** (limite acima): conta todo mandato com posse, inclusive o mandato obtido por deposição;
- **mandatos concluídos** (experiência): conta somente mandatos estatutários completos; mandato por deposição não gera experiência.

**Mudanças de lei:** alterações de duração de mandato, requisitos de elegibilidade e limite de mandatos consecutivos afetam apenas eleições cuja janela de inscrição se abre **após a vigência** da mudança, sem retroatividade. Salários e parâmetros fiscais valem no tick efetivo previsto pelo processo legislativo.

---

# 11.5. Constituição e regras protegidas

A Constituição está acima das leis ordinárias. Leis comuns não podem reduzir ou eliminar as garantias protegidas.

## 11.5.1. Educação

A Educação possui um piso constitucional de **5%**, calculado sobre a base definida em 11.2.1 (receitas recebidas pelo Município em 30 dias).

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

Somente o **Presidente** e os **Deputados** formalizam projetos temporários, conforme `07 — Leis` (o `07` prevalece). **Governadores e Prefeitos podem sugerir** projetos ao Presidente, que decide se os adota.

A área escolhida para o projeto respeita a jurisdição administrativa do cargo:

| Cargo | Alcance disponível |
|---|---|
| Presidente | Estados do país |
| Deputado | Alcance nacional |

Sugestões de Prefeitos e Governadores usam o alcance de sua jurisdição (bairros da própria cidade; cidades do próprio Estado) como indicação ao Presidente, mas somente o Presidente ou um Deputado formaliza a proposta no processo legislativo federal (`07 — Leis`). A competência territorial não transforma o projeto em lei municipal ou estadual.

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

**Campanhas (aprovado):**

- unidade territorial de campanha de Deputado: **Estado**;
- conflito entre campanhas: **mesmo tipo, mesmo território e períodos sobrepostos**;
- a **reserva financeira** ocorre quando a campanha **entra em vigor**; sem saldo disponível para a reserva integral, a campanha **não entra em operação**;
- o custo sai do **caixa federal** e tem destino final no **sumidouro explícito** do registro monetário (conta contábil identificada, indisponível para gastos normais, excluída do dinheiro em circulação);
- as "categorias" do subsídio setorial derivam do catálogo e de suas permissões (integração na P0.02).

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
- imposto sobre lucro (ver `09 — Orçamento Público`);
- leis municipais e mudança de uso do zoneamento por lei (a mecânica de zoneamento ainda será definida em P1.07; não existem leis municipais no primeiro Bot Test);
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
