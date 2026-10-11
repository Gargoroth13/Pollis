# 04 — Dia a Dia

> **Status:** FINAL — BOT TEST
>
> Este documento define o funcionamento do ciclo diário do jogador,
> incluindo Energia, QoL, Saúde, Nutrição, Burnout, Lazer e deslocamento.
>
> Parâmetros explicitamente marcados como calibráveis não representam decisões
> de balanceamento já definidas. Seus valores devem ser calibrados posteriormente
> com o Bot Test, sem exigir nova definição estrutural do sistema.

---

# 1. Visão geral

O sistema de Dia a Dia representa o conjunto de estados e ações que determinam a rotina do jogador.

Os principais sistemas são:

- Energia;
- Qualidade de Vida (QoL);
- Saúde;
- Nutrição;
- Burnout;
- Trabalho;
- Estudo;
- Lazer;
- Viagem.

Esses sistemas são interdependentes e formam uma das principais estruturas de progressão de Polis.

A regra central é que o jogador administra recursos e consequências ao decidir quantas ações realizar e como distribuir seu tempo entre trabalho, estudo, lazer, alimentação, tratamento e deslocamento.

---

# 2. Energia

Energia é o principal recurso utilizado para realizar ações.

A Energia possui:

- valor atual;
- valor máximo;
- regeneração temporal.

## 2.1 Escala e valor máximo

A Energia máxima do jogador é **100**.

A Energia não pode ficar abaixo de 0 nem acima de 100.

## 2.2 Custos de ação

Cada ação possui um custo fixo de Energia. O jogador não escolhe quantos pontos de Energia gastar em uma ação.

Custos definidos para o Bot Test:

| Ação | Custo |
|---|---:|
| Trabalhar | 20 |
| Estudar | 10 |
| Lazer | 10 |
| Tratamento | 10 |

Outras ações devem definir seu próprio custo no sistema correspondente.

Uma ação que exige mais Energia do que o jogador possui não pode ser realizada.

## 2.3 Regeneração

A Energia é regenerada ao longo do tempo e deve ser calculada de forma lazy sempre que o estado do jogador for atualizado.

A regeneração base é **5 Energia a cada 10 minutos de jogo**.

A QoL influencia essa regeneração.

Estrutura:

`regeneração = regeneração_base × (1 + modificador_de_regeneração_da_QoL)`

Onde:

- QoL = 1,00 produz modificador de 0%;
- QoL acima de 1,00 produz bônus de regeneração;
- QoL abaixo de 1,00 produz penalidade de regeneração;
- o bônus máximo é +10%;
- a penalidade máxima é -10%;
- a regeneração nunca pode ser negativa; o piso é 0.

A relação exata entre o valor da QoL e o modificador percentual dentro desses limites é um parâmetro de calibração do Bot Test.

A regeneração utiliza principalmente a QoL Base efetiva, e não a QoL Atual, para evitar que buffs temporários causem oscilações excessivas na regeneração.

---

# 3. Qualidade de Vida (QoL)

Qualidade de Vida é uma das variáveis centrais de Polis.

Ela representa as condições gerais de vida do jogador e pode influenciar a eficiência de outras atividades.

A QoL é composta por uma base estrutural e modificadores temporários.

---

# 4. QoL Base e QoL Atual

## 4.1 QoL Base

A QoL Base representa as condições estruturais da vida do jogador.

Estrutura inicial:

`QoL Base = 0,50 + modificadores estruturais`

Os modificadores estruturais são definidos pelos sistemas que fornecem cada componente.

Podem contribuir para a QoL Base, por exemplo:

- moradia;
- bens;
- condições sociais;
- localização;
- instituições;
- serviços persistentes;
- outras condições estruturais definidas por seus sistemas.

O documento 04 não define o valor de cada componente. Cada sistema responsável por um fator de QoL deve definir seu próprio modificador quando esse sistema for especificado.

