# Polis — Documento de Design

## Índice

- [0. Filosofia do jogo](#0-filosofia-do-jogo)
- [1. Skills do jogador (revisão grande)](#1-skills-do-jogador-revisão-grande)
  - [1.1 Como cada skill cresce](#11-como-cada-skill-cresce)
  - [1.2 Fórmula de ganho de skill](#12-fórmula-de-ganho-de-skill-você-confirmou-com-exemplos)
  - [1.3 Skills afetam produção e salário](#13-skills-afetam-produção-e-salário)
  - [1.4 Diminishing returns](#14-diminishing-returns-proposta-você-pediu-o-conceito-sem-fórmula)
- [2. Empresas](#2-empresas)
  - [2.1 Tipos gerais](#21-tipos-gerais)
  - [2.2 Matriz](#22-matriz-definida-por-terreno-não-por-skill)
  - [2.3 Industrial](#23-industrial-4-sub-tipos-cada-um-com-suas-receitas)
  - [2.4 Consumo operacional (mecânica nova)](#24-consumo-operacional-mecânica-nova)
  - [2.5 Varejo](#25-varejo)
  - [2.6 Construtora](#26-construtora-revisão)
  - [2.7 Serviços](#27-serviços-especializações-revisadas)
  - [2.8 Financeira](#28-financeira-detalhamento-da-especialização)
  - [2.9 Produção passa a ser dos funcionários, não só do dono](#29-produção-passa-a-ser-dos-funcionários-não-só-do-dono-mudança-grande)
  - [2.10 Estrelas](#210-estrelas-mantém)
  - [2.11 Especialização de funcionário](#211-especialização-de-funcionário-novo)
  - [2.12 Qualidade afeta preço e preferência do consumidor](#212-qualidade-afeta-preço-e-preferência-do-consumidor-novo)
- [3. Escolas e universidades](#3-escolas-e-universidades)
- [4. Diploma e admissão universitária](#4-diploma-e-admissão-universitária-fórmulas-precisas)
- [5. Dia a dia do jogador](#5-dia-a-dia-do-jogador-revisão-completa)
  - [5.1 Ações e custo de energia](#51-ações-e-custo-de-energia)
  - [5.2 QoL](#52-qol-como-funciona-de-verdade)
  - [5.3 Saúde](#53-saúde)
  - [5.4 Nutrição (esse é o nome que você usou, substitui minha sugestão de "Saciedade")](#54-nutrição-esse-é-o-nome-que-você-usou-substitui-minha-sugestão-de-saciedade)
  - [5.5 Viajar](#55-viajar)
- [6. Inventário do jogador (sistema novo, ainda não existe)](#6-inventário-do-jogador-sistema-novo-ainda-não-existe)
- [7. Política e QoL](#7-política-e-qol-efeito-da-população-da-cidade)
  - [7.1 Trade-offs explícitos nas decisões políticas](#71-trade-offs-explícitos-nas-decisões-políticas-novo)
  - [7.2 População dinâmica (jogadores + NPCs)](#72-população-dinâmica-jogadores-npcs-novo-versão-enxuta-pra-não-travar-tudo)
- [8. Cargos políticos](#8-cargos-políticos-números-completos)
  - [8.1 Executivo](#81-executivo)
  - [8.2 Legislativo](#82-legislativo)
  - [8.3 Judiciário e fiscalização](#83-judiciário-e-fiscalização)
- [9. Orçamento público](#9-orçamento-público-sistema-novo-pré-requisito-pros-trade-offs-de-lei)
- [10. Imóveis e zonas](#10-imóveis-e-zonas-mantém-com-um-ajuste)
  - [10.1 Imóveis residenciais em detalhe](#101-imóveis-residenciais-em-detalhe-faltava-proposta)
- [11. Catálogo de leis paramétricas](#11-catálogo-de-leis-paramétricas)
  - [11.1 Econômico e empresarial](#111-econômico-e-empresarial)
  - [11.2 Trabalhista](#112-trabalhista)
  - [11.3 Fiscal e orçamentário](#113-fiscal-e-orçamentário)
  - [11.4 Imobiliário e zoneamento](#114-imobiliário-e-zoneamento)
  - [11.5 Social](#115-social)
  - [11.6 Eleitoral e constitucional](#116-eleitoral-e-constitucional)
  - [11.7 Projetos temporários (campanhas)](#117-projetos-temporários-campanhas)
  - [11.8 Ambiental](#118-ambiental-categoria-nova)
- [12. Histórico do mundo (crônica do servidor)](#12-histórico-do-mundo-crônica-do-servidor)
- [13. Sistema de eventos aleatórios](#13-sistema-de-eventos-aleatórios)
- [14. Rankings](#14-rankings)
- [15. Jornal / feed de notícias](#15-jornal-feed-de-notícias)
- [16. Empresas com múltiplos donos (sociedade / ações)](#16-empresas-com-múltiplos-donos-sociedade-ações-mudança-estrutural-grande)
- [17. Transparência de mercado](#17-transparência-de-mercado)
- [18. Contratos entre jogadores](#18-contratos-entre-jogadores)
- [19. Militares e Milícias](#19-militares-e-milícias-sistema-novo-e-grande)
  - [19.1 Exército](#191-exército)
  - [19.2 Milícias](#192-milícias)
  - [19.3 Força e prontidão](#193-força-e-prontidão)
  - [19.4 Regras do confronto](#194-regras-do-confronto)
- [20. Filosofia de feedback ao jogador (UI)](#20-filosofia-de-feedback-ao-jogador-ui)
- [21. Bots para testes de beta](#21-bots-para-testes-de-beta-metodologia-de-teste-não-mecânica-de-jogo)
- [22. Implicações técnicas](#22-implicações-técnicas-o-que-precisa-ser-refeito-no-código)
- [Pendências que ainda restam](#pendências-que-ainda-restam)

---

## 0. Filosofia do jogo

> A ideia do jogo é fazer todas as decisões partirem dos jogadores. Eles
> controlam o mercado, as políticas, os empregos, a qualidade de vida,
> tudo. A função do sistema é apenas dar as ferramentas e prevenir que
> eles quebrem o jogo de forma injusta.

Isso vale como critério de desempate sempre que uma regra nova estiver
em dúvida: dar ferramenta, não travar decisão; e sempre que tiver risco
de exploit (como no caso da Financeira falindo de propósito), o sistema
tem que ter uma trava.

✅ = já implementado. 🤝 = combinado, não implementado ainda. 🆕 =
proposta minha aguardando confirmação. ⚠️ = pendência ou inconsistência
que precisa de uma resposta sua.

---

## 1. Skills do jogador (revisão grande)

**Só existem 3 skills, e elas substituem as 8 categorias antigas
(Indústria, Comércio, Tecnologia etc — essas viram classificação de
empresa, não de jogador, ver seção 2):**

- Inteligência
- Físico
- Carisma

Crescem infinitamente. Nascimento no bairro já define o nível inicial
de cada uma (mantém o que já tínhamos de sorteio por faixa de renda).

### 1.1 Como cada skill cresce

| Fonte | Efeito |
|---|---|
| Trabalhar | Cresce, mas menos que estudar. Cada emprego/cargo específico aumenta **uma** skill só (definida pelo cargo) |
| Estudar (escola/universidade) | Cresce mais que trabalhar |
| Atividades de lazer / grupos de estudo | Também aumenta skill, fora da escola/universidade |

### 1.2 Fórmula de ganho de skill ✅ (você confirmou com exemplos)

```
ganho = QoL_base × qualidade_da_escola × ganho_base
```

Exemplos que você deu (batem com essa fórmula):
- QoL 1, escola qualidade 1 → ganho 1 (nas 3 skills)
- QoL 0.5, escola qualidade 1 → ganho 0.5
- QoL 0.5, escola qualidade 0.5 → ganho 0.25

### 1.3 Skills afetam produção e salário

- Skill relevante do funcionário define **quanto** a empresa produz por
  clique de trabalho (Matriz e Industrial)
- Skill relevante também define o **salário máximo** que o cargo pode
  pagar: `salário máximo = 1.5 × nível da skill`. Exemplo: Físico 100
  numa Matriz de mineração → salário máx. R$ 150
- 🆕 Skill alta também vira **requisito de acesso**, não só
  multiplicador — cargos de gestão dentro da empresa, cargos políticos
  e cargos de pesquisa exigem um nível mínimo pra sequer se candidatar,
  igual ao `nivel_minimo` que já existe nos Cargos normais hoje. Ou
  seja, a mesma mecânica de gate que já implementamos passa a valer
  também pra política e pesquisa, não só emprego comum.

⚠️ **Pendência:** seu exemplo fala em salário *diário* máximo, mas hoje
o `Cargo.salario` é pago por clique de "trabalhar", não por dia. Preciso
que você diga se o teto é por dia (daí precisa somar os ganhos do dia)
ou por clique.

✅ **Resolvido: o teto é por dia**, não por clique. Implementação
proposta: um contador simples (`ganho_hoje` + `data_referência`),
que soma cada pagamento e zera quando o dia muda. Se a soma do dia
ultrapassar o teto, o pagamento daquele clique é cortado no que sobrar
até o limite (não bloqueia o trabalho, só limita o quanto entra).

### 1.4 Diminishing returns 🆕 (proposta, você pediu o conceito sem fórmula)

Skill continua crescendo infinitamente, mas a eficiência de ganho cai a
cada 100 pontos:

```
faixa = nível // 100
multiplicador_de_eficiência = 1 / (1 + faixa × 0.2)
```

| Nível | Multiplicador |
|---|---|
| 0–99 | 1.0x (cheio) |
| 100–199 | 0.83x |
| 200–299 | 0.71x |
| 300–399 | 0.63x |
| 400–499 | 0.56x |

Isso multiplica o `ganho` calculado na fórmula da seção 1.2. Continua
sem teto — só fica cada vez mais caro virar especialista de verdade,
o que empurra o jogador a diversificar em vez de empilhar tudo numa
skill só.

---

## 2. Empresas

### 2.1 Tipos gerais

| Tipo | Vende pro jogador? |
|---|---|
| Matriz | Não — só vende pra Industrial |
| Industrial | Não — só vende pra Varejo/Construtora |
| Varejo | ✅ Sim |
| Construtora | Não — constrói e vende o imóvel pronto |
| Serviços | ✅ Sim (inclui Financeira como especialização, ver 2.7/2.8) |

✅ **Resolvido:** Financeira é especialização de Serviços, não um tipo
próprio — igual Transporte/Publicidade/Lazer. Só ganhou seção grande
(2.8) porque tem muito mais regra que as outras, não porque é estrutura
diferente.

**Confirmado: só Varejo e Serviços vendem direto pro jogador.**

### 2.2 Matriz — definida por terreno, não por skill 🤝

| Terreno | Produz |
|---|---|
| Agropecuária | Trigo, Leite, Cana, Grão de Café, Cacau, Carne, Ovos, Couro, Lã, Fruta |
| Extrativismo | Madeira, Resina, Látex, Óleo natural, Ervas, Areia, Pedra, Químicos, Petróleo, Borracha |
| Mineração | Ferro, Cobre, Sílica, Carvão, Petróleo, Sal, Lítio, Ouro, Prata, Diamante |

✅ **Resolvido:** "Leite" era repetição (fica só uma vez na lista).
Petróleo em Extrativismo *e* Mineração é intencional — duas rotas
diferentes pro mesmo insumo, cada terreno com seu próprio custo/ritmo
de extração a definir depois.

### 2.3 Industrial — 4 sub-tipos, cada um com suas receitas 🤝

**Produção:**

| Produto final | Ingredientes | Estrela mínima |
|---|---|---|
| Cimento | Pedra + Areia | 1★ |
| Aço | Ferro + Carvão | 2★ |
| Tábuas | Madeira | 1★ |
| Vidro | Areia | 2★ |
| Materiais de Construção | Cimento + Aço + Madeira + Vidro | 3★ |
| Plástico | Petróleo | 2★ |
| Combustível | Petróleo | 3★ |
| Fertilizante | Químicos | 2★ |
| Fios de cobre | Cobre | 1★ |
| EPIs | Borracha + Plástico + Aço + Roupas + Calçados | 3★ |
| Materiais escolares | Borracha + Caneta + Móveis + Papel | 3★ |
| Materiais hospitalares | Químicos + Componentes eletrônicos + Plástico + Ervas | 4★ |

**Alimentícia:**

| Produto final | Ingredientes | Estrela mínima |
|---|---|---|
| Farinha | Trigo | 1★ |
| Açúcar | Cana | 1★ |
| Queijo | Leite | 1★ |
| Manteiga | Leite | 2★ |
| Café em pó | Grão de café | 2★ |
| Manteiga de cacau | Cacau | 3★ |
| Carne processada | Carne | 2★ |

**Bens de consumo:**

| Produto final | Ingredientes | Estrela mínima | Nutrição | Efeito de QoL |
|---|---|---|---|---|
| Roupas | Lã | 1★ | — | — |
| Móveis | Tábuas + Aço | 3★ | — | — |
| Papel | Madeira + Sal | 2★ | — | — |
| Caneta | Aço + Químicos | 1★ | — | — |
| Calçado | Couro | 1★ | — | — |
| Uniforme | Roupas + Calçado | 3★ | — | — |
| Pão | Farinha | 1★ | — | — |
| Chocolate | Manteiga de cacau + Açúcar + Leite | 4★ | pouca | pequeno buff |
| Macarrão | Queijo + Farinha + Ovo | 3★ | bastante | sem efeito |
| Hambúrguer | Queijo + Carne processada + Pão | 4★ | média | pequeno buff |
| Suco | Fruta + Açúcar | 2★ | quase nada | pequeno buff |
| Sorvete | Leite + Açúcar + Fruta | 3★ | nada | buff médio |
| Carne de Sol | Carne + Sal | 1★ | média | **debuff** |
| Refrigerante | Açúcar + Suco + Químicos | 2★ | nada | buff médio |
| Carro | Aço + Plástico + Bateria + Borracha + Químico | 5★ | — | — |

🆕 **Todas as receitas agora têm estrela mínima, não só o Carro** — o
campo `estrela_minima` na `Receita` (proposto na rodada anterior) vira
regra geral do catálogo, não exceção. Isso cria uma progressão natural:
empresa 1★ só faz o básico, e o motivo real de upar de estrela deixa de
ser só "mais cargos" e passa a ser "desbloqueio de receita".

⚠️ **Implicação técnica que essa receita expõe:** Aço e Plástico vêm do
tipo Produção, Bateria vem do tipo Tecnológica — ou seja, pra fabricar
Carro (tipo Bens de Consumo), a Industrial precisa comprar produto
manufaturado de **outra Industrial**, não só matéria-prima de Matriz.
Hoje `REGRAS_DE_COMPRA` só permite Industrial comprar de Matriz — vai
precisar de uma regra nova de Industrial comprando de Industrial
(provavelmente sem restrição de tipo, já que Bens de Consumo precisa
de Produção e Tecnológica ao mesmo tempo).

**Tecnológica:**

| Produto final | Ingredientes | Estrela mínima |
|---|---|---|
| Componentes eletrônicos | Fios de cobre + Sílica + Ouro | 1★ |
| Bateria | Cobre + Lítio + Químicos | 2★ |
| Celular | Componentes eletrônicos + Plástico + Bateria | 3★ |
| Computador | Componentes eletrônicos + Plástico + Aço + Químicos | 4★ |

⚠️ Nosso `Receita` no código já suporta múltiplos ingredientes por
produto (fiz assim de propósito lá atrás), então estruturalmente isso
encaixa sem redesenhar o modelo — é "só" MUITO dado de seed pra digitar.

### 2.4 Consumo operacional (mecânica nova) 🤝

Empresas e instituições agora **consomem** produtos continuamente pra
funcionar, não só o jogador:

| Quem consome | Consome |
|---|---|
| Escolas/Universidades | Uniformes + Materiais escolares |
| Hospitais | Uniformes + Materiais hospitalares |
| Matriz e Industrial | EPIs + Uniformes (gasto por funcionário a cada trabalho) |
| Varejo e Serviços | Uniformes |

Isso dá utilidade real pra praticamente todo mundo da cadeia de Bens de
Consumo, não só o jogador final.

### 2.5 Varejo 🤝

- Nível de estrela define **qual imóvel comercial** ela pode ocupar (liga com a seção 9)
- Compra de Industrial, revende pro jogador ✅ (já implementado, falta o vínculo com imóvel)
- Carros também são vendidos por Varejo, igual qualquer outro bem de consumo — sem loja/tipo de imóvel exclusivo pra veículo

🆕 **Capacidade de estoque limitada por funcionário.** Não é só Matriz e
Industrial que ficam travados pelo número de funcionários trabalhando —
Varejo também: ela só consegue **comprar/movimentar** uma certa
quantidade de estoque por período, proporcional a quantos funcionários
estão ativos. Isso cria escassez de verdade na ponta final também, não
só na produção — obriga a fazer acordo com fornecedores específicos ou
correr atrás de quem tiver estoque disponível no momento, em vez de
"comprar quanto quiser, quando quiser". A fórmula exata (quantidade
máxima por funcionário por período) fica pra quando formos implementar.

### 2.6 Construtora — revisão 🤝

Pra terminar um imóvel pronto pra venda, precisa comprar **dois**
produtos da Industrial: Materiais de Construção (ergue a estrutura) e
Móveis (finaliza/mobilia). Isso substitui minha simplificação anterior
de "só Cimento".

### 2.7 Serviços — especializações revisadas

| Especialização | Status | Regra |
|---|---|---|
| Transporte | 🤝 | Vende ticket de uso único, pequeno buff de QoL, limite **2 por dia por jogador**. Não funciona se o jogador tiver veículo próprio — **exceto** se a empresa de transporte for 5 estrelas. ⏸️ Veículo próprio ainda não tem sistema nenhum (compra, posse, manutenção) — decidido deixar essa exceção sem efeito prático até existir um sistema de veículos, sem travar Transporte por causa disso |
| ~~Segurança~~ | ❌ removida por você | Motivo: você queria uma forma dos jogadores poderem perder itens (pra "comprou não é pra sempre"), mas achou que tem jeito melhor de fazer isso. Fica em aberto pro futuro, fora do sistema de Serviços |
| Publicidade | 🤝 | Anúncio em páginas específicas do site; quanto mais paga, maior a chance de aparecer; preço escala com o tráfego da página |
| Lazer | 🤝 | Buff temporário de QoL, varia de acordo com o imóvel Especial onde a empresa está |
| Financeira | 🤝 | Ver seção 2.8 — é especialização de Serviços igual as outras, só ganhou seção própria pelo tanto de regra que tem |

### 2.8 Financeira — detalhamento da especialização 🤝

- **Empréstimos** pros jogadores
- **Bolsa de valores e poupança**: acesso mediante taxa mensal; poupança paga juros semanais sobre o valor depositado
- **Cartão de crédito**: limite rotativo, jogador escolhe pagar tudo ou o mínimo. Se ficar em dívida, é **preso** e seus bens são vendidos pra quitar a dívida
- **Transferência entre jogadores**: taxa menor que a de outros métodos, paga só pra empresa financeira
- **Falência**: se a Financeira quebra, o dono fica em dívida; jogadores com dinheiro depositado recebem uma "promessa de recompensa" — o valor volta em 1 mês, mas com perda de 30%

🆕 **Controles de solvência adicionais** (sua ideia nova, evita que
"promessa de recompensa com 30% de perda" seja a única salvaguarda):

- **Reserva obrigatória**: a Financeira precisa manter um % fixo do
  total depositado pelos clientes em caixa, sem poder emprestar tudo.
  ✅ Fechado em **20%**.
- **Rating de solvência público**: score visível pra todo mundo (ex:
  A/B/C/D/F), calculado a partir da razão entre reserva em caixa e o
  total de obrigações (depósitos + dívidas pendentes). Jogador decide
  onde depositar sabendo o risco.
- **Intervenção do governo**: se o rating cair abaixo de um limiar, o
  governo (ou um futuro "banco central" controlado por jogadores) pode
  intervir e liquidar a empresa de forma **ordenada** — vender os
  ativos e ratear entre credores antes da falência total, o que reduz
  (mas não necessariamente elimina) a perda dos 30% já combinada.

🆕 **Cartão de crédito, revisado:**

- Juros compostos agressivos sobre saldo não pago. ✅ Fechado em **10%
  ao mês** (~213% ao ano composto).
- Limite de crédito **não é fixo** — calculado a partir de uma
  combinação de Carisma + renda declarada (histórico de salário do
  jogador), não um valor arbitrário que o dono da Financeira escolhe

⚠️ **Trava anti-exploit necessária** (você mesmo marcou isso): impedir
que o dono abra uma Financeira, capte depósitos, e falência
"proposital" vire lucro líquido descontando os 30%. A reserva
obrigatória + rating público + intervenção do governo acima já ajudam
bastante nisso, mas vale revisar de novo quando formos implementar.

### 2.9 Produção passa a ser dos funcionários, não só do dono ⚠️ **mudança grande**

Hoje no código, só o **dono** clica em "produzir"/"fabricar" (simplificação
que eu tinha assumido). Pelo que você descreveu agora: **cada funcionário
que clica em "trabalhar" contribui pro progresso da produção** — ou
seja, produção vira um acúmulo coletivo dos funcionários trabalhando, não
uma ação isolada do dono. Isso é uma mudança de mecânica, não só de
número — precisa redesenhar a view de produzir/fabricar.

### 2.10 Estrelas ✅ (mantém)

Sem mudança na tabela de estrelas/cargos máximos/custo de upar que já
tínhamos. Construtora continua com a exceção de upar por obras
concluídas, não por essa tabela padrão.

### 2.11 Especialização de funcionário ✅ (implementado)

Um funcionário pode virar especialista num produto específico (ex:
"especialista em café"), produzindo mais daquele item do que o normal
da skill dele sozinha explicaria. Proposta: um registro separado
(`EspecializacaoDoFuncionario`: usuário, produto, nível), que sobe
conforme o funcionário produz aquele item especificamente — quanto mais
vezes ele trabalha *nesse produto*, maior o bônus só *nele*, sem
beneficiar os outros produtos da mesma empresa.

```
bônus_de_especialização = 1 + (nível_de_especialização / 100) × 0.5
```

Máximo de +50% de produção adicional pra quem virou especialista de
verdade — some tudo com a mecânica de diminishing returns geral (seção 1.4).

### 2.12 Qualidade afeta preço e preferência do consumidor ✅ (preço implementado; efeito ao consumir, não)

Hoje o preço de um produto é fixo (`preco_base`), igual pra qualquer
empresa que vende. Proposta: a estrela de quem produziu afeta tanto o
preço quanto o efeito do produto — um Pão de padaria 5★ não é só "mais
caro", ele **nutre/dá buff visivelmente mais** que o de uma padaria 1★.

```
preço efetivo = preco_base × (1 + (estrela − 1) × 0.15)
efeito efetivo (nutrição/buff) = efeito_base × (1 + (estrela − 1) × 0.2)
```

Isso cria de verdade um mercado de "básico barato" vs "premium caro",
em vez de todo produto igual ter preço fixo. Preferência do consumidor
(NPC ou jogador escolhendo onde comprar) fica pra depois — pressupõe
que exista uma listagem comparável no Mercado, o que já temos.

---

## 3. Escolas e universidades

Mantém o que já tínhamos combinado (profissionais, estrela da escola,
qualidade = skill dos profissionais + investimento em material) — só
que agora a "qualidade" afeta as **3 skills novas** (Inteligência,
Físico, Carisma) em vez das 8 categorias antigas.

---

## 4. Diploma e admissão universitária — fórmulas precisas 🤝

A prova de admissão é calibrada assumindo um jogador hipotético que
teve QoL 1 numa escola de qualidade 1 durante todo o período escolar
(isso hipoteticamente chega a 100 na skill relevante).

| Curso | Exige |
|---|---|
| Medicina | Inteligência 100 |
| Engenharia | Inteligência 100 **e** Físico 100 |
| Direito | Inteligência 100 **e** Carisma 100 |
| Outros diplomas | 50 (numa skill a definir por curso) — servem só pra impulsionar skill, sem destravar profissão específica |

✅ **Resolvido:** cada curso genérico é cadastrado já ligado a UMA das 3
skills, a que fizer mais sentido temático (ex: curso técnico industrial
→ Físico 50, curso de humanas → Carisma 50, curso de ciências →
Inteligência 50). Não é uma skill fixa pra todos, é decidido produto a
produto no catálogo de cursos.

Cada curso só pode ser concluído **uma vez** por jogador.

---

## 5. Dia a dia do jogador — revisão completa

### 5.1 Ações e custo de energia 🤝

| Ação | Custo de energia | Efeito |
|---|---|---|
| Trabalhar | 25 (era 10 no código — precisa mudar) | Ganha dinheiro + skill; contribui pra produção da empresa |
| Estudar (se matriculado) | 25 | Ganha skill (mais que trabalhar) |
| Praticar lazer | 25 | Buff temporário de QoL |

### 5.2 QoL — como funciona de verdade 🤝

- QoL tem uma **base**, definida pelos bens do jogador (casa, carro, roupas etc — sistema de posse ainda não existe)
- QoL decai em direção a essa base com o tempo
- Trabalhar/estudar **também** drena QoL diretamente: ~0.2 por clique
- Praticar lazer sobe QoL temporariamente
- Quanto maior o QoL, maior a **eficácia** de trabalho e estudo (multiplicador de ganho, ver seção 1.2)
- QoL base também define **quanto de energia regenera por tick** (novo vínculo — precisa de fórmula)

✅ **Resolvido — fórmula de energia por QoL:**
```
minutos_por_ponto_de_energia_efetivo = minutos_por_ponto_base / QoL_base
```
QoL 1 (padrão) = regen normal. QoL 0.5 = demora o dobro pra regenerar
cada ponto. QoL 1.2 (ex: cidade com população Ideal) = regen 20% mais
rápido. Mesma lógica pode valer pra saúde depois.

### 5.3 Saúde 🤝

- Chance de **decair por tick**, maior quanto menor o QoL (só quando QoL < 1)
- Se saúde chega num patamar baixo → jogador entra em "depressão", QoL base é **cortada pela metade**
- Se saúde chega a 0 → internado por 3 dias
- Jogador com diploma de Médico pode gastar 25 energia pra reduzir esse tempo de internação de outro jogador

✅ **Resolvido — patamar de depressão:** saúde ≤ 20 (de 100) ativa o
estado de depressão. Sai da depressão voltando a subir a saúde acima
desse patamar (com alguma folga pra não ficar entrando e saindo toda
hora — proponho sair só acima de 30, não exatamente 20, pra evitar
oscilação constante).

### 5.4 Nutrição (esse é o nome que você usou, substitui minha sugestão de "Saciedade") 🤝

- Funciona como a saúde, mas recupera consumindo **itens de alimento do inventário** (novo sistema, ver seção 6)
- Nutrição 0 começa a reduzir a QoL, até um piso de **60% da QoL base**

### 5.5 Viajar 🤝

- Paga uma empresa de Transporte
- Fica 1 dia sem trabalhar/produzir
- Ganha boost na QoL base — limite de **1x por mês**

---

## 6. Inventário do jogador (sistema novo, ainda não existe) ⚠️

Precisa existir pra "consumir item de alimento pra recuperar nutrição"
funcionar. Hoje comprar no Mercado só transfere dinheiro — não guarda
nada. Vai precisar de um model tipo `ItemDoJogador` (usuário, produto,
quantidade), e as compras passam a alimentar isso em vez de só somar
dinheiro pro vendedor.

---

## 7. Política e QoL — efeito da população da cidade 🤝

| Faixa de população | Efeito na QoL |
|---|---|
| Baixa | 0 |
| Ideal | +0.2 |
| Acima | −0.1 |
| Lotada | −0.2 |

(você já avisou que os valores podem mudar pra ter mais impacto — não é definitivo)

### 7.1 Trade-offs explícitos nas decisões políticas 🆕 (novo)

Toda lei com impacto econômico precisa ter um efeito colateral visível,
não só o benefício — senão vira escolha óbvia sem custo político real.
Exemplos que você deu:

- **Aumentar salário mínimo** → sobe QoL dos trabalhadores, mas aumenta
  o custo das empresas e pode gerar desemprego
- **Subsídio agrícola** → melhora o preço dos alimentos pro consumidor,
  mas gera déficit no orçamento público

Isso implica que o sistema de leis (ainda não implementado) precisa
calcular e mostrar os dois lados de cada proposta antes da votação, não
só o efeito pretendido. E implica também que precisa existir um
**orçamento público** de verdade (receita de impostos vs gastos), pra
"gerar déficit" ser uma consequência mensurável, não só flavor text.

### 7.2 População dinâmica (jogadores + NPCs) 🆕 (novo, versão enxuta pra não travar tudo)

Migração de jogadores + IA completa de NPC reagindo à economia é grande
demais pra entrar de uma vez. Proposta de versão inicial, simples o
suficiente pra implementar junto com o resto:

- **NPCs de preenchimento**: população de NPC de um bairro = capacidade
  total dos imóveis residenciais construídos ali **menos** os jogadores
  que já moram lá. Não fazem nada, não têm IA, só contam pra calcular a
  faixa de população (Baixa/Ideal/Acima/Lotada) da seção 7 — assim a
  política já tem efeito mensurável desde o início, sem precisar de
  simulação de verdade
- **Migração de jogador**: nova ação "mudar de bairro/cidade" — paga
  uma taxa + 1 dia parado (mesmo custo de Viajar), transfere o `Perfil`
  pro novo bairro

NPC "reagindo de verdade" às políticas (comprando no Mercado, votando,
etc) fica pra uma fase bem mais adiante — colocar isso agora atrasaria
todo o resto sem necessidade.

---

## 8. Cargos políticos — números completos 🆕

### 8.1 Executivo

| Cargo | Quantos |
|---|---|
| Presidente | 1 (nacional) |
| Governador | 1 por estado |
| Prefeito | 1 por cidade |

### 8.2 Legislativo

| Cargo | Quantos |
|---|---|
| Deputados (Câmara) | 1 a cada 500 jogadores residentes no país, mínimo 5 no total |

### 8.3 Judiciário e fiscalização

| Cargo | Quantos |
|---|---|
| Ministros (STF) | 7, fixo, nacional |
| Juízes (tribunais locais/"ministros menores") | 1 a cada 200 jogadores residentes na cidade, mínimo 1 por cidade |
| Fiscais | 1 a cada 300 jogadores residentes na cidade, mínimo 1 por cidade |

⚠️ "População" aqui hoje só conta jogador de verdade (não temos NPC
ainda — ver seção 7.2/7.3). Quando NPC existir, essas contas passam a
usar população total (jogador + NPC) automaticamente, sem precisar
redesenhar a regra.

---

## 9. Orçamento público 🆕 (sistema novo, pré-requisito pros trade-offs de lei)

Cada nível de governo (cidade, estado, país) tem seu próprio orçamento:

- **Receita**: impostos — % sobre transações do Mercado, % sobre
  salários pagos, % sobre lucro de empresa. As taxas exatas são leis
  paramétricas (ligou com o sistema de leis que já esboçamos
  antes — o político define o %, dentro de limites)
- **Gastos**: infraestrutura (escolas, hospitais, contratos de
  construção), subsídios (ex: agrícola, do exemplo da seção 7.1)
- **Déficit**: se os gastos aprovados passarem da receita acumulada, o
  orçamento fica negativo. Proposta: um orçamento muito tempo no
  vermelho aumenta a insatisfação da população (baixa QoL geral da
  cidade/estado), criando pressão política real — não só um número
  abstrato

⚠️ Isso é pré-requisito técnico pra qualquer trade-off de lei ter efeito
mensurável (seção 7.1). Sem orçamento, "gera déficit público" é só
flavor text.

---

---

## 10. Imóveis e zonas ✅ (mantém, com um ajuste)

Mantém a tabela de zonas/tipos que já tínhamos. Ajuste: reforçar que a
estrela da empresa de Varejo (e não só da Construtora) determina qual
imóvel comercial ela pode ocupar.

### 10.1 Imóveis residenciais em detalhe 🆕 (faltava, proposta)

| Tipo | Capacidade | Estrela mínima da Construtora | Efeito na QoL base do morador |
|---|---|---|---|
| Baixa densidade simples | 1 família por lote | 1★ | +0 (linha de base) |
| Baixa densidade luxo | 1 família por lote | 3★ | +0.3 |
| Alta densidade simples | ~20 unidades por prédio | 2★ | +0.1 |
| Alta densidade luxo | ~20 unidades por prédio | 4★ | +0.4 |

Isso é o que vai alimentar o "bens do jogador" que a seção 5.2 menciona
como base da QoL (junto com carro, roupas etc, que ainda não têm
sistema próprio).

---

## 11. Catálogo de leis paramétricas 🆕

Cada lei tem um **escopo** (onde o efeito vale quando aprovada — não
quem pode propor: qualquer político pode propor qualquer lei, e ela
sobe pela cadeia de aprovação já combinada na seção 6.3, não importa o
escopo). Todas têm um **parâmetro** que o proponente define na hora de
propor, dentro de limites técnicos (não dá pra propor imposto de
-500%, por exemplo).

### 11.1 Econômico e empresarial

| Lei | Escopo | Parâmetro | Padrão | Efeito | Trade-off |
|---|---|---|---|---|---|
| Imposto sobre vendas | Federal | X% sobre toda venda (Mercado + entre empresas) | 5% | Receita pro orçamento | Reduz margem, pode subir preço final |
| Imposto de renda | Federal | X% sobre salário pago | 10% | Receita pro orçamento | Reduz salário líquido do jogador |
| Salário mínimo | Federal | R$ X por dia (teto já existe por skill, isso é piso) | R$ 50 | Sobe QoL de quem ganha pouco | Empresa pequena pode não bancar → desemprego |
| Regulação antitruste | Federal | Máximo de X empresas do mesmo tipo por dono | sem teto | Evita monopólio | Trava expansão de quem é eficiente |
| Subsídio setorial | Federal ou Estadual | X% de desconto no preço de produtos de um terreno/tipo de indústria | 0% | Baixa preço pro consumidor | Gera déficit (sai do orçamento público) |
| Reserva obrigatória da Financeira | Federal | X% mínimo em caixa | 20% | Protege depositante | Financeira empresta menos, lucra menos |
| Teto de juros do cartão de crédito | Federal | X% ao mês, máximo | 10% | Protege devedor | Financeira pode restringir crédito |
| Cota de diplomados | Federal | X% dos cargos de Industrial/Construtora acima de N★ têm que ser diplomados, além da tabela fixa da seção 1.6 | 0% (só a tabela fixa vale) | Garante retorno de quem investiu em universidade | Empresa pode não achar diplomado suficiente e travar contratação |
| Teto de preço de produto essencial | Federal ou Municipal | Preço máximo de venda de um Produto específico (ex: Pão) | sem teto | Protege consumidor de alta abusiva | Produtor reduz oferta se não for lucrativo — risco de desabastecimento |
| Transparência financeira obrigatória | Federal | Empresas acima de X★ publicam saldo/estoque publicamente | desligada | Reduz fraude, ajuda decisão de compra/investimento | Empresa perde vantagem competitiva de sigilo |
| Incentivo a P&D tecnológico | Federal | X% do lucro de Industrial Tecnológica 4★+ reinvestido, acelera desbloqueio de receita nova | 0% | Acelera avanço tecnológico do território | Reduz lucro líquido do dono |
| Teto salarial | Federal | Nenhum cargo paga acima de R$ X por dia, mesmo dentro do teto natural por skill (seção 1.3) | sem teto | Reduz desigualdade extrema | Desincentiva empresa contratar gente de skill muito alta |
| Estoque mínimo de emergência | Municipal | Varejo mantém X unidades de comida em estoque sempre | 0 | Evita desabastecimento repentino | Empresa trava capital em estoque parado |

### 11.2 Trabalhista

| Lei | Escopo | Parâmetro | Padrão | Efeito | Trade-off |
|---|---|---|---|---|---|
| Jornada máxima | Federal | Máximo de X cliques de "trabalhar" por dia | sem limite | Evita exploração/burnout | Reduz teto de produção por jogador |
| Fiscalização de EPI/uniforme | Federal | Multa de R$ X se empresa for flagrada sem estoque de consumo operacional | desligada | Garante que a mecânica da seção 2.4 é levada a sério | Custo extra de fiscalização/risco pro dono |
| Vale-transporte obrigatório | Federal | Empresas com X+ funcionários custeiam ticket de Transporte pra todos | desligado | Sobe QoL dos funcionários sem custo direto pro jogador | Custo extra pra empresa grande |

### 11.3 Fiscal e orçamentário

| Lei | Escopo | Parâmetro | Padrão | Efeito | Trade-off |
|---|---|---|---|---|---|
| Alocação de orçamento — Educação | Municipal/Estadual/Federal | X% do orçamento do período | 20% | Mais verba pra qualidade de ensino (seção 2.3) | Sobra menos pra outras áreas |
| Alocação de orçamento — Saúde | idem | X% do orçamento do período | 20% | Mais verba pra hospitais | idem |
| Alocação de orçamento — Infraestrutura | idem | X% do orçamento do período | 20% | Mais contratos de construção liberados | idem |
| Teto de déficit público | idem | Déficit máximo permitido (% da receita anual) | 10% | Evita colapso fiscal | Trava gasto mesmo em emergência |
| Salário de político | Federal | R$ X por dia por cargo eleito, sai do orçamento | R$ 200 | Atrai gente competente pro cargo | É gasto público obrigatório |
| Resgate emergencial de empresa | Municipal/Estadual/Federal | Governo injeta R$ X numa empresa estratégica em risco de falência | não usado por padrão | Evita colapso de empresa importante pro território | Gasto público direto, risco de virar favorecimento político |

### 11.4 Imobiliário e zoneamento

| Lei | Escopo | Parâmetro | Padrão | Efeito | Trade-off |
|---|---|---|---|---|---|
| Imposto predial (IPTU) | Municipal | X% do valor do imóvel, por ano | 1% | Receita municipal | Encarece manter imóvel parado |
| Teto de posse de imóveis | Municipal | Máximo de X imóveis por jogador/empresa | sem teto | Evita concentração/especulação | Limita investimento, pode reduzir oferta de aluguel |
| Controle de aluguel | Municipal | Teto de X% de reajuste de aluguel por ano | sem teto | Protege inquilino | Desincentiva construir pra alugar |
| Abertura de zona | Municipal | Quantidade de novas zonas de um tipo, liberadas pro leilão | 1 por vez | Empresas crescem, mais imóvel disponível | Sobe densidade populacional → pode piorar QoL (seção 7) |
| Estrela mínima do leilão | Municipal | Estrela mínima da Construtora pra participar daquela zona | 1★ | Garante qualidade da obra | Menos empresas conseguem competir |

### 11.5 Social

| Lei | Escopo | Parâmetro | Padrão | Efeito | Trade-off |
|---|---|---|---|---|---|
| Bolsa educação | Municipal/Estadual/Federal | R$ X por aluno matriculado | R$ 0 | Incentiva matrícula, mais gente chega na universidade | Gasto público |
| Programa de saúde pública | idem | R$ X de desconto em tratamento/internação | R$ 0 | Mais acesso à saúde, menos tempo internado | Gasto público |
| Taxa/incentivo de migração | Municipal | R$ X cobrado (positivo) ou pago como bônus (negativo) por jogador que se muda pra cá | R$ 0 | Taxa alta protege contra superlotação; bônus atrai gente pra cidade esvaziada | Taxa alta afasta jogador; bônus alto pesa no orçamento |

### 11.6 Eleitoral e constitucional

Essas são as leis "pesadas" — mudam a própria estrutura do jogo, não só
um número econômico:

| Lei | Escopo | Parâmetro | Padrão | Efeito | Trade-off |
|---|---|---|---|---|---|
| Sistema eleitoral | Federal | Povo vota em tudo / povo só vota presidente (que indica o resto) / sem eleição popular nenhuma | Povo vota em tudo | Muda quem escolhe cada cargo | Concentrar poder é mais eficiente a curto prazo, mas arrisca plebiscito de derrubada (seção 6.3) |
| Duração de mandato | Federal | X meses | 6 (prefeito/governador), 12 (presidente) | Muda ritmo de renovação política | Mandato longo = estabilidade, mas menos accountability |

✅ **Leis constitucionais (protegidas)** — confirmado: existem garantias
que **não podem ser votadas pra baixo**: moradia e educação. Funcionam
como valores com um **piso mínimo travado** (ex: "Alocação de
orçamento — Educação" não pode ir abaixo de X% nunca, não importa quem
proponha), e se o indicador de verdade (% da população sem
escola/sem moradia) passar de um limite, isso dispara automaticamente a
possibilidade de plebiscito pra depor o presidente — sem precisar de um
fiscal abrir processo, é uma trava sistêmica.

### 11.7 Projetos temporários (campanhas) 🆕

Diferente das leis das seções 12.1–12.6 (parâmetro permanente até
alguém votar de novo), campanha é um **investimento pontual**: custa
uma vez, dura um tempo definido, e some sozinha no final. Não cria
nada novo — reforça o que já existe (empresas de um setor, ou
escolas/universidades/hospitais já construídos) dentro de um
território escolhido.

**Escopo territorial segue a jurisdição de quem propõe** — reaproveita
a hierarquia política que já existe, sem precisar de conceito novo:

| Quem propõe | Escolhe entre | Exemplo |
|---|---|---|
| Prefeito | Bairros da própria cidade | 3 dos 8 bairros de Nova Polis |
| Governador | Cidades do próprio estado | 2 das 5 cidades do Estado Central |
| Presidente | Estados do país | Metade dos estados, ou o país inteiro |

**Tipos de campanha:**

| Tipo | O que reforça | Parâmetro |
|---|---|---|
| Boom de investimento setorial | Todas as empresas de um terreno (Matriz) ou tipo de indústria (Industrial) já existentes no território | X% de buff na quantidade produzida/fabricada |
| Campanha educacional | Todas as escolas e universidades já existentes no território | X% de buff na qualidade de ensino (afeta o ganho de skill dos alunos, seção 1.2) |
| Campanha de saúde pública | Todos os hospitais já existentes no território | X% de redução no tempo de internação, ou X% menos chance de saúde decair |

**Custo, escala com o alcance:**

```
custo = custo_base_por_unidade × número_de_unidades_escolhidas × (duração_em_dias / 30)
```

Proposta de `custo_base_por_unidade` (por bairro/cidade/estado,
conforme quem propõe): **R$ 10.000 a cada 30 dias**. Ou seja, um
prefeito fazendo um boom de investimento em 3 bairros por 60 dias
custa `10.000 × 3 × 2 = R$ 60.000`, saindo do orçamento municipal
(seção 9).

**Limites propostos** (pra não virar exploit): buff máximo de **+50%**,
duração máxima de **90 dias**. Depois de expirar, pode propor de novo
— sem restrição de quantas vezes, contanto que o orçamento aguente.

### 11.8 Ambiental 🆕 (categoria nova)

| Lei | Escopo | Parâmetro | Padrão | Efeito | Trade-off |
|---|---|---|---|---|---|
| Teto de extração ambiental | Municipal | Reduz em X% a produção máxima de Matrizes de Extrativismo/Mineração no território | 0% (sem teto) | Melhora a QoL do bairro (menos poluição/degradação) | Reduz oferta de matéria-prima — sobe o preço de toda a cadeia que depende dela (Industrial e Varejo sentem também) |

---

## 12. Histórico do mundo (crônica do servidor) 🆕

Registro cronológico e permanente dos eventos mais importantes do jogo,
numa página pública ("História de Nova Polis"). Cada entrada: data
(ano/mês do jogo), descrição curta, categoria (política/economia/
conflito/marco).

Dispara registro automático em: primeira eleição de cada cargo,
fundação da primeira empresa de cada tipo, primeira construção
institucional, mudanças de lei com trade-off grande, mobilização de
milícia (seção 19), renúncia/deposição de presidente, falência de
empresa grande (acima de X★), eventos aleatórios (seção 13).

Tecnicamente barato — um model `EventoHistorico` (data, categoria,
descrição), preenchido automaticamente pelos outros sistemas quando
disparam — mas o valor de jogo é enorme — dá identidade única a cada
servidor.

---

## 13. Sistema de eventos aleatórios 🆕

Princípio central, direto da sua ideia: **evento nunca aplica um
modificador solto tipo "+20%"** — sempre altera uma condição real que
já existe no sistema, e deixa a cadeia de causa-efeito que a gente já
desenhou (produção → estoque → preço → custo → QoL) reagir sozinha.
Evento não precisa de lógica de efeito própria, só precisa mexer nos
números que os sistemas já leem.

| Evento | O que altera de verdade | Efeito em cascata natural |
|---|---|---|
| Acidente em mina | Zera/reduz o estoque de uma Matriz de Mineração específica | Matéria-prima escassa → Industrial não fabrica → preço sobe |
| Desastre natural | Reduz QoL de um bairro/cidade direto, pode destruir % do estoque das empresas de lá | QoL baixa → menos eficiência de trabalho/skill (seção 1.2) → governo precisa agir |
| Pandemia | Sobe a chance de decaimento de Saúde (seção 5.3) numa região | Mais gente internada → menos gente trabalhando → produção cai |
| Descoberta de recurso | Abre uma Matriz "vaga" numa zona Rural nova, ou aumenta o teto de produção de uma existente | Mais oferta → preço cai |
| Quebra de empresa importante | Força falência de uma empresa grande (acima de X★) | Funcionários desempregados, estoque some do mercado |
| Boom econômico | Aumenta temporariamente a demanda numa região | Preço sobe organicamente, sem mexer no preço base |
| Escassez | Reduz o estoque global de um Produto específico | Preço sobe, empresas competem pelo pouco que sobra |
| Migração | Muda a população de NPC (seção 7.2) de uma cidade de uma vez | Muda a faixa de população e a QoL da tabela (seção 7) |
| Crise bancária | Reduz o rating de solvência de todas as Financeiras de uma vez (seção 2.8) | Pode disparar intervenção do governo em cascata |

⚠️ Isso é claramente conteúdo de depois que a base estiver rodando —
marcar como fase tardia no roadmap, não prioridade de curto prazo.

---

## 14. Rankings 🆕

Dois tipos: **ao vivo** (situação atual, muda a qualquer momento) e
**histórico** (recorde já alcançado, nunca é apagado mesmo que a
pessoa perca a posição depois).

**Ao vivo:** maior patrimônio, maior empresa (por estrela, funcionários
como desempate), maior produção, melhor QoL pessoal, maior influência
política, maior empregador, maior contribuinte (imposto pago), melhor
universidade/escola, maior organização (maior milícia, seção 19),
**tempo de conta ativa** ✅ (era "expectativa de vida", renomeado — mede
há quanto tempo o jogador tem a mesma conta ativa, não morte de
personagem).

**Histórico:** maior patrimônio já alcançado, maior empresa da
história, presidente com maior aprovação.

⚠️ **Pendência:** "maior expectativa de vida" não tem um equivalente
literal claro hoje, já que não existe morte de personagem no design —
só internação (seção 5.3) e prisão (seções 6.3/8). Você quis dizer
tempo de conta ativa sem interrupção, ou tinha outra métrica em mente?

---

## 15. Jornal / feed de notícias 🆕

Feed gerado automaticamente pelos próprios sistemas — sem geração de
texto livre por IA, só templates preenchidos com dado real:

- Produto varia X% de preço em 24h → "Mercado do {produto} registra {alta/queda} de {X}%"
- Nova zona aberta → "Prefeitura de {cidade} anuncia nova zona {tipo}"
- Empresa grande falindo → "{Empresa} entra em falência"
- Lei aprovada → "{Cargo} aprova {nome da lei}"
- Mobilização de milícia → "{Milícia} convoca nova mobilização"
- QoL nacional caindo 3 meses seguidos → "QoL nacional cai pelo terceiro mês consecutivo"

Reaproveita o mesmo `EventoHistorico` da seção 12 — a diferença é só de
apresentação: histórico é a página completa e permanente, jornal é o
feed recente com cara de manchete. Podem ser a mesma tabela, com um
campo `eh_manchete`.

---

## 16. Empresas com múltiplos donos (sociedade / ações) 🆕 — mudança estrutural grande

Hoje `Empresa.dono` é um jogador único (FK direta). Pra sociedade,
precisa virar uma relação N-pra-N com percentual:

```
Empresa
  ↳ Participacao (empresa, jogador, percentual)
```

- Fundador começa com 100%, pode vender parte da participação pra
  outro jogador (conecta com Contratos, seção 18)
- Quem decide o quê: dono majoritário (>50%) mantém controle sozinho,
  igual hoje. Sem maioria clara, precisa de votação entre os sócios
  proporcional à participação — mesma lógica de aprovação de leis, só
  que dentro da empresa
- **É o pré-requisito estrutural da Bolsa de Valores** (seção 2.8): uma
  ação nada mais é que um pedaço pequeno e padronizado de
  `Participacao`, negociado livremente. Faz sentido reaproveitar o
  mesmo modelo em vez de criar dois sistemas parecidos.

⚠️ Mudança estrutural grande — todo o código atual assume dono único
(upar, criar cargo, receber pagamento de venda). Vale tratar como fase
própria, não ajuste pontual.

---

## 17. Transparência de mercado 🆕

Mercado (e a página de cada Produto) passam a mostrar estatística
agregada, não só "compre aqui":

```
Café
Preço médio: R$ 42       Menor preço: R$ 31       Maior preço: R$ 68
Estoque total: 14.200     Produção diária: 11.800   Consumo diário: 13.500
Tendência: ⬆️ +8% (últimos 7 dias)
```

E a página da empresa ganha um resumo de causa-efeito nos custos:

> Seus custos aumentaram 14% nos últimos 7 dias. Principal causa: alta de 21% no preço do Aço.

Tecnicamente é "só" leitura agregada do que já existe — mas expõe uma
lacuna real: hoje o preço de venda é sempre o `preco_base` fixo do
catálogo (a seção 2.12 já previa isso mudando por qualidade). Pra
"tendência" e "preço médio" fazerem sentido, precisa existir um
histórico de preço por transação de verdade, não só o preço "oficial".

---

## 18. Contratos entre jogadores 🆕

Diferente de compra avulsa (que já existe): contrato é um **acordo
recorrente ou de prazo**, registrado no sistema, entre duas partes:

| Tipo | Exemplo |
|---|---|
| Fornecimento | "Fornecer 10.000 unidades de Aço por mês, a R$ 12/unidade" |
| Trabalho | Como um Cargo, mas negociado fora dos termos padrão (ex: salário combinado à parte) |
| Empréstimo entre jogadores | Fora da Financeira — direto entre duas pessoas, prazo e juros combinados |
| Aluguel | De imóvel, entre dono e morador/empresa |
| Governamental | Generaliza o leilão de contrato de construção (seção 11.4) pra outros tipos de contrato com o governo |

Precisa de aceite das duas partes, prazo/recorrência, e uma consequência
real pra quebra de contrato (multa combinada, ou reputação — que ainda
não existe como sistema, faria sentido nascer junto com isso). Sem
nenhum enforcement, contrato é só um "combinado de boca" que já dá pra
fazer sem sistema nenhum — o valor está em ter consequência de verdade.

---

## 19. Militares e Milícias 🆕 — sistema novo e grande

Primeiro sistema do jogo com conflito direto entre jogadores — tudo o
resto até aqui é econômico/político sem "combate". Esse é o design com
mais peça móvel em aberto de todos até agora.

### 19.1 Exército

- Governo contrata jogadores como militares — funcionário público,
  análogo a um Cargo, mas com exclusividade: **militar não pode ter
  outro emprego nem ser dono de empresa**
- Treinamento gasta energia, sobe Físico; cargos de comando (Capitão,
  General, Marechal) também exigem Inteligência
- Nível de investimento do governo (orçamento, seção 9) afeta a
  eficiência do treinamento

### 19.2 Milícias

- Múltiplas milícias independentes podem existir ao mesmo tempo
- Jogador (não-militar) se filia à milícia alinhada com seus interesses políticos
- **Membro ≠ mobilizado**: liderança convoca mobilizações específicas;
  só uma parte dos membros participa de cada confronto
- Líder da milícia vencedora assume a Presidência — condição
  **propositalmente muito difícil** de acontecer

### 19.3 Força e prontidão

| Lado | Força depende de |
|---|---|
| Exército | Quantidade de militares, skill média, treinamento/investimento, prontidão atual |
| Milícia | Quantidade de membros mobilizados, skill média, e um multiplicador ligado à QoL global — **quanto menor a QoL nacional, maior a capacidade de mobilização das milícias** |

Militar é individualmente mais eficiente, mas milícia muito numerosa
pode superar Exército profissional só pelo número. Prontidão do
Exército desgasta com confronto/mobilização, recupera com
investimento/treino/descanso.

### 19.4 Regras do confronto

- **Vitória por atrito**: milícia não precisa ganhar um confronto —
  perder repetidamente já desgasta o Exército financeira e
  operacionalmente até a repressão deixar de valer a pena pro governo
- **Derrota da milícia não é punição pesada**: só fracassa aquela
  mobilização específica, pode tentar de novo
- **Custo da repressão**: manter o Exército mobilizado gera custo pro
  orçamento — campanha prolongada pode ficar insustentável
- **Renúncia pacífica**: presidente pode sair voluntariamente antes de
  uma derrota total, evitando queda violenta
- **Vitória da milícia**: líder assume a Presidência e pode indicar
  novos membros do STF

✅ **Cooldown entre Exército e Milícia** (regra sua, confirmada): quem
sai de uma milícia só pode entrar no Exército depois de **3 meses**.
Quem sai do Exército só pode entrar numa milícia depois de **3 meses**
também. Evita troca oportunista de lado no meio de um conflito.

✅ **Trava constitucional sobrevive a uma tomada de poder** — confirmado:
mesmo com o líder da milícia assumindo a Presidência, as garantias de
moradia/educação (seção 11.6) continuam valendo. O novo presidente
herda a mesma trava, não começa "zerado".

🆕 **Propostas pro resto (ainda sem sua confirmação):**

- **Quantidade de milícias**: sem mínimo nem máximo teórico — qualquer
  jogador pode fundar uma. Proponho só um piso de **5 membros** pra uma
  milícia ser "oficial" (aparecer no ranking, poder mobilizar) — abaixo
  disso é só um grupo informal sem efeito mecânico.
- **Fórmula de força:**
  ```
  Força do Exército = nº de militares × skill Físico médio × prontidão (0 a 1)
  Força da Milícia  = nº de membros mobilizados × skill Físico médio × multiplicador de QoL nacional
  ```
  onde o multiplicador de QoL só ativa abaixo do ideal: `multiplicador = 1 + (1 − QoL_nacional)` se QoL < 1, senão `1`. Isso implementa direto a regra que você já tinha dado (QoL baixa = milícia mais forte).
- **Exército após deposição**: proponho que o Exército seja **dissolvido**
  — todo militar vira civil livre pra escolher novo emprego, e o novo
  presidente (ex-líder de milícia) começa um Exército do zero. Isso
  evita que vencer uma vez vire vantagem militar permanente, reforçando
  o "deve ser muito difícil de alcançar" que você já tinha pedido.
- A trava constitucional (seção 11.6, moradia/educação) continua valendo depois de uma tomada de poder, ou é reiniciada?

---

## 20. Filosofia de feedback ao jogador (UI) 🆕

Princípio geral pra todo indicador importante, não só QoL: **nunca
mostrar só o número final, sempre mostrar por que ele é esse número.**
Ao clicar, abre um detalhamento aditivo:

```
QoL: 0.82 → 0.76
  Moradia:                    +0.10
  População acima do ideal:   −0.10
  Nutrição baixa:             −0.04
  Saúde baixa:                −0.02
```

Vale pra qualquer fórmula com múltiplas entradas somando num resultado
(QoL, custo de empresa, força militar, salário...). Tecnicamente,
significa que toda fórmula composta do jogo precisa **retornar o
detalhamento junto com o total**, não só o número final — é uma
convenção de código a manter desde o início dessas fórmulas, não um
retrofit fácil de fazer depois que tudo já retorna só um número.

---

## 21. Bots para testes de beta 🆕 (metodologia de teste, não mecânica de jogo)

Não é conteúdo do jogo final — é ferramenta de validação antes do
lançamento:

- Criar usuários-bot progressivamente (proposta: 1 por hora), jogando
  sob as **mesmas regras** dos jogadores reais (sem trapacear limite
  de energia etc)
- Comportamento simples (regras básicas tipo "se energia > 50%,
  trabalha; se dinheiro > X, tenta abrir empresa"), não precisa de IA
  sofisticada
- Registrar o comportamento pra achar problema estrutural antes de
  gente de verdade jogar: gargalo de produção, concentração de
  emprego, empresa quebrando em cadeia, falta de produto, distribuição
  de riqueza anormal

Isso é plano de teste, não roadmap de feature — vale um `TESTING.md`
próprio quando chegar perto do lançamento, não uma fase no roadmap
principal.

---

## 22. Implicações técnicas — o que precisa ser refeito no código

Pra você ter clareza do tamanho do refactor antes da gente decidir por
onde começar:

1. ✅ **Sistema de skills** — feito na Fase 1: trocado as 8
   `CategoriaDeHabilidade` por 3 stats fixos (Inteligência/Físico/Carisma),
   usando `TextChoices` em vez de tabela (são fixas, não precisam mais
   de catálogo editável).
2. ✅ **Classificação de empresa** — feito na Fase 1: Matriz tem
   `terreno` (Agropecuária/Extrativismo/Mineração), Industrial tem
   `tipo_industria` (Produção/Alimentícia/Bens de consumo/Tecnológica),
   Serviços tem `especializacao_servico` (Transporte/Publicidade/Lazer/Financeira).
   `Empresa.clean()` garante que só o campo certo pro tipo escolhido é
   preenchido. `setor` como conceito compartilhado com skill não existe mais.
3. **Catálogo de produtos**: Fase 1 trocou os produtos placeholder por
   um recorte pequeno mas real (4 matérias-primas, 3 manufaturados,
   já usando terreno/tipo_industria corretos). Expandir pro catálogo
   completo (~40 itens) fica pra Fase 2.
4. **Produção via funcionário**: `produzir`/`fabricar` deixam de ser
   ação exclusiva do dono; viram progresso acumulado por cliques de
   "trabalhar" de qualquer funcionário.
5. **Inventário do jogador**: model novo, do zero.
6. **QoL pessoal, Saúde, Nutrição**: 3 barras novas no `Perfil`, com
   decaimento/regeneração próprios, além da energia que já existe.
7. **Salário com teto por skill**: validação nova ao definir/pagar salário.
8. **Consumo operacional** (EPIs, uniformes, materiais escolares/hospitalares): mecânica nova de "empresa/instituição gasta estoque pra funcionar".
9. ✅ **Diminishing returns de skill** — feito na Fase 1:
   `HabilidadeDoJogador.ganhar_xp()` já aplica o multiplicador por
   faixa de 100 pontos, testado e confirmado matematicamente correto.
10. **Especialização de funcionário**: model novo ligando jogador + produto + nível de especialização.
11. **Qualidade afetando preço/efeito**: os cálculos de compra (`comprar_de_empresa`, `comprar_do_mercado`) passam a considerar a estrela de quem produziu, não só `preco_base` fixo.
12. **Financeira completa**: reserva obrigatória, rating de solvência, intervenção do governo, juros compostos, limite de crédito calculado — é praticamente um app novo por si só.
13. **Orçamento público**: pré-requisito pra trade-offs de lei terem efeito real (déficit/superávit mensurável).
14. **População dinâmica com NPCs**: sistema de simulação separado, migração de jogadores + IA leve de NPC.
15. **Estrela mínima em toda receita**: `Receita` precisa do campo `estrela_minima` — não é caso especial do Carro, é regra geral de todo o catálogo (1★ a 5★, valores já definidos na seção 2.3).
16. **Compra Industrial→Industrial**: `REGRAS_DE_COMPRA` precisa de uma entrada nova pra Industrial comprar manufaturado de outra Industrial (hoje só existe Industrial comprando de Matriz).
17. **Limite de estoque por funcionário**: Matriz, Industrial e agora Varejo têm capacidade de produzir/comprar proporcional a funcionários ativos — muda a lógica de `produzir`/`fabricar`/`comprar_de_empresa` de "ação isolada do dono" pra "capacidade agregada dos funcionários".
18. **Leis paramétricas**: model `Lei` (nome, escopo, parâmetro atual, quem propôs, status de aprovação) + o motor que aplica o efeito de cada uma nos cálculos existentes (impostos entram em `comprar_de_empresa`/pagamento de salário, teto de posse em `criar_empresa`, etc — cada lei "pluga" num ponto diferente do código já existente).
19. **Leis constitucionais protegidas**: piso mínimo travado + verificação automática de indicador (% sem moradia/escola) disparando elegibilidade de plebiscito.
20. **Campanhas temporárias**: model `Campanha` (tipo, território afetado, buff, data de início/fim), + um job agendado (mesmo padrão dos outros prazos, seção "arquitetura de worker") que desativa a campanha sozinha quando a duração acaba, e os pontos onde o buff precisa ser lido (produção de Matriz/Industrial, qualidade de escola, tempo de internação) passam a somar o bônus de campanha ativa, se houver.
21. **`EventoHistorico`**: model único usado tanto pra Histórico (seção 12) quanto pro Jornal (seção 15) — outros sistemas (leis, falências, milícia) chamam um helper pra registrar evento, em vez de cada view escrever isso na mão.
22. **Eventos aleatórios**: um worker agendado (mesmo padrão de outros jobs) que sorteia e dispara eventos da tabela da seção 13, mexendo direto nos campos que os sistemas já leem (estoque, QoL, rating de solvência) — sem lógica de efeito própria.
23. **Rankings**: queries agregadas (ordenação por patrimônio, produção etc) + uma tabela separada de recordes históricos que só atualiza quando bate um novo máximo, nunca reduz.
24. **Sociedade/ações**: `Participacao` (empresa, jogador, percentual) substitui `Empresa.dono` como FK direta — reescreve toda lógica que hoje assume dono único (upar, criar cargo, receber pagamento).
25. **Histórico de preço por transação**: hoje só existe `preco_base` fixo por produto — precisa de um registro por transação de compra/venda pra "preço médio/tendência" (seção 17) fazerem sentido.
26. **Contratos**: model `Contrato` (tipo, partes, termos, prazo, status) + verificação periódica de cumprimento/quebra.
27. **Militares e Milícias**: sistema novo do zero — `Militar`, `Milicia`, `Mobilizacao`, fórmula de força de combate, e o fluxo de deposição/vitória que muda quem ocupa a Presidência.
28. **Fórmulas com detalhamento**: convenção de código pra toda fórmula composta (QoL, custo, força militar) retornar o breakdown aditivo junto com o total, não só o número final (seção 20) — precisa virar padrão desde as primeiras fórmulas novas escritas, não só nas telas.

**Fase 1 concluída e testada** (itens 1, 2 e 9). Itens 3 (catálogo
completo) e 16 (compra Industrial→Industrial) formam a Fase 2 natural,
já que um depende do outro (o Carro só faz sentido com os dois prontos).

---

## Pendências que ainda restam

- [x] Salário máximo: resolvido, é por dia (acumulador simples)
- [x] Veículo próprio: adiado de propósito, sem sistema por enquanto
- [x] "Maior expectativa de vida" (ranking, seção 14): resolvido, é tempo de conta ativa
- [x] Milícias (seção 19.4): cooldown de 3 meses pra trocar de lado, trava constitucional sobrevive a tomada de poder — ambos confirmados. Quantidade de milícias, fórmula de força e dissolução do Exército pós-deposição ficaram como proposta 🆕, aguardando confirmação
- [ ] Validar as fórmulas 🆕 propostas ao longo do documento — se eu não tiver notícia em contrário, vou tratar como aceitas quando começarmos a implementar
