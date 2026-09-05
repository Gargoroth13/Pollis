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

### 2.8 Financeira — detalhamento da especialização ✅ (implementado, exceto bolsa de valores e intervenção do governo)

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


---

## Correções de hoje

### Fundar empresa tem custo, escalado por tipo

Fundar é objetivo de fim de jogo, não algo trivial. Proposta de custo:

| Tipo | Custo |
|---|---|
| Varejo | R$ 15.000 |
| Serviços (Transporte/Publicidade/Lazer) | R$ 25.000 |
| Matriz | R$ 40.000 |
| Construtora | R$ 60.000 |
| Industrial | R$ 80.000 |
| Serviços (Financeira) | R$ 100.000 |

Depois, diploma de **Administração Empresarial** também vira
pré-requisito — mas só entra quando Escola/Universidade existirem de
verdade (03-escolas.md).

### Cargo "Dono" automático

Ao fundar, cria um `Cargo` "Dono" com o fundador como ocupante e
salário definido por ele mesmo. Dono passa a clicar "trabalhar no
emprego" igual funcionário comum pra receber.

Um jogador pode ser dono de uma empresa **e** funcionário contratado
de outra ao mesmo tempo — o cargo "Dono" da própria empresa não conta
pro limite de "só um cargo contratado por vez".

### Produção: só o dono escolhe o quê

Funcionário não escolhe mais o produto ao clicar produzir/fabricar —
só o dono define "o que a empresa está produzindo agora"; funcionário
só contribui clicando.

### Especialização mais lenta

`GANHO_DE_ESPECIALIZACAO_POR_ACAO` cai de 2 pra 1 (dobra o tempo até
nível 100).

### Vagas de emprego (mural público)

Precisa de uma página listando todos os `Cargo` vagos de todas as
empresas. Candidatura exige aprovação do dono (ou sócio, quando
sociedade existir — 10-futuro.md).

⚠️ **Pendência aberta**: você mencionou a interface *atual* de
Matriz/Industrial/Varejo como parte do que precisa arrumar — preciso
que descreva especificamente o que parece faltando aí, porque no
código essas 3 já têm estoque, compra entre empresas e venda desde a
Fase 2.
