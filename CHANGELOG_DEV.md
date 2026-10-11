# Polis — CHANGELOG DEV

Registro das decisões importantes de design e desenvolvimento que precisam permanecer visíveis para os agentes.

---

## 2026-10-11 — Produtos, Receitas e usos (P1.01)

### Escopo
- **Implementado:** app `catalog` — `Product`, `Recipe`, `RecipeInput` e `FoodProfile` com **identificadores estáveis**, carga **idempotente e atômica** (`sync_catalog`), ligação com os **recursos da Geografia**, **consultas derivadas** (receita, usos, consumidores, matérias-primas transitivas), **relatório de integridade** com códigos estáveis (`check_catalog`) e testes.
- **Fora, como pedido:** inventário (P1.02), empresas e produção (P1.04), mercado e preços (P1.05), veículos. Nenhum desses sistemas foi tocado; `players`, `geography` e `travel` não mudaram.
- **Fonte:** o `design/22-Receitas-Produção.md` **atual**, que o Game Director declarou **não ser um catálogo completo nem definitivo**. Entrou **somente** o que ele declara: **73 produtos** = 29 matérias-primas (10 Agropecuária, 10 Extrativismo, 9 Mineração), **41 receitas** (12 Produção, 7 Alimentícia, 15 Bens de consumo, 4 Tecnológica, 3 Milícia) e 3 produtos militares do Exército (sem receita, comprados pelo governo). O `22` **não foi editado**.

### Decisões do Game Director (2026-10-11) aplicadas
1. **Completude:** nada foi inventado (receitas, usos comerciais, quantidades, atributos). As lacunas conhecidas estão registradas abaixo, com `código`, quem as cita e **quais etapas dependem delas**; também vivem no código (`catalog.definitions.KNOWN_GAPS`) e saem como pendência de design em `check_catalog`. Um teste exige que cada código esteja neste arquivo.
2. **Normalização de nomes** quando é claramente a mesma entidade. **Identidade = `key`** (slug estável, independente do nome; o `save` recusa mudar a `key`; renomear só muda o `name`). As variantes como aparecem no `22` ficam em `Product.source_names`, e um teste lê o `22` e confere o catálogo contra ele (se o arquivo mudar, o teste obriga a atualizar). Normalizações realizadas:

| `key` | Nome de apresentação | Variantes no `22` |
|---|---|---|
| `shoes` | Calçados | Calçado, Calçados |
| `eggs` | Ovos | Ovo, Ovos |
| `chemicals` | Químicos | Químico, Químicos |
| `hospital_supplies` | Materiais hospitalares | Materiais hospitalares, Materiais Hospitalares |
| `coffee_bean` | Grão de café | Grão de café, Grão de Café |

   **Distinções preservadas:** o "Kit Médico" da **milícia** (`militia_medical_kit`, nome de apresentação "Kit médico (milícia)") e os "Kits médicos" do **Exército** (`military_medical_kits`, "Kits médicos militares") são entidades **diferentes** (origem diferente); o qualificador no nome é só para não colidirem. As chaves dos 10 recursos espaciais são os valores de `geography.constants.Resource` (`oil`, `iron`, ...).
3. **Matéria-prima sem uso e produto sem consumidor** (Diamante, Prata, Látex, Resina, Óleo natural; e 17 produtos sem uso declarado) carregam normalmente e saem como **pendência de design**, **não** como erro. **Nenhuma permissão de compra/venda é inferida**: `uses_of` devolve só usos declarados (insumo de receita; consumo como alimento) e lista vazia significa nenhuma permissão. Erro (impede a carga): referência quebrada, chave duplicada, ciclo, inconsistência estrutural.
4. **Valores numéricos não inventados:** quantidade de insumo, rendimento, ganho de Nutrição, intensidade de QoL e estrela das Matrizes ficam **não especificados** (`NULL`/`None`), **distintos de zero**: o modelo e o relatório os distinguem (zero é um valor especificado; `NULL` nunca é lido como zero). Quem precisa deles **recusa** com `UNSPECIFIED_DESIGN_VALUE` e a lista do que falta (`check_production_ready`, `check_consumption_ready`), em vez de prosseguir em silêncio. Hoje **nenhum produto está pronto para produção e nenhum alimento para consumo**: é o comportamento correto, e muda sozinho quando o design especificar os valores. Nenhum `[PROV]` foi escolhido.

### Interpretações técnicas (reversíveis; não são regra de gameplay)
5. **Uma receita por produto** (como no `22`); se o design admitir receitas alternativas, a relação muda.
6. **Usos são derivados, não armazenados:** insumo de receita (a partir de `RecipeInput`) e consumo como alimento (a partir de `FoodProfile`). Não há tabela de "usos" paralela: usos comerciais novos entram quando o design os declarar (ver `GAP_COMMERCIAL_USES_UNDECLARED`).
7. **Restrições de banco:** quantidade e rendimento, quando especificados, são **> 0**; Nutrição e intensidade **>= 0** (a intensidade é uma magnitude: o sentido vem de `qol_effect`, inclusive `debuff`); estrela entre 1 e 5. Zero em quantidade/rendimento é recusado por ser sem sentido; o design não diz o contrário.
8. **Estrela:** `NULL` significa "não especificada" (Matrizes) ou "não se aplica" (milícia — o `22` diz "Não existe" — e compra do governo); é erro (`STARS_NOT_APPLICABLE`) dar estrela a esses últimos.
9. **Níveis de Nutrição e tipos de efeito de QoL são os qualitativos do `22`** ("nada", "quase nada", "pouca", "média", "bastante"; "sem efeito", "pequeno buff", "buff médio", "debuff"), **sem ordem numérica** definida.
10. **A carga nunca apaga Produto** (inventário e estoque vão referenciá-lo); um produto no banco sem definição aparece como erro `PRODUCT_NOT_IN_DEFINITIONS`. A carga é por comando (`sync_catalog`, como `generate_world`), não automática em migração; testes carregam o catálogo por classe.
11. **Dependência de `players`:** só do tipo `ActionResult` (recusas como código, padrão do projeto).

### Relatório de integridade (`check_catalog [--pending]`)
- **Erros:** `DUPLICATE_KEY`, `DUPLICATE_RESOURCE_LINK`, `INGREDIENT_NOT_FOUND`, `DUPLICATE_INPUT`, `RAW_WITH_RECIPE`, `PROCURED_WITH_RECIPE`, `PRODUCED_WITHOUT_RECIPE`, `RECIPE_CYCLE`, `INVALID_QUANTITY`, `INVALID_YIELD`, `INVALID_STARS`, `STARS_NOT_APPLICABLE`, `INVALID_FOOD_VALUE`, `RESOURCE_ON_NON_RAW`, `RESOURCE_UNKNOWN`, `RESOURCE_SECTOR_MISMATCH`, `RESOURCE_WITHOUT_PRODUCT`, e, contra o `22`: `EMPTY_CATALOG`, `CATALOG_NOT_SYNCED`, `PRODUCT_NOT_IN_DEFINITIONS`, `PRODUCT_DIFFERS_FROM_DEFINITIONS`.
- **Pendências de design (nunca reprovam):** `RAW_MATERIAL_WITHOUT_USE` (5), `PRODUCT_WITHOUT_DECLARED_USE` (17), `RECIPE_QUANTITIES_UNSPECIFIED` (41), `RECIPE_YIELD_UNSPECIFIED` (41), `MIN_STARS_UNSPECIFIED` (29), `FOOD_NUTRITION_UNSPECIFIED` (7), `FOOD_QOL_INTENSITY_UNSPECIFIED` (7) e as lacunas globais abaixo.