**0,50 é a base estrutural do cálculo, e não uma classificação pré-definida de QoL média, alta ou baixa.**

## 4.2 QoL Base efetiva

Alguns estados temporários podem modificar a QoL Base sem alterar os fatores estruturais que a formam.

Exemplo principal:

**Burnout → penalidade temporária sobre a QoL Base efetiva.**

A QoL Base estrutural permanece preservada.

## 4.3 QoL Atual

A QoL Atual representa o estado momentâneo do jogador.

Estrutura conceitual:

`QoL Atual = QoL Base efetiva + efeitos temporários ativos`

Efeitos temporários podem vir de:

- alimentos;
- lazer;
- serviços;
- condições temporárias;
- outros sistemas.

A QoL Atual pode mudar sem alterar permanentemente a QoL Base estrutural.

## 4.4 Regra de efeitos temporários por categoria

Efeitos temporários são organizados por categoria, sejam positivos (bônus) ou negativos (penalidades).

Um jogador pode possuir no máximo **um efeito temporário ativo por categoria**, independentemente de o efeito ser positivo ou negativo.

Quando um novo efeito da mesma categoria é aplicado, **o novo efeito substitui o anterior**, qualquer que seja o sinal de cada um. O efeito anterior não é somado ao novo.

Exemplo: um novo efeito de Comida substitui o efeito anterior de Comida, seja um bônus ou uma penalidade; um novo efeito de Lazer substitui o efeito anterior de Lazer. Um efeito negativo de Comida substitui um bônus de Comida ativo, e vice-versa.

Efeitos de categorias diferentes podem coexistir.

Essa regra vale para efeitos temporários em geral (buffs e debuffs) e não apenas para QoL.

---

# 5. QoL e eficiência

QoL pode atuar como modificador de eficiência de atividades.

Conceitualmente:

`QoL maior → maior eficiência`

Isso pode afetar:

- trabalho;
- estudo;
- produção;
- outras atividades definidas por seus respectivos sistemas.

A relação exata entre QoL e eficiência é um parâmetro de calibração.

O sistema deve evitar que uma QoL elevada se torne automaticamente dominante sobre todas as outras formas de progressão.

---

# 6. Trabalho

O jogador pode realizar a ação de trabalho.

Cada ação de trabalho:

- consome 20 Energia;
- executa as regras de trabalho do sistema correspondente;
- pode desenvolver skill;
- pode gerar produção ou contribuição para uma empresa;
- aumenta Burnout conforme a regra de Burnout.

Salário, produção, cargos, requisitos e demais regras econômicas pertencem aos sistemas correspondentes.

O jogador não pode trabalhar enquanto:

- estiver em Burnout Ativo;
- estiver em Saúde Crítica;
- estiver hospitalizado;
- estiver em viagem (o Trabalho **exige** presença física no local; ver §20).

---

# 7. Burnout

Burnout representa acúmulo de esforço e exaustão.

Burnout é uma escala de **0 a 100**.

## 7.1 Ganho de Burnout

| Ação | Alteração de Burnout |
|---|---:|
| Trabalhar | +5 |
| Estudar | +3 |
| Lazer | -10 |

O sistema deve impedir valores abaixo de 0 ou acima de 100.

## 7.2 Recuperação natural

A recuperação natural de Burnout começa depois que o jogador permanece **1 hora sem trabalhar**.

Depois desse período:

**Burnout -5 a cada 10 minutos de jogo.**

A recuperação é calculada de forma lazy e não exige polling contínuo por jogador.

## 7.3 Burnout Ativo

Quando Burnout atingir **100**, o jogador entra em **Burnout Ativo**.

Histerese:

- entrada: Burnout = 100;
- saída: Burnout ≤ 50.

Durante Burnout Ativo:

- trabalho fica bloqueado;
- estudo fica bloqueado;
- lazer continua permitido;
- a QoL Base efetiva recebe a penalidade de Burnout;
- o Burnout continua podendo ser recuperado.

