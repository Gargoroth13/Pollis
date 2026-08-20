# Polis — Documento de Design

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

### 2.11 Especialização de funcionário 🆕 (novo)

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

### 2.12 Qualidade afeta preço e preferência do consumidor 🆕 (novo)

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

## 11. Implicações técnicas — o que precisa ser refeito no código

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

**Fase 1 concluída e testada** (itens 1, 2 e 9). Itens 3 (catálogo
completo) e 16 (compra Industrial→Industrial) formam a Fase 2 natural,
já que um depende do outro (o Carro só faz sentido com os dois prontos).

---

## Pendências que ainda restam

- [x] Salário máximo: resolvido, é por dia (acumulador simples)
- [x] Veículo próprio: adiado de propósito, sem sistema por enquanto
- [ ] Validar as fórmulas 🆕 propostas ao longo do documento — se eu não tiver notícia em contrário, vou tratar como aceitas quando começarmos a implementar