### Lacunas conhecidas do `22` (rastreabilidade; **não resolvidas**)
| Código | Lacuna | Citada em | Bloqueia |
|---|---|---|---|
| `GAP_FINISHINGS_UNDEFINED` | **Acabamentos** (insumo da Construtora) não existe no `22` | `02 §2.5` | P1.04, P1.07 |
| `GAP_OPERATIONAL_MATERIALS_UNDEFINED` | **Materiais operacionais** e consumo por funcionário não definidos | `02 §10`, `§20` | P1.04 |
| `GAP_MATRIZ_STARS_UNDEFINED` | **Estrelas das Matrizes** (matérias-primas) não definidas | `02 §5.2`, `§14` | P1.04 |
| `GAP_PRODUCTION_QUANTITIES_UNDEFINED` | quantidade por insumo, rendimento, quantidade produzida por trabalho | `02 §5` | P1.04, P1.05 |
| `GAP_FOOD_VALUES_UNDEFINED` | ganho de Nutrição e intensidade de QoL numéricos (e base do auto-consumo "menor ganho") | `04 §15-16`, `05 §6` | P1.02 |
| `GAP_FOOD_PROFILE_BREAD_UNDECLARED` | Pão tem Nutrição/QoL "—" mas é insumo do Hambúrguer: é consumível? | `22 §2.3` | P1.02 |
| `GAP_COMMERCIAL_USES_UNDECLARED` | usos/consumidores comerciais ausentes; permissão de compra/venda **não** é inferida | `02 §4`, `§20` | P1.04, P1.05 |
| `GAP_INVENTORY_CATEGORIES_UNDEFINED` | categorias de inventário e itens permanentes x consumíveis | `05 §3`, `§22` | P1.02 |
| `GAP_BASE_PRICE_UNDEFINED` | `preco_base`/valor de referência do item (taxa do correio) | `17 §20`, `05 §12` | P1.02, P1.05 |
| `GAP_VEHICLE_RELATION_UNDEFINED` | produto Carro x veículo ativo/viagem (veículos adiados) | `04 §21`, `05 §9` | sistema de veículos (futuro) |

### Pendências registradas por etapa (decisões do Game Director a fechar **antes** de cada uma)
- **P1.02 — Inventário:** `GAP_FOOD_VALUES_UNDEFINED` (Nutrição e intensidade numéricas; ordenação para o auto-consumo), `GAP_FOOD_PROFILE_BREAD_UNDECLARED`, `GAP_INVENTORY_CATEGORIES_UNDEFINED`, `GAP_BASE_PRICE_UNDEFINED` (taxa de correio). **Se a implementação depender de números, consultar o GD antes de escolher valores `[PROV]`.**
- **P1.04 — Empresas:** `GAP_FINISHINGS_UNDEFINED`, `GAP_OPERATIONAL_MATERIALS_UNDEFINED`, `GAP_MATRIZ_STARS_UNDEFINED`, `GAP_PRODUCTION_QUANTITIES_UNDEFINED`, `GAP_COMMERCIAL_USES_UNDECLARED`. A produção deve usar `catalog.services.check_production_ready` e **recusar** enquanto houver `UNSPECIFIED_DESIGN_VALUE`. **Consultar o GD antes de escolher `[PROV]`.**
- **P1.05 — Mercado:** `GAP_BASE_PRICE_UNDEFINED`, `GAP_PRODUCTION_QUANTITIES_UNDEFINED`, `GAP_COMMERCIAL_USES_UNDECLARED`. **P1.07:** `GAP_FINISHINGS_UNDEFINED`.

### Observações sobre o `22` (sem alteração do arquivo)
- O arquivo não tem cabeçalho nem status, e a §2.3 vem antes da §2.2; o texto diz "4 sub-tipos" de Industrial e lista Milícia à parte (tratada como setor próprio, sem estrela).
- 5 matérias-primas e 17 produtos sem uso declarado: ver pendências acima. O Pão pode não ser um alimento por omissão.

### Testes
106 testes novos em `catalog` (582 no total): definições válidas e **fiéis ao `22`** (parser do arquivo), cada código de erro e de pendência, ciclos (autorreferência, 2 e 3 elos, grafo real, losango que **não** é ciclo), erro x pendência, carga idempotente/atômica/identidade estável, restrições de banco (zero x `NULL`), usos derivados sem permissão inferida, recusas `UNSPECIFIED_DESIGN_VALUE`, ligação com a Geografia, deriva banco x definições e comandos. **Mutação:** 27 mutantes nas regras do catálogo (validação, carga, serviços, integridade, chave permanente); 3 sobreviveram na primeira rodada (remoção de receita, rendimento ignorado, zero tratado como não especificado) e ganharam teste; todos mortos.

### Como usar
`python manage.py sync_catalog` (carrega, idempotente) e `python manage.py check_catalog [--pending]`. Serviços em `catalog.services`: `recipe_of`, `uses_of`, `consumers_of`, `raw_materials_of`, `product_for_resource`, `food_of`, `check_production_ready`, `check_consumption_ready`.

---

## 2026-10-06 — Localização do jogador e viagem básica (P0.06.1)

### Escopo
- **Implementado:** lote de localização atual, localização inicial válida, viagem entre lotes, distância derivada da Geografia, tempo-base `distância × travel_minutes_per_unit` (15 inicial), estado de viagem, conclusão pelo sistema de tempo, bloqueio de ações incompatíveis, testes.
- **Fora, como pedido:** veículos (apenas o ponto de extensão para modificadores), transporte público, imóveis/propriedade, residência (o `05` "Residência ativa" é conceito distinto da localização e **não** foi tocado).
- Cumpre duas pendências anteriores: o **vínculo de localização do jogador** (registrado na aprovação do P0.06) e o **bloqueio de Trabalho por Viagem** (`04 §6`, pendente desde o P0.04).

### Decisões do `04` implementadas
1. **Localização** (`04 §24`): todo jogador tem um lote (`PlayerLocation`). Em viagem, o lote continua sendo o de **origem**; a chegada o atualiza.
2. **Viagem** (`04 §20`): `Journey` com origem, destino e instantes em **tempo de jogo**; **no máximo uma ativa** por jogador (restrição no banco), concluídas ficam como histórico.
3. **Tempo-base** (`04 §21`, corrigido em 2026-10-03): `distância × minutos_por_unidade`, parâmetro de **cenário da Geografia** (`travel_minutes_per_unit`, 15 como valor inicial de calibração). Devolvido com **detalhamento estruturado** (doc 20): componentes `distance` e `minutes_per_unit`, aos quais futuros modificadores são aplicados como novos passos. O custo monetário segue o mesmo formato (ver decisão 4 abaixo).
4. **A distância não é guardada** (`04 §21`): a viagem não tem coluna de distância nem de duração; vem sempre da Geografia. Mudar o parâmetro depois **não altera** uma viagem em curso (`arrives_at` é fixado na partida).
5. **Bloqueio** (`04 §6`, `§20`): durante a viagem o jogador não executa ação que **dependa de presença física** (Trabalho e Estudo; ver decisão 2 abaixo); a recusa é um **código** (`TRAVELING`), sem custo de Energia e sem ganho de skill. **Humano e Bot usam o mesmo caminho** (`players.services.perform_action`).
6. **Conclusão pelo sistema de tempo**: o handler do ciclo de 10 min conclui a viagem no primeiro ciclo após a chegada (ciclos posteriores já veem o jogador no destino, em ordem) **e** o hook de acesso (On Access, `04 §22`) a conclui no **instante exato** entre ciclos. Ambos levam ao mesmo estado final; **acessar a mais nunca muda o resultado** (testado por propriedade). Cada um é necessário (testado removendo o outro).