A penalidade de QoL causada pelo Burnout é um parâmetro de calibração.

O valor estrutural da QoL Base não é destruído nem reescrito pelo Burnout.

---

# 8. Estudo

Cada ação de Estudo:

- consome 10 Energia;
- gera progresso de estudo;
- gera o desenvolvimento de skill correspondente;
- gera +3 Burnout.

Não existe uma alocação contínua de Energia para estudo. A quantidade de estudo realizado depende da quantidade de ações de estudo executadas.

O ganho específico de skills é definido pelo sistema de Skills e Educação.

Estudar pode ser realizado enquanto o jogador trabalha no mesmo período, desde que haja Energia e nenhuma condição impeça a ação.

---

# 9. Escola e Universidade

As regras específicas de educação pertencem ao documento 03 — Escolas.

O sistema de Dia a Dia define apenas a relação da educação com a rotina:

`estudar → Energia → progresso acadêmico → Skill → Burnout`

Trabalho e estudo podem ser combinados no mesmo período.

---

# 10. Saúde

Saúde é uma variável independente, mas interligada a QoL e Nutrição.

A Saúde possui escala **0 a 100**.

A cada 10 minutos de jogo, a Saúde pode variar.

Estrutura:

`variação de Saúde = Recuperação Regional + 5 - Penalidades`

Onde:

- 5 é a recuperação base;
- Recuperação Regional é determinada pelo sistema de saúde e pelo trabalho médico realizado na região;
- Penalidades podem vir de condições do jogador, Burnout e outros efeitos definidos por sistemas próprios.

A variação final pode ser positiva, zero ou negativa.

A Saúde nunca pode ficar abaixo de 0 nem acima de 100.

---

# 11. Recuperação Regional e médicos

Hospitais são estruturas localizadas no mundo.

O trabalho dos médicos realizado durante um dia alimenta a capacidade de recuperação médica da região para o ciclo seguinte.

Fluxo:

`Dia D → médicos trabalham → trabalho médico é contabilizado → Daily Tick calcula a Recuperação Regional do ciclo seguinte.`

Durante o ciclo seguinte:

`Recuperação Regional + recuperação base de 5 - penalidades`

é utilizada para atualizar Saúde a cada 10 minutos de jogo.

A atuação médica possui limite máximo: **o componente médico pode aumentar em no máximo 30% a recuperação aplicável.**

A curva que converte trabalho médico, skill, especialização e quantidade de trabalho em eficiência médica permanece parametrizada para calibração.

O trabalho médico não gera Saúde instantaneamente no momento do clique; sua contribuição é consolidada no ciclo diário seguinte.

---

# 12. Saúde Crítica

Quando `Saúde ≤ 20`, o jogador entra em **Saúde Crítica**.

A condição utiliza histerese: `Saúde > 30` → deixa de ser crítica.

Durante Saúde Crítica:

- o jogador não pode trabalhar;
- a QoL Atual recebe um debuff;
- o jogador pode utilizar tratamento médico.

O debuff de QoL de Saúde Crítica é um parâmetro de calibração.

---

# 13. Tratamento médico

Cada tratamento consome 10 Energia.

| Pagamento | Recuperação |
|---:|---:|
| $100 | +10 Saúde |
| $200 | +20 Saúde |
| $500 | +50 Saúde |

A Saúde final nunca pode ultrapassar 100.

O pagamento é transferido para o hospital/médico responsável pelo tratamento, seguindo o sistema econômico correspondente.

---

# 14. Hospitalização

Quando `Saúde = 0`, o jogador entra em **hospitalização**.

Hospitalização é um estado distinto de Saúde Crítica.

Enquanto hospitalizado, o jogador não pode realizar as ações de **Trabalhar, Estudar e Lazer**.

A recuperação durante hospitalização utiliza as regras normais de Saúde e assistência médica.

A duração exata da hospitalização e quaisquer regras adicionais associadas permanecem parametrizadas para calibração.