### Integração com o P0.04/P0.05 (aditiva)
- `players.hooks`: `ActivityContext.requires_presence`, **provedores de bloqueio** (um sistema acrescenta motivos de recusa a `perform_action` e ao snapshot) e **hooks de acesso** (rodam ao fim do catch-up).
- `players.services.locked_player`: sessão pública (transação + trava + catch-up + save) para serviços de outros sistemas, sem duplicar a lógica de `perform_action`.
- `CycleContext.cache`: um handler consulta o banco **uma vez por catch-up**, não a cada ciclo (testado contando consultas: ~288 ciclos custam um número constante).
- **`create_player` agora exige um mundo** (`WorldNotGenerated`): sem lote não existe localização válida, e a criação falha **inteira** (transação). Consequência: **186 testes do P0.04/P0.05 criavam jogador sem mundo**; a infraestrutura de teste passou a gerar um mundo pequeno **uma vez por classe**. Nenhuma asserção de regra mudou; a única asserção alterada foi a do P0.04 que exigia que o `cycle` fosse o *único* handler do ciclo (agora o `cycle` é o **primeiro**, e a viagem soma o seu).
- **Custo (medido, mesma máquina, 198 testes de `players`+`skills`):** ~40 s na `main` contra ~50 s na branch (+25%), por consultas adicionais da viagem em cada catch-up (número constante por catch-up, testado).

### Decisões finais do Game Director (revisão de 2026-10-07; substituem os 3 pontos `[ABERTO]` anteriores)
Nenhuma é mais `[ABERTO]`. Os pontos de configuração antigos (`POLIS_TRAVEL_BALANCE`: `presence_dependent_by_default` e `travel_blocking_states`) **foram removidos** (`travel/balance.py` deixou de existir): deixaram de ser decisões em aberto.
1. **Localização inicial.** O jogador pode começar na **capital** (primeiro lote territorial da cidade capital do primeiro estado, em ordem determinística; sem capital definida ou sem lotes, o primeiro lote do mundo). **Sem distribuição aleatória**. A **moradia inicial** é garantida, básica, neutra em QoL e **não consome** capacidade residencial normal nem de população: muitos jogadores na capital não são problema de capacidade. Isto é só uma **regra**: não existe sistema de residência/propriedade nem spawn sofisticado (o hook `register_initial_location_provider` continua existindo como extensão futura).
2. **Presença física por ação** (regra fixa, `travel.rules.PRESENCE_BY_ACTION`): **Trabalho exige; Estudo exige; Lazer não; Tratamento não**; as demais atividades definem individualmente (`ActivityContext.requires_presence`). Em viagem, ação que exige presença é recusada (`TRAVELING`) **antes** de Energia, skills ou qualquer efeito.
3. **Nenhum estado impede iniciar viagem**: hospitalizado, Saúde Crítica e Burnout Ativo podem viajar (intenção: viajar em busca de tratamento melhor). Nenhuma restrição física nova foi inventada.
4. **Viagem custa tempo e dinheiro.** Tempo: `distância × travel_minutes_per_unit` (15, inalterado). Custo: `distância × travel_cost_per_unit`, parâmetro de **cenário da Geografia**, com **valor provisório 10 `[PROV]`**: é calibração do Bot Test, **não** balanceamento definitivo. Ambos retornam detalhamento estruturado (doc 20). A arquitetura aceita **modificadores futuros** de veículos (reduzir custo, alterar tempo): `register_travel_modifier` (fatores multiplicativos, passos `modifier:<nome>` no detalhamento). **Não implementados:** veículos, combustível, manutenção, transporte público ou transporte completo (nenhum modificador é registrado hoje).

### Interpretações técnicas (reversíveis; não alteram regra de gameplay)
5. **Não existe sistema de dinheiro** (nem saldo no `Player`). O custo é **calculado e registrado** em `Journey.cost`, e entregue ao sistema de dinheiro por um **ponto de integração**: `register_payment_handler(nome, fn(player, valor, contexto) -> bool)`. Sem handler, a viagem parte e `Journey.charged = False` (custo registrado, **não cobrado**; resultado `payment = NO_PAYMENT_SYSTEM`); com handler, saldo insuficiente recusa com `INSUFFICIENT_FUNDS` **sem criar viagem** (atômico). Nenhum dinheiro é criado ou destruído aqui (`CLAUDE.md` §5.2). Consequência a decidir quando o sistema financeiro existir: **hoje a viagem não custa dinheiro efetivo no jogo**.
6. **Arredondamento do custo:** calculado em `Decimal` exato; o valor **cobrado/registrado** é arredondado a centavos (2 casas, arredondamento bancário). `Journey.cost` e `arrives_at` são **fixados na partida** (mudar os parâmetros depois não altera viagem em curso).
7. **Tempo:** segundos de jogo inteiros **para cima** (a viagem nunca chega antes do calculado), mínimo de 1 s.
8. **Sem posição intermediária, sem cancelar nem redirecionar** viagem em curso; **qualquer lote para qualquer lote**, exceto o próprio (`SAME_LOCATION`).
9. O `04 §20` fala em presença "no local de **origem**": o bloqueio vale durante **toda** a viagem.
10. **Tabela fixa de presença:** uma atividade que **contradiz** a regra da ação (ex.: `requires_presence=False` em Trabalho) é **erro de programação** (`ValueError`), não escolha silenciosa; ação sem regra fixa e atividade sem declaração também é erro. `treatment` já consta da tabela, mas ainda **não é uma `Action`** (depende do sistema de dinheiro, ver pendências do P0.04).
11. **Dependência da fila:** o `TASK_QUEUE` citava "`03 — Sistema de tempo`", mas o `03` é *Escolas*; a fundação temporal é o **P0.03** (`core`). Corrigido na fila.

### Parâmetros
`travel_minutes_per_unit` = 15 (calibração, decisão de 2026-10-03, inalterado). **Novo:** `travel_cost_per_unit` = 10 `[PROV]` (cenário `geography.balance`; validado `>= 0`). Nenhuma outra configuração nova; as duas antigas de `travel` foram removidas.

### Preservado (o que a auditoria apontou como correto)
`PlayerLocation`; no máximo uma viagem ativa por jogador (restrição no banco); distância sempre da Geografia; `arrives_at` fixado na partida; conclusão preguiçosa por ciclo + hook de acesso; bloqueio de presença antes de Energia/skills; mesmo caminho para humano e Bot; atomicidade e determinismo; cache do catch-up; testes existentes.

### Pendência documental (não bloqueadora; registrada após o merge do P0.06.1)
- **Frase obsoleta na seção do P0.06 (2026-10-03, "Escopo"):** diz que o bloqueio de Trabalho por Viagem "continua pendente". Ele foi implementado no P0.06.1. Não corrigida de propósito, para não ampliar o escopo do merge; corrigir numa **limpeza documental posterior**. Valem as seções do P0.06.1 e da lista de pendências do P0.04 (já marcada como implementada).
- **Lembrete:** `travel_cost_per_unit` = 10 segue **`[PROV]`** (calibração do Bot Test, não balanceamento) e a **cobrança efetiva** do custo da viagem depende da futura integração com o sistema financeiro (`register_payment_handler`); hoje `Journey.charged = False`.

### Sugestões (**NÃO implementadas**)
- Quando o sistema de dinheiro existir, registrar o handler de pagamento (hoje o custo não é cobrado).
- Quando existirem veículos, registrar um modificador de viagem; o sistema de Empresas/cargos deve informar `requires_presence` por cargo (`04 §6`).

---

## 2026-10-03 — Geografia (P0.06) sobre o `08` (FINAL)

### Escopo
- **Implementado:** o `08` (hierarquia, coordenadas, bairros, lotes, capacidades, zoneamento-base, áreas rurais, recursos espaciais).
- **Fora, de propósito:** o `10` (propriedade, leilões, "lotes começam do governo", imóveis) é do **P1.07**. **Veículos e modificadores de viagem** são do sistema de viagem/transporte. A Geografia fornece **a distância** e o **tempo-base** (`distância × minutos_por_unidade`, `04 §21`); o bloqueio de Trabalho por Viagem, pendente desde o P0.04, **continua pendente**.

### Decisões do `08` implementadas
1. **Estado → Cidade → Bairro → Lote**, cada nível com coordenadas X/Y; a **distância é sempre derivada** das coordenadas (nenhum atributo "distância até a capital", `08 §17`). Cada estado tem uma capital que pertence a ele.
2. **25 bairros por cidade** (`§3.1`), **concentrados** em torno de uma região central (quantis de Rayleigh + ângulo áureo: espiral, sem grade uniforme e sem aleatoriedade). **Sem classe social** de bairro (`§4`).
3. **6 categorias de lote** e **capacidades base** 50 / 30 / 20 / 5 / 10 (residencial, comercial, industrial, institucional, especial); **rural** sem valor fixo ("definida pela estrutura territorial"). Lotes **começam vazios** (`10 §2`); o estado de ocupação existe, as transições são do P1.07.
4. **Zoneamento** parametrizável (`§16`): por padrão cada categoria só admite o próprio uso; **ponto de extensão** para leis/projetos alterarem permissões. O sistema imobiliário deve **consultar** este módulo (`10 §22`).
5. **Recursos**: 9 minerais com as raridades do `§15` e **petróleo exclusivamente em Extrativismo** (`§12`). Distribuição **espacial concentrada** (campo de concentrações regionais, não sorteio independente por lote, `§13`): há regiões ricas e regiões sem ocorrência, e a **frequência global é exata** (`§23.3`).
6. **Cenário parametrizado** (`§19`): seed, tamanho do mundo e demais valores são do cenário, não regra permanente. Geração **determinística**, **atômica** e que **nunca sobrescreve** um mundo existente. Comandos `generate_world` e `check_world`.
7. **Integridade territorial** com relatório estruturado (códigos estáveis): estado sem cidade/capital, capital de outro estado, nº de bairros, plano de tipos, composição e índices dos lotes, sobreposição de coordenadas, depósito fora de lote rural, frequência de recursos. Valida o mundo **contra o cenário em vigor**.

### Decisões do Game Director sobre Geografia (2026-10-03)
Fecham o que estava como `[ABERTO]` ou como interpretação minha. **Não há decisão de design aberta no P0.06.**
1. **Composição dos lotes: leitura A.** Cada bairro tem um **tipo predominante** e a quantidade de lotes da capacidade **daquele tipo**. A leitura B (todas as categorias em todos os bairros) está **descartada**. *Implementação:* a opção `lot_composition` foi **removida** (passá-la é erro de configuração). **Quantos bairros de cada tipo** existem nas 25 posições de uma cidade **segue como configuração provisória de cenário** (`neighborhood_type_counts`), para não transformar uma escolha do Bot Test em regra do jogo.
2. **Distância: euclidiana como padrão.** *Implementação:* `distance_metric` continua uma configuração do cenário (para calibração), com `euclidean` como padrão.
3. **Usos relativamente separados:** a **mistura é permitida conforme o zoneamento**; **não há regra rígida de distância entre tipos de uso**. Restrições de distância virão de leis/zoneamento quando esse sistema existir. *Implementação:* a decisão de zoneamento de um lote depende **só do lote e do uso** (testado: mudar a vizinhança não a altera). A matriz de permissões segue parametrizável; sem outras regras, cada categoria admite o próprio uso, e as misturas entram por essa matriz ou por overrides de lei.
4. **Recursos naturais concentrados em lotes rurais:** interpretação confirmada.
5. **Capital estadual:** a primeira cidade do estado no cenário padrão, **como configuração/interpretação do cenário, não regra universal**. *Implementação:* deixou de ser fixa no gerador e virou `Scenario.capital_city_index` (padrão 0; a integridade só exige que a capital pertença ao estado).
6. **Escala espacial e tempo de viagem.** A escala espacial (`city_radius`, `state_spacing`, `city_spacing`, `lot_spacing`) **não foi alterada** e fica registrada como **parâmetro de cenário/calibração do Bot Test**. **Correção do Game Director:** o tempo-base de viagem é `distância × minutos_por_unidade`, com **15 minutos por unidade** como valor **inicial de calibração** (não balanceamento definitivo), em vez dos 40 minutos que o `04 §21` trazia. *Implementação:* `Scenario.travel_minutes_per_unit` (padrão 15) e `services.base_travel_minutes`. **O texto do `04 §21` foi atualizado** para a fórmula parametrizada. Veículos e seus modificadores **não** foram implementados: o cálculo final de viagem poderá aplicá-los depois sobre o tempo-base.

### Interpretações técnicas (reversíveis; **confirmar**)
1. ~~**Recursos só em lotes rurais.**~~ **Confirmada pelo Game Director (2026-10-03)** (decisão 4).
2. **Raridade = fração global dos lotes rurais** que têm o depósito (arredondada ao lote). O `§15` avisa que não é "necessariamente probabilidade literal independente".
3. Um lote pode ter **vários recursos**; `richness` (0,001 a 1) é o tamanho **relativo** ao lote mais rico daquele recurso. A conversão para quantidades pertence a Produtos/Empresas (`22`).
4. ~~**Capital estadual = primeira cidade do estado.**~~ **Confirmada como configuração do cenário** (decisão 5): `capital_city_index`.
5. **Cidade de referência em (0,0)** (`04 §21`) = primeira cidade do primeiro estado; é só uma coordenada de layout, **sem bônus nem penalidade**, e **independente** de qual cidade é a capital.
6. **Não há entidade "País" nem "capital nacional"** (`08 §2` a cita só na distância; é assunto político, `06`).
7. O algoritmo de recursos (concentrações gaussianas sorteadas com seed, escolha dos lotes de maior valor) é **minha escolha**: o `08` exige o comportamento, não o método. Idem o layout em espiral.
8. Coordenadas com 3 casas decimais, para o mundo não depender do último bit do ponto flutuante.
9. A "capacidade" do bairro é **derivada** dos lotes existentes, nunca guardada em duplicidade.

### Pendências registradas na aprovação do P0.06 (nenhuma corrigida agora, por decisão do Game Director)
1. **Portabilidade de floats nos depósitos.** A distribuição de recursos usa ponto flutuante (campo gaussiano e ordenação por valor); o resultado é determinístico na **mesma plataforma**, mas pode diferir no último bit entre máquinas/builds diferentes e, em empates próximos, mudar quais lotes recebem o depósito. O layout espacial já é protegido por arredondamento a 3 casas. **Adiado** até haver Bot Test multi-máquina/distribuído.
2. ~~**Vínculo de localização do jogador — REQUISITO para o bloco de Imóveis (P1.07) e para o sistema de Viagem; não implementado.**~~ **Cumprido no P0.06.1** (2026-10-06); resta a **residência/moradia** (`05`), do P1.07. Hoje o `Player` não tem posição. Será preciso: onde o jogador está/reside (lote/bairro), o estado "em viagem" e o destino. Dele dependem o **bloqueio de Trabalho por Viagem** (`04 §6`, `§20`, pendente desde o P0.04), moradia/QoL estrutural e o tempo de viagem sobre o tempo-base de `geography.services.base_travel_minutes`. A Viagem **não tem bloco próprio na fila**: precisa ser priorizada.
3. **Comentários de teste `[ABERTO]`.** Restam 2 comentários em testes que ainda usam essa marca para decisões já fechadas. **Limpeza futura**, sem efeito em comportamento.

### Parâmetros de cenário `[PROV]` (o `08 §19`: mapa de teste não é regra permanente)
Em `geography/balance.py`, sobrescrevíveis por `POLIS_GEOGRAPHY`. O doc não fornece nenhum deles:

| Parâmetro | Valor | Observação |
|---|---|---|
| `states` / `cities_per_state` | 2 / 2 | mundo padrão: 4 cidades, 100 bairros, **3420 lotes** |
| `neighborhood_type_counts` | institucional 3, comercial 5, residencial 10, especial 1, industrial 3, rural 3 | soma 25; só vale na leitura A |
| `type_order_from_center` | institucional → comercial → residencial → especial → industrial → rural | centro para a periferia |
| `rural_lots_per_neighborhood` | 40 | `§6`: "definida pela estrutura territorial" |
| `state_spacing` / `city_spacing` / `city_radius` / `lot_spacing` | 20 / 6 / 1,5 / 0,01 | unidades de grid |
| `hotspots_per_resource` / `hotspot_sigma` | 3 / 2 | concentrações regionais |
| raridade do **petróleo** | 3% | o `08 §14` só diz "raro" e remete a Produtos |
| `seed` | 1 | |
| `capital_city_index` | 0 | índice da cidade-capital em cada estado (decisão 5) |
| `travel_minutes_per_unit` | 15 | valor **inicial de calibração** do Bot Test (decisão 6), não definitivo |

### Observações e sugestões (**NÃO implementadas**)
- **Escala:** a escala espacial foi **mantida** (decisão 6). Com `city_radius` 1,5 e 15 min por unidade, ir do centro à borda de uma cidade leva ~22,5 min, e entre bairros opostos até ~45 min; entre cidades do mesmo estado (`city_spacing` 6), ~90 min. São números de **calibração do Bot Test**, não regra.
- **Raridade × geografia:** a frequência é calculada sobre os lotes **rurais**. Se o mundo tiver poucos lotes rurais, os recursos raros (diamante 1%) podem sair com 0 ou 1 depósito.
- **Sugestão:** a fixar quando o design definir: quantos bairros de cada tipo existem por cidade (hoje `[PROV]`, decisão 1).

---

## 2026-10-02 — Skills (P0.05) sobre o `01` (REVIEW)

**Princípio:** o `01` está em REVIEW. Foi implementado **somente o que ele já estabelece**. Onde o documento diz que algo será definido/calibrado, há um parâmetro ou um ponto de extensão **neutro**; nenhum exemplo conceitual virou regra. As regras do `04` (P0.04) não foram alteradas; só ganharam os pontos de integração necessários.

### Decisões do `01` implementadas
1. Exatamente **3 skills** (Inteligência, Físico, Carisma); restrição no banco impede uma quarta.
2. Progressão **infinita**: nenhuma regra faz clamp superior (a coluna tem 26 dígitos inteiros).
3. O jogador **não distribui pontos**: não existe ação de "treinar"; a skill cresce porque a **atividade** foi feita.
4. **Estudar** desenvolve as 3 skills (`01 §1.4`); **Trabalhar** desenvolve a skill que o **cargo** informar (`01 §1.2`); o ganho do Trabalho é **menor** que o do Estudo (validado na configuração).
5. **Múltiplas skills** por atividade, quando ela as declarar.
6. **Requisitos mínimos** de uma ou mais skills, todas exigidas (`01 §1.9`), com detalhamento do que falta.
7. Fórmula de ganho `ganho_base × QoL_base × qualidade_da_escola` (`01 §1.3`), com **detalhamento estruturado** (doc 20), inclusive o diminishing returns como componente. `QoL_base` = QoL Base **estrutural** e a escola só entra em atividades **educacionais** (decisões do Game Director de 2026-10-02).
8. Skill como **multiplicador de produção** e como **base do teto salarial** (`01 §1.6-1.7`): só os pontos de uso/cálculo; ver extensão abaixo.
9. **Especialização do `02 §13`** (FINAL): ganho pelo trabalho, decadência diária, **piso de 50%** do máximo histórico, **recuperação a 1,5×**. Mais um **perfil emergente** descritivo (`01 §1.1`).

### Integração com o P0.04 (sem caminho paralelo)
- Novo `players/hooks.py`: `perform_action` aceita `activity: ActivityContext` e executa hooks **na mesma transação**, **só após o sucesso** da ação, em ordem determinística. Recusas (energia, burnout, hospitalização) **nunca** geram skill; falha em qualquer hook desfaz a ação inteira.
- `create_player` passou a ser atômico e chama hooks de criação (é onde as 3 skills nascem).
- Jogador humano e Bot usam exatamente o mesmo caminho (testado).
- A decadência da Especialização roda no **tick diário** do escopo `player` do P0.04. Único ajuste em teste do P0.04: `kinds_for("player")` deixou de ser exatamente `[TEN_MINUTES]`, porque outros sistemas agora somam outros kinds.

### Decisões do Game Director sobre Skills (2026-10-02)
Fecham itens que estavam como interpretação minha ou como `[ABERTO]`. Os valores provisórios de ganho, diminishing returns, Skill → produção, Especialização, salário e freelance **seguem abertos e calibráveis**: nada neles foi alterado.
1. **QoL usada no ganho de Skill: QoL Base estrutural.** Não a Base efetiva (que cai com o Burnout Ativo) nem a QoL Atual (efeitos temporários, Saúde Crítica). *Implementação:* o hook usa `qol_base`; a opção de configuração `qol_source` foi **removida** (deixou de ser decisão aberta) e passar a chave agora é erro de configuração.
2. **Skills não decaem.** Inteligência, Físico e Carisma nunca diminuem; a **única** progressão com decadência é a Especialização. *Implementação:* já era assim; passou a ser travado por testes (800 dias de jogo sem queda; só o handler de Especialização roda no tick diário).
3. **Atividade com múltiplas skills: cada skill declarada recebe o seu próprio ganho, sem divisão automática.** *Implementação:* já era assim; travado por teste (1, 2 ou 3 skills dão o mesmo ganho em cada uma).
4. **Qualidade da Escola só participa de atividades educacionais.** Para Trabalho e demais atividades o fator é neutro (1). *Implementação:* hoje a única atividade educacional é a ação **Estudar**; informar `school_quality` diferente de 1 em Trabalho ou Lazer é **erro explícito** (não é ignorado em silêncio). Quando surgirem outras atividades educacionais (cursos, grupos de estudo), será preciso marcá-las como tais.
*O texto de `design/01-skills.md` não foi alterado (segue REVIEW). Sugestão de ajuste, se desejado: §1.3 (QoL_base = QoL Base estrutural; escola só em educacionais) e a menção de que skills não decaem.*

### Ambiguidades e interpretações técnicas (reversíveis; **confirmar**)
1. **"Especialização" tem dois sentidos.** `01 §1.1`: concentração que "surge naturalmente" (sem mecânica). `02 §13` (FINAL): valor próprio por atividade/produto. `03 §14` fala em cursos que aumentam "especializações". Implementei o perfil emergente (só leitura) **e** a mecânica do `02 §13`. **Não implementados:** ganho por curso (`03 §14`) e o fator `f(skill, especialização)` da produção, pois dependem de Escolas/Empresas e seus valores não existem.
2. ~~**"QoL_base" (`01 §1.3`) × `04`** (QoL Base / Base efetiva / Atual).~~ **Fechada pelo Game Director (2026-10-02):** QoL Base estrutural (decisão 1 acima).
3. ~~**"qualidade_da_escola" na fórmula geral.**~~ **Fechada pelo Game Director (2026-10-02):** só em atividades educacionais; neutro (1) nas demais (decisão 4 acima).
4. ~~**Várias skills em uma atividade.**~~ **Fechada pelo Game Director (2026-10-02):** cada skill declarada recebe o seu próprio ganho, sem dividir (decisão 3 acima). O ganho base **por skill** segue parametrizável (`[PROV]`).
5. **Trabalhar/Lazer sem skill declarada não desenvolve nada.** Quem define a skill relevante é o cargo (Empresas) e a atividade de lazer. Lazer **não tem ganho padrão** (`01 §2` deixa em aberto); pedir skill no Lazer sem informar o ganho é erro explícito, não um valor inventado.
6. **Ganho é por execução da ação** (não por energia nem por dia). Coerente com `03` ("mais energia dedicada → mais ganho diário").
7. ~~**Skills nunca diminuem.**~~ **Fechada pelo Game Director (2026-10-02):** skills não decaem; só a Especialização (decisão 2 acima).
8. **Especialização:** só o **Trabalho** a desenvolve (`02 §13`: "através do trabalho"); a chave é opaca (atividade ou produto). "Dia sem uso" = dia de calendário do jogo (fuso do jogo) sem trabalhar naquela área, decaindo no tick que abre o dia seguinte; o dia do uso e o seguinte não decaem. A **forma** da decadência (pontos por dia) é suposição minha; o `02` só diz "decadência diária baixa".
9. **Teto salarial:** implementado só o **cálculo** (`nível × multiplicador`). O limite é diário com contador de recebido no dia; esse contador pertence ao sistema de pagamento (dinheiro), inexistente.
10. **Requisitos:** só **E** (todas as skills). O `01` não define "OU".
11. **Precisão:** a coluna aceita níveis enormes, mas o **SQLite de desenvolvimento** guarda decimais como ponto flutuante (~15 dígitos significativos). Em PostgreSQL (produção) é exato.
12. Consequência natural do `04`: com Burnout Ativo o Estudo é bloqueado, então não gera skill.