---

# 15. Nutrição

Nutrição representa o estado alimentar do jogador.

A escala é **0 a 100**.

A alimentação ocorre pelo consumo de itens de comida do Inventário.

Fluxo:

`alimento → consumo → Nutrição → eventuais efeitos temporários`

Os valores individuais de Nutrição e efeitos temporários pertencem ao catálogo de Produtos e Receitas e não devem ser definidos neste documento.

Nutrição sofre alteração temporal de forma lazy.

---

# 16. Auto-consumo de alimentos

O jogador pode habilitar **Auto-consumo** no Inventário e selecionar um alimento preferido.

Quando `Nutrição < 10`, durante o processamento lazy do estado do jogador, o sistema tenta realizar o consumo automático.

Prioridade:

1. alimento preferido, se existir no Inventário;
2. caso não exista, alimento disponível com o menor ganho de Nutrição.

O sistema repete o consumo enquanto Nutrição permanecer abaixo de 10 e existir alimento elegível.

Quando Nutrição atingir ou ultrapassar 10, o consumo automático para.

Se não existir alimento elegível, nenhuma ação é executada.

O auto-consumo utiliza exatamente as mesmas regras do consumo manual.

Não existe ganho especial de Nutrição por usar o modo automático.

Os efeitos temporários da comida seguem a regra geral de categorias de buffs: um novo efeito da categoria Comida substitui o efeito anterior da mesma categoria em vez de acumulá-lo.

O sistema não deve realizar uma verificação contínua por jogador apenas para detectar fome.

---

# 17. Nutrição e Saúde

Nutrição influencia Saúde.

Conceitualmente:

`Nutrição adequada → melhores condições para manter/recuperar Saúde`

`Nutrição baixa → maior penalidade sobre Saúde`

A fórmula exata é um parâmetro de calibração.

---

# 18. Nutrição e QoL

Nutrição também pode influenciar QoL.

Nutrição inadequada pode gerar efeitos negativos.

Alimentos podem gerar efeitos temporários positivos ou negativos.

A contribuição estrutural de Nutrição para QoL e os efeitos específicos de cada alimento são definidos nos sistemas correspondentes e no catálogo de Produtos.

---

# 19. Lazer

No Bot Test, Lazer permanece deliberadamente simples.

A ação de Lazer:

- consome 10 Energia;
- reduz Burnout em 10;
- aplica um efeito temporário de QoL correspondente à atividade.

O bônus de QoL de Lazer não acumula. Uma nova aplicação da categoria Lazer substitui o efeito anterior de Lazer.

A aplicação de Lazer continua reduzindo Burnout mesmo quando já existe um buff de Lazer ativo.

Atividades elaboradas, minigames, conteúdo criado por jogadores, Cinema, Rinque e outros sistemas complexos de entretenimento ficam fora do primeiro Bot Test.

---

# 20. Viagem

Viagem representa deslocamento físico entre localidades.

A viagem utiliza o tempo de jogo e não o relógio do computador do jogador.

O jogador não pode executar ações que dependam de presença física no local de origem enquanto estiver viajando.

Quais ações dependem de presença física (decisão do Game Director):

- **Trabalho** exige presença; **Estudo** exige presença;
- **Lazer** não exige presença; **Tratamento** não exige presença;
- as demais atividades definem individualmente se exigem presença.

O bloqueio por presença ocorre **antes** de qualquer custo de Energia, ganho de skill ou outro efeito da ação.

**Nenhum estado atual impede iniciar uma viagem**: hospitalizado, Saúde Crítica e Burnout Ativo podem viajar (por exemplo, para buscar tratamento melhor). Não existem restrições físicas novas para viajar.

Viajar não aplica automaticamente uma penalidade de "dia perdido".

# 21. Distância e tempo de viagem

A distância utilizada para viagens deve ser derivada da estrutura geográfica definida em 08 — Geografia e Imóveis.