### Decisões abertas do `01`: isoladas, NÃO fechadas
| Decisão aberta | Como ficou |
|---|---|
| Fórmula do diminishing returns | Ponto de extensão `skills.curves.register_progress_curve`; única curva embutida é `"none"` (fator 1). Curva que devolva fator ≤ 0 é rejeitada (pararia a progressão infinita) |
| Fórmula Skill → produção | Ponto de extensão `register_production_curve`; padrão `"none"` (fator 1) |
| Multiplicador salarial definitivo | Parâmetro `salary_cap_multiplier`, `[PROV]` 1,5 (o "atualmente considerado" do `01`) |
| Distribuição de cargos entre INT/FIS/CAR | Não implementada (pertence a Empresas); o cargo informa a skill via `ActivityContext` |
| Quais atividades usam várias skills | `ActivityContext.skills`, definido por quem conhece a atividade |
| Ganhos definitivos de skill | Parâmetros `[PROV]` abaixo |
| Balanceamento de freelance | Não implementado |
| Atividades não especificadas | Sem ganho padrão; ganho explícito por atividade |

### Parâmetros provisórios `[PROV]` (numéricos, sobrescrevíveis por `POLIS_SKILLS_BALANCE`)
| Parâmetro | Valor | Observação |
|---|---|---|
| `initial_level` | 0 | o nível inicial virá do contexto de nascimento (hook `register_initial_level_provider`) |
| `base_gain.study` (cada skill) | 1,0 | `1` é só a unidade de referência; o `01 §1.3` usa "1.0" como exemplo conceitual |
| `base_gain.work` (cada skill) | 0,5 | só respeita "menor que o estudo" |
| `salary_cap_multiplier` | 1,5 | não definitivo (`01 §2`) |
| `specialization_gain_per_work` | 1 | `02 §13` deixa para o balanceamento |
| `specialization_decay_per_day` | 0,1 | idem |

`[02 §13]` (definidos): `specialization_floor_ratio` 0,5 e `specialization_recovery_multiplier` 1,5. `[ABERTO]` (configuração, não regra): `progress_curve` e `production_curve`. *(`qol_source` deixou de existir: decisão 1 de 2026-10-02.)*

### Sugestões para o Game Director (**NÃO implementadas**; só para decisão)
- **Diminishing returns:** o `01` já cita uma fórmula em faixas como não definitiva. Candidatas: (a) faixas por nível; (b) contínua, ex. `1 / (1 + nível / k)`; (c) logarítmica. Qualquer uma deve manter o fator estritamente positivo para preservar a progressão infinita. Sugiro escolher depois de observar a distribuição de níveis nos Bots.
- **Razão Trabalho/Estudo:** com os valores atuais, Estudar custa 10 de Energia e rende 0,5 por skill; Trabalhar custa 20 e rende 0,25 na skill do cargo. Por Energia, estudar rende **4×** mais. Vale confirmar se essa proporção é a intenção antes de calibrar.
- **Ordem de grandeza dos requisitos:** com QoL 0,50 e os ganhos atuais, o exemplo conceitual do `01` (Inteligência ≥ 100) exigiria ~200 estudos, e o Burnout do `04` bloqueia o Estudo após ~34 seguidos (+3 cada). Os níveis "100" e "75" do `01` são só exemplos; os níveis reais dos cargos precisam nascer da calibração.
- **Multiplicador salarial:** manter como parâmetro e avaliar se vira parâmetro de lei (`07`/`11`), como o `01 §1.7` sugere.
- **Freelance:** definir "desenvolvimento mínimo" como razão do ganho do Trabalho antes de implementá-lo.

---

## 2026-10-01 — `04` fechado como FINAL e estado do jogador (P0.04)

### Decisão do Game Director
- `04 — Dia a Dia` foi reescrito e fechado como **FINAL — BOT TEST** (`a62f37f`). O rascunho do P0.04 que eu havia feito sobre a versão REVIEW foi **descartado e refeito**. Principais mudanças de regra: custos de Energia **fixos** (Trabalhar 20, Estudar 10, Lazer 10); regeneração **5 por 10 min** com modificador de QoL de ±10%; Burnout **0–100** com Burnout Ativo (entra em 100, sai em ≤ 50) que bloqueia Trabalho e Estudar; Saúde **+5 − penalidades por ciclo** (pode cair); Saúde Crítica (≤ 20 entra, > 30 sai) e Hospitalização (Saúde = 0); efeitos de QoL **um por categoria**; QoL **sem teto**.

### Motor de tempo
- Novo `TickKind.TEN_MINUTES` (600 s absolutos): o ciclo dos estados contínuos (`04 §2.3, §7.2, §10, §23`). Decisão técnica; roda antes dos demais ticks no mesmo instante.
- Os estados são processados **ciclo a ciclo** (lazy, no acesso) e não por fórmula fechada, porque Saúde, Burnout, Nutrição e Energia dependem uns dos outros (`§23`). Custo medido: ~25 µs por ciclo (144 dias de jogo ≈ 20 mil ciclos ≈ 0,5 s).

### Decisões estruturais confirmadas pelo Game Director (2026-10-01)
1. **Risco de Burnout (`02 §9.2`):** é um **multiplicador** sobre os *ganhos* de Burnout de **Trabalhar e Estudar** (`04 §7.1`), com **piso de 1%** (mínimo 0,01); o Lazer **não** é afetado. Para eliminar a ambiguidade entre os documentos, o texto do `02 §9.2` foi **atualizado** (com exemplo: risco 50% → Trabalhar dá +2,5 em vez de +5).
2. **Efeitos temporários (`04 §4.4`):** a regra de **um único efeito ativo por categoria é GLOBAL**, para efeitos positivos **e** negativos; um novo efeito da mesma categoria sempre substitui o anterior, qualquer que seja o sinal. O texto do `04 §4.4` foi **atualizado** para falar em "efeito temporário" (antes dizia "bônus").
3. **Hospitalização (`04 §14`):** bloqueia **Trabalhar, Estudar e Lazer**. O texto do `04 §14` foi **atualizado** (antes: "ações incompatíveis com internação, incluindo trabalho"). A lista segue configurável (`Balance.hospitalization_blocked_actions`) por causa do Tratamento e de outras ações futuras ainda não definidas; a validação continua exigindo `work`. A duração segue `[PROV]`.

### Interpretações de implementação (derivadas do texto do `04`; não contestadas)
1. **Ordem do ciclo (`§23`):** Saúde (lê o estado do *início*) → Burnout → Nutrição → Energia (usa a QoL Base efetiva do *novo* estado). Fica numa única função, `rules.advance_cycle`.
2. **Recuperação de Burnout:** a espera de 1 h conta só a partir do último *Trabalho* (Estudar e Lazer não reiniciam), é inclusiva (≥ 1 h) e quem nunca trabalhou recupera sem espera.
3. Saúde Crítica e Hospitalização são estados independentes (Saúde = 0 implica os dois).
4. A hospitalização termina por **duração** (o `§14` a declara parametrizada), não por limiar de Saúde.

### Decisões de design a fechar
Nenhuma aberta no momento. *(A da hospitalização, `04 §14`, foi fechada em 2026-10-01: ver acima.)* Ao surgir uma, entra aqui com a categoria `[ABERTO]` do código (`players/balance.py`), separada dos `[PROV]` numéricos.

### Parâmetros provisórios `[PROV]` (`04 §27`: calibráveis; valores só para o sistema rodar)
São **numéricos**, e ficam separados das decisões estruturais e da decisão em aberto acima. Todos em `players/balance.py`, sobrescrevíveis por `POLIS_BALANCE`:

| Parâmetro | Valor | O que representa |
|---|---|---|
| `energy_regen_qol_sensitivity` | 1 | QoL → modificador de regeneração (linear em torno de 1,00) |
| `burnout_qol_penalty` | 0,10 | penalidade na QoL Base efetiva em Burnout Ativo |
| `critical_health_qol_debuff` | 0,10 | debuff na QoL Atual em Saúde Crítica |
| `nutrition_decay_per_cycle` | 0,5 | taxa temporal de alteração da Nutrição |
| `health_nutrition_penalty_max` | 8 | penalidade de Saúde por ciclo com Nutrição = 0 (linear) |
| `health_burnout_penalty` | 0 | penalidade de Saúde em Burnout Ativo (0 = ainda não definida) |
| `hospitalization_duration_seconds` | 21600 (6 h) | duração da hospitalização |

### Observações para calibração (parâmetros mantidos como estão)
Por decisão do Game Director (2026-10-01), estas consequências **não** motivam alterar valores antes do Bot Test; os parâmetros seguem provisórios.
- Com QoL Base **0,50** (`§4.1`) e relação linear, **todo jogador começa no teto de −10% de regeneração** (4,5 por ciclo) até que Moradia/Bens elevem a QoL a ≥ 0,90. É consequência direta de `§4.1` + `§2.3`; vale avaliar a relação.
- Sem comer, a Nutrição zera em ~33 h de jogo e a Saúde cai 3 por ciclo até a Hospitalização: com a taxa atual o jogador precisa comer a cada ~1,4 dia de jogo (~14 min reais no Bot Test).

### Dependências ainda não implementadas
- **Tratamento** (`§13`, 10 de Energia + pagamento): depende do sistema de dinheiro.
- **Auto-consumo de alimentos** com Nutrição < 10 (`§16`): depende de Inventário (P1.02) e do catálogo.
- **Recuperação Regional** (`§11`): hook `register_regional_recovery_provider` pronto (vale 0 enquanto não houver saúde regional/médicos).
- ~~**Bloqueio de Trabalho por Viagem** (`§6`, `§20`)~~ **Implementado no P0.06.1** (2026-10-06), como provedor de bloqueio em `players.hooks`.
- **Modificadores estruturais de QoL** (`§4.1`): hook `register_qol_base_provider`; cada sistema define o seu.
- **QoL → eficiência** (`§5`): sem consumidor ainda. **Estudar/Escola** (`§8-9`): P0.05+.

---

## 2026-09-30 — Reconstrução do código e fundação temporal

### Decisão do Game Director
- Todo o jogo implementado antes do design atual é defasado e foi **removido** (apps `empresas`, `financeira`, `geography`, `skills`, `Perfil`, templates). Preservado no histórico do Git. Mantidos: `design/`, documentos operacionais, projeto Django e `Usuario` como `AUTH_USER_MODEL`. Migrations reiniciadas (não há dados de produção a preservar).
- Consequência: a regra antiga "-0,2 QoL por trabalho/estudo" (código) está obsoleta, o `04` a substituiu por Burnout; e a criação de dinheiro por salário sem origem contraria o `CLAUDE.md`.

### Tempo do jogo (decisão do Game Director, 2026-09-30)
- **O tempo do jogo é o tempo real**: segundos, dias e meses de calendário reais (mês de 28–31 dias, anos bissextos). Não é relativo à time zone do usuário: o jogo tem a **sua própria time zone**.
- O jogo funciona por ticks **horários, diários, semanais e mensais**.
- Só a **velocidade** pode ser acelerada, no Bot Test (ex.: 1 dia = 10 min reais). Em produção, velocidade 1×.

### Motor de tempo (P0.03): decisões técnicas assumidas
Não são regras de gameplay; são convenções reversíveis e cobertas por testes:
- Tempo de jogo = segundos Unix do relógio de jogo (a 1× é idêntico ao tempo real). A velocidade padrão é 86400 s reais/dia de jogo; o Bot Test usa 600.
- **Fuso do jogo: `America/Sao_Paulo`** (confirmado pelo Game Director em 2026-09-30), configurável por `POLIS_GAME_TIMEZONE`. Sem horário de verão hoje; o motor aguenta DST (testado com New York e Kolkata).
- Hourly: a cada 3600 s absolutos. Daily: 00:00 local. Weekly: **segunda 00:00 local** (`07`). Monthly: **dia 1, 00:00 local** (confirmado pelo Game Director em 2026-09-30).
- Intervalos são (start, end]: sem perda nem repetição. Não há tick "retroativo" antes de o mundo existir.
- Ordem no mesmo instante: `TickKind` (do menor para o maior período), depois `priority`, depois `name`. Ordem do motor, não de gameplay; as dependências do estado do jogador estão em `04 §23` e vivem em `players/rules.advance_cycle` (ver 2026-10-01).
- Escopo sem handlers avança o ponteiro; handlers registrados depois não reprocessam o passado.
- Consequência da aceleração: com 1 dia = 10 min, um mês de calendário dura de 4h40 a 5h10 reais, e um jogador ausente por 1 dia real "perde" 144 dias de jogo (catch-up em lote).

### Pendências para o Game Director (nenhuma bloqueia o P0.03)
1. **Status divergente entre `TASK.md` e os arquivos de design:** `01` e `03` estão em FINAL no `TASK.md` mas `REVIEW` no cabeçalho do arquivo; `19` está REVIEW no `TASK.md` mas `FINAL — BOT TEST` no arquivo; `05` (REVIEW) não consta na lista. Tratados como REVIEW até decisão. A resolver em P0.01. *(O `04` já foi fechado como FINAL — BOT TEST em 2026-10-01.)*
2. **Índices desatualizados:** `design/README.md` e `implicacoes-tecnicas.md` citam arquivos que não existem mais (`06-politica.md`, `09-financeira.md`, `10-futuro.md`).
3. **Classificação de tick por sistema:** o `04 §23` já define a ordem dos estados do jogador (ver 2026-10-01); para os demais sistemas (leis, orçamento, contratos...) a classificação ainda precisa ser decidida sistema a sistema.
4. **Calendário "Ano N, Mês M" do Histórico do Mundo (`12`)**: é contado a partir do início do mundo ou é o ano de calendário? A tratar em P1.14.

---

## 2026-09-29 — Transição para implementação

### Processo

- O projeto encerra a rodada principal de discussão dos documentos `01–21`.
- `FINAL — BOT TEST` passa a significar especificação fechada para implementação.
- O Sitemap permanece em `REVIEW`, mas já pode orientar a estrutura de UI.
- O desenvolvimento deve começar pelos fundamentos e avançar por dependências.

### Estratégia de implementação

- Não esperar todos os sistemas futuros para começar a codificar.
- Não implementar sistemas FUTURO apenas para “completar” o jogo.
- Priorizar fundações reutilizáveis, testes e integrações.