Os grids/coordenadas da geografia são a base da distância.

Regra do Bot Test:

`tempo-base de viagem = distância em grid × minutos_por_unidade`

`minutos_por_unidade` é um **parâmetro de cenário**. O valor inicial de calibração do Bot Test é **15 minutos de jogo por unidade de distância de grid**; não é um valor definitivo de balanceamento.

A Geografia fornece apenas a distância. O cálculo final de transporte/viagem aplicará os modificadores sobre o tempo-base.

A distância deve ser fornecida pela Geografia e não armazenada como atributo independente inventado no jogador.

A cidade de referência em (0,0) continua sendo apenas uma coordenada geográfica; estar distante da capital não gera automaticamente bônus ou penalidade de QoL.

Veículos, infraestrutura, estradas, transporte público e outros modificadores podem futuramente transformar o tempo base de viagem.

**Custo monetário.** Viajar custa **tempo e dinheiro**. O custo-base é proporcional à distância:

`custo-base de viagem = distância em grid × custo_por_unidade`

`custo_por_unidade` é um **parâmetro de cenário**; o valor inicial é de calibração do Bot Test, não um valor definitivo de balanceamento. Veículos e outros sistemas futuros poderão **reduzir o custo** e também **modificar o tempo** de viagem. Combustível, manutenção e transporte completo não fazem parte do Bot Test inicial.

---

# 22. Modelo temporal

O sistema utiliza o motor temporal do core.

Categorias:

- processamento lazy;
- Hourly Tick;
- Daily Tick;
- Scheduled Event;
- On Action;
- On Access.

Estados contínuos devem preferir cálculo lazy.

Devem ser preferencialmente lazy:

- regeneração de Energia;
- alteração temporal de Nutrição;
- recuperação natural de Burnout após o período de espera;
- duração de efeitos temporários;
- duração de viagens;
- outros estados contínuos.

On Action inclui:

- gasto de Energia;
- ganho de Burnout;
- redução de Burnout por Lazer;
- ganho de skill correspondente;
- consumo manual de item;
- tratamento;
- início de viagem;
- outras consequências imediatas.

Daily Tick inclui processos que dependem explicitamente da virada do dia, como consolidação do trabalho médico e cálculo da Recuperação Regional do próximo ciclo.

On Access processa o estado lazy e ticks/eventos pendentes antes de novas ações.

---

# 23. Estados e processamento determinístico

Estados interdependentes não devem ser recalculados indefinidamente em ciclos.

Para relações como:

`QoL ↔ Saúde ↔ Nutrição`

o sistema usa o estado anterior como entrada e produz um novo estado uma única vez por ciclo aplicável.

Exemplo:

`estado no início do período → calcula Saúde → calcula QoL com base no novo estado → consolida novo estado`

Não existe cadeia infinita de recalculação.

Quando múltiplos eventos possuem o mesmo timestamp, devem ser processados em ordem determinística. Dependências entre sistemas devem ser explicitamente registradas quando necessárias.

---

# 24. Estado inicial do jogador

| Estado | Valor |
|---|---:|
| Energia | 100 |
| Saúde | 100 |
| Nutrição | 100 |
| Burnout | 0 |
| Burnout Ativo | não |
| Saúde Crítica | não |
| Hospitalizado | não |
| Em viagem | não |

A QoL Atual inicial é igual à QoL Base inicial.

A QoL Base inicial segue:

`0,50 + modificadores estruturais aplicáveis`

O jogador possui localização inicial física no mundo conforme as regras de Geografia e criação do jogador.

**Decisão do Game Director:** o jogador pode começar na **capital**; não há distribuição aleatória de localização inicial. A moradia inicial é **garantida**, **básica** e **neutra em QoL**, e **não consome** capacidade de lotes residenciais nem de população. Muitos jogadores começarem na capital não é um problema de capacidade.

---

# 25. Feedback e explicabilidade