---

## 2026-09-29 — Feedback

- `20 — Filosofia de Feedback ao Jogador` foi fechado como `FINAL — BOT TEST`.
- Fórmulas compostas devem retornar valor e detalhamento estruturado.
- O detalhamento pode representar soma, multiplicação, limites ou condições.
- Feedback não deve inventar causalidade que o modelo não calcula.
- A separação entre cálculo e apresentação é obrigatória.

---

## 2026-09-29 — Bots

- `21 — Bots para Testes de Beta` foi fechado como `FINAL — BOT TEST`.
- Bot Test é ferramenta de validação, não mecânica de jogo.
- Ambiente único contínuo.
- População-alvo inicial: aproximadamente 1.000 Bots.
- Criação padrão: aproximadamente 1 Bot por minuto até a meta.
- Population Controller pode preencher lacunas de cobertura.
- Relógio acelerado padrão: aproximadamente 1 dia de jogo = 10 minutos reais.
- Bots usam somente informações que jogadores normais teriam.
- Bots interagem entre si e com jogadores humanos quando aplicável.
- Abordagem de aprendizado: RL híbrido com regras de validação e Action Masking.
- LLM não é mecanismo de decisão do primeiro Bot Test.
- Modelo neural pode ser compartilhado entre Bots, com memória/experiência individual.
- Personalidade, objetivo e especialização são dimensões separadas.
- Reward varia por arquétipo/objetivo.
- Exploração varia por arquétipo e individualmente.
- Checkpoints do modelo são versionados e reproduzíveis.
- Métricas de conhecimento devem ser baseadas em desempenho demonstrado.
- Dashboard deve permitir inspeção geral, por arquétipo e individual.
- Dashboard deve mostrar objetivo, plano, próxima ação, decisões e conhecimento.
- Sistema deve detectar lacunas de cobertura e anomalias automaticamente.
- Logs devem ser exportáveis para análise externa.
- Performance deve medir CPU, RAM, GPU, VRAM, ticks, scheduler, banco e treinamento.

### Arquétipos-base

1. Casual
2. Otimizador
3. Conservador
4. Explorador
5. Caótico
6. Empreendedor
7. Político
8. Especialista
9. Social
10. Adversarial

A arquitetura não deve transformar esses 10 nomes em classes rígidas. Eles representam combinações-base; personalidade, objetivo e especialização devem permanecer combináveis.

---

## 2026-09-28 — Rankings

- Janela de produção do ranking: 14 dias.
- Ranking de contribuinte: impostos efetivamente pagos nos últimos 30 dias.
- Influência política permanece fora do Bot Test até existir métrica objetiva.
- Melhor escola/universidade utiliza qualidade atual.
- Conta mais antiga utiliza tempo desde criação.
- Maior tempo ativo utiliza sequência de ações válidas com intervalos inferiores a 72 horas.
- O antigo “Presidente com maior aprovação” tornou-se “Presidente com maior percentual de votos”, baseado no resultado efetivo da eleição.

---

## 2026-09-28 — Transparência de mercado

- Página de Produto deve usar transações reais e agregados.
- Preço médio é ponderado por quantidade.
- Estatísticas públicas utilizam agregados para desempenho.
- Histórico bruto continua disponível para auditoria/Dev.
- Gráficos de produto fazem parte do Bot Test.
- Custos de empresa devem mostrar componentes e principais contribuições sem inventar causalidade.

---

## 2026-09-27 — Contratos

- Partes de contratos podem ser jogadores ou empresas.
- Contratos de trabalho foram removidos da especificação de Contratos e permanecem nas regras de emprego/empresa.
- Empréstimos diretos entre jogadores podem existir como contrato.
- Execução é automática segundo os termos.
- Multas transferem dinheiro entre partes; não criam dinheiro.
- Contrato aceito fica congelado para aquela obrigação salvo mecanismo específico futuro.

---

## 2026-09-26 — Sociedades e Ações

- Sociedades e ações são endgame/futuro.
- Empresas normais continuam com proprietário único no início.
- Empresas de 4★ ou mais podem futuramente ser fracionadas em ações.
- Emissão primária capta capital para a empresa.
- Mercado secundário transfere dinheiro entre investidores.
- Bolsa, dividendos e voto acionário detalhado ficam fora do primeiro Bot Test.

---

## 2026-09-25 — Eventos Aleatórios

- Eventos continuam FUTURO.
- Evento deve alterar condição real existente, não aplicar apenas buff abstrato.
- Não criar consumidores fictícios ou dinheiro novo.
- Boom econômico baseado em NPCs foi removido.
- Eventos futuros podem usar estoque, QoL, saúde, recursos e estados reais existentes.

---

## 2026-09-24 — Geografia / Economia

- Hierarquia territorial: Estado → Cidade → Bairro → Lote.
- Bairro/cidade possuem estrutura espacial; capital é referência histórica em `(0,0)`.
- Lotes possuem capacidades por tipo.
- Áreas rurais suportam Matriz de Agropecuária, Extrativismo e Mineração.
- Petróleo deve pertencer a **Extrativismo**; referências antigas que coloquem petróleo em Mineração não são autoridade.
- Ocorrências minerais são espacialmente correlacionadas, não apenas sorteios independentes por lote.

---

## 2026-09 — Política / Leis

### Estrutura política

- Presidente, Governador e Prefeito são os executivos.
- Câmara dos Deputados é nacional no primeiro Bot Test.
- Um jogador não ocupa mais de um cargo político simultaneamente.
- Governador exige experiência anterior como Prefeito.
- Presidente exige experiência anterior como Governador e diploma de Engenharia, Direito ou Medicina.
- Político pode possuir empresas privadas, mas essas empresas não recebem contratos públicos enquanto ele ocupar cargo.
- Político não é empregado de outra empresa durante o mandato.

### Processo legislativo

- Discussão: 3 dias.
- Votação: 3 dias.
- Processo segue calendário semanal fixo.
- Câmara usa maioria absoluta da composição congelada.
- Presidente pode sancionar ou vetar.
- Veto pode ser derrubado por 2/3.
- Mudança do Presidente antes de sanção/veto retorna a proposta à Câmara.
- Lei entra em vigor no próximo weekly tick.
- Leis não retroagem.
- Constituição limita leis ordinárias.

### Deposição

- Milícia pode depor Presidente segundo `19`.
- Líder da milícia assume com novo mandato completo conforme parâmetro aplicável.
- Governadores e Prefeitos permanecem.
- Câmara é encerrada e nova eleição é realizada.
- Constituição e leis existentes não são apagadas automaticamente.

---

## 2026-09 — Militar

- Não existe cooldown para trocar Exército e Milícia.
- Entrada e saída devem respeitar apenas os requisitos normais do sistema.
- Milícias utilizam estoque e Produtos reais.
- Conflitos consomem recursos e podem gerar hospitalização.
- Exército é financiado por orçamento público.

---

## 2026-09 — Economia / Empresas

- Uma empresa produtiva possui um Produto/linha de produção atual por vez, com regras de mudança documentadas em `02`.
- Produto → usos permitidos → empresas capazes de consumir o produto é a cadeia de compatibilidade econômica.
- Compras de insumos são limitadas pelas regras reais de receita/operação.
- Engenheiros aumentam eficiência por ação de trabalho, com limite por estrela.
- Advogados reduzem risco de burnout.
- Construção possui um projeto ativo por vez.
- Acabamentos usam Tábuas + Vidro.
- Propriedade normal da empresa não depende de sociedade por ações no Bot Test.

---

# Próximo marco

**Implementação do núcleo do Bot Test:** tempo → estado do jogador → skills → geografia → produtos/inventário → Action Registry → empresas/mercado → UI → política/militar → Bots.

O objetivo é manter cada etapa pequena, testável e reversível sem reabrir decisões de design já marcadas como FINAL.