Fórmulas compostas devem seguir a regra transversal definida em 20 — Filosofia de Feedback ao Jogador.

O sistema deve preservar:

- valor final;
- componentes;
- modificadores;
- limites;
- condições.

Exemplo:

**Regeneração de Energia**

Energia regenerada: 5,25 / 10 min

Base: 5,00

QoL: +5%

O backend deve preservar os componentes estruturados; a UI escolhe como apresentá-los.

---

# 26. Relação entre sistemas

O sistema de Dia a Dia define as interações gerais.

### Trabalho

Trabalho → Energia → Skill → dinheiro/produção → Burnout

### Estudo

Estudo → Energia → progresso acadêmico → Skill → Burnout

### Alimentação

Alimento → Inventário → Consumo → Nutrição → Saúde/QoL → efeito temporário de categoria Comida

### Lazer

Lazer → Energia → Burnout -10 → buff temporário de categoria Lazer

### Saúde

Saúde → QoL → recuperação/tratamento

QoL e Nutrição → condições de Saúde

### Viagem

Geografia → distância → tempo de viagem → localização → disponibilidade de ações

O objetivo não é que todos os sistemas afetem todos os outros diretamente. Cada relação deve existir por uma justificativa de design.

---

# 27. Parâmetros de calibração

Os seguintes valores e curvas são deliberadamente mantidos parametrizados para calibração do Bot Test.

## Energia

- relação exata entre QoL e o modificador percentual dentro do limite de ±10%;
- custos de outras ações ainda não definidos;
- quaisquer custos de viagem futuros.

## QoL

- modificadores individuais de Moradia;
- modificadores de Bens;
- modificadores de Condições Sociais;
- modificadores de outros sistemas estruturais;
- modificadores temporários específicos;
- relação QoL → eficiência;
- penalidade de QoL do Burnout;
- debuff de QoL de Saúde Crítica.

## Saúde

- fórmula de Recuperação Regional a partir do trabalho médico;
- contribuição de skill e especialização dos médicos;
- forma da curva até o limite máximo de +30%;
- penalidades específicas de Saúde;
- contribuição de Nutrição;
- duração e regras adicionais de hospitalização.

## Burnout

- efeitos quantitativos sobre QoL;
- efeitos adicionais de condições futuras.

## Nutrição

- taxa temporal de alteração;
- ganhos de Nutrição por alimento;
- efeitos temporários de alimentos.

Esses parâmetros não precisam ser definidos antes do Bot Test quando a estrutura da mecânica já estiver fechada.

A calibração deve utilizar observação de comportamento e dados dos Bots em vez de valores arbitrários escolhidos apenas para preencher a especificação.

---

# 28. Fora do escopo do Bot Test

Não fazem parte da implementação inicial deste documento:

- sistemas de lazer elaborados;
- Cinema;
- Rinque;
- minigames de lazer;
- conteúdo complexo criado por jogadores;
- transporte público detalhado;
- trânsito;
- estradas detalhadas;
- veículos com modificadores avançados;
- sistemas médicos complexos;
- doenças individualizadas;
- modelagem nutricional detalhada.

Esses sistemas podem utilizar a estrutura criada pelo Dia a Dia futuramente sem alterar seu núcleo.

---

# 29. Princípios de implementação

1. Estados contínuos devem preferir cálculo lazy.
2. Ações possuem custos de Energia definidos por ação, não por alocação manual.
3. O documento 04 não deve inventar parâmetros pertencentes a outros sistemas.
4. Buffs temporários da mesma categoria substituem o efeito anterior em vez de acumular.
5. Relações entre estados interdependentes devem produzir um novo estado uma única vez por ciclo aplicável.
6. Fórmulas compostas devem retornar valor + detalhamento estruturado.
7. O tempo de jogo é a referência temporal de todas as regras, inclusive no Bot Test.
8. Parâmetros de balanceamento que ainda não possuem base empírica devem permanecer calibráveis.
