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
| Pão | Farinha | 1★ | média | sem efeito |
| Chocolate | Manteiga de cacau + Açúcar + Leite | 4★ | pouca | pequeno buff |
| Macarrão | Queijo + Farinha + Ovo | 3★ | bastante | sem efeito |
| Hambúrguer | Queijo + Carne processada + Pão | 4★ | média | pequeno buff |
| Suco | Fruta + Açúcar | 2★ | quase nada | pequeno buff |
| Sorvete | Leite + Açúcar + Fruta | 3★ | nada | buff médio |
| Carne de Sol | Carne + Sal | 1★ | média | **debuff** |
| Refrigerante | Açúcar + Suco + Químicos | 2★ | nada | buff médio |
| Carro | Aço + Plástico + Bateria + Borracha + Químico | 5★ | — | — |

> **Pão (GD 2026-10-14, Q5): consumível.** O perfil de consumo (média / sem efeito) é `[PROV]`: este documento não o declarava; foi escolhido como valor inicial calibrável (ver §4).

**Tecnológica:**

| Produto final | Ingredientes | Estrela mínima |
|---|---|---|
| Componentes eletrônicos | Fios de cobre + Sílica + Ouro | 1★ |
| Bateria | Cobre + Lítio + Químicos | 2★ |
| Celular | Componentes eletrônicos + Plástico + Bateria | 3★ |
| Computador | Componentes eletrônicos + Plástico + Aço + Químicos | 4★ |

**Milícia (produzido por milícias):**

| Produto final | Ingredientes | Estrela mínima |
|---|---|---|
| Armas Improvisadas | Aço + Madeira + Plástico | Não existe |
| Armaduras Improvisadas | Aço + Plástico | Não existe |
| Kit Médico Improvisado | Lã + Materiais hospitalares | Não existe |

**Produtos militares do Exército (produzidos por empresas Industriais / Produção; receitas e estrela `[PROV]`, GD 2026-10-14, Q4):**

| Produto final | Ingredientes | Estrela mínima |
|---|---|---|
| Armas Militares | Aço + Madeira + Plástico | 2★ [PROV] |
| Armaduras Militares | Aço + Plástico | 2★ [PROV] |
| Kits de Primeiros Socorros do Exército | Lã + Materiais hospitalares | 2★ [PROV] |

> Os produtos do Exército são entidades **distintas** das versões improvisadas da milícia (Armas/Armaduras/Kit Médico Improvisados). O abastecimento recorrente vem de produção ou fornecimento efetivo; o cenário pode iniciar com dotação explícita de itens. A empresa produtora é do tipo **Industrial, sub-tipo Produção** (decisão do Game Director, 2026-10-15; a ser aplicada na P1.04).

### 2.2 Matriz — definida por terreno, não por skill 🤝

| Terreno | Produz |
|---|---|
| Agropecuária | Trigo, Leite, Cana, Grão de Café, Cacau, Carne, Ovos, Couro, Lã, Fruta |
| Extrativismo | Madeira, Resina, Látex, Óleo natural, Ervas, Areia, Pedra, Químicos, Petróleo, Borracha |
| Mineração | Ferro, Cobre, Sílica, Carvão, Sal, Lítio, Ouro, Prata, Diamante |

### 3. Classificação e canais comerciais (GD 2026-10-14, Q6 e Q8)

Cada produto tem **uma** categoria principal (Alimento, Material, Equipamento, Durável, Militar); *consumível*, *permanente* e *militar* são tags separadas. "Usável em receita" é derivado das receitas, não é categoria. Os canais são **declarados** (nenhum é inferido): Varejo vende bens finais aos jogadores; matérias-primas e intermediários circulam entre empresas; produtos do Exército saem por contrato federal; a milícia compra insumos por Requisição Especial. Não há venda direta geral entre inventários pessoais. Não há limite de capacidade de inventário do jogador nem de estoque institucional do Exército. Não existe o produto "Acabamentos" (Q7): Tábuas e Vidro entram direto nas receitas. Materiais operacionais ficam fora da primeira implementação de Empresas (Q10).

> Esta tabela é **gerada** pelo catálogo (`manage.py list_provisional --format markdown`) e um teste confere que documento e código coincidem.

| Chave | Produto | Categoria | Tags | Canais comerciais |
|---|---|---|---|---|
| wheat | Trigo | Material | — | entre empresas |
| milk | Leite | Material | — | entre empresas |
| sugar_cane | Cana | Material | — | entre empresas |
| coffee_bean | Grão de café | Material | — | entre empresas |
| cocoa | Cacau | Material | — | entre empresas |
| meat | Carne | Material | — | entre empresas |
| eggs | Ovos | Material | — | entre empresas |
| leather | Couro | Material | — | entre empresas |
| wool | Lã | Material | — | entre empresas, requisição especial |
| fruit | Fruta | Material | — | entre empresas |
| wood | Madeira | Material | — | entre empresas, requisição especial |
| resin | Resina | Material | — | entre empresas |
| latex | Látex | Material | — | entre empresas |
| natural_oil | Óleo natural | Material | — | entre empresas |
| herbs | Ervas | Material | — | entre empresas |
| sand | Areia | Material | — | entre empresas |
| stone | Pedra | Material | — | entre empresas |
| chemicals | Químicos | Material | — | entre empresas |
| oil | Petróleo | Material | — | entre empresas |
| rubber | Borracha | Material | — | entre empresas |
| iron | Ferro | Material | — | entre empresas |
| copper | Cobre | Material | — | entre empresas |
| silica | Sílica | Material | — | entre empresas |
| coal | Carvão | Material | — | entre empresas |
| salt | Sal | Material | — | entre empresas |
| lithium | Lítio | Material | — | entre empresas |
| gold | Ouro | Material | — | entre empresas |
| silver | Prata | Material | — | entre empresas |
| diamond | Diamante | Material | — | entre empresas |
| cement | Cimento | Material | — | entre empresas |
| steel | Aço | Material | — | entre empresas, requisição especial |
| planks | Tábuas | Material | — | entre empresas |
| glass | Vidro | Material | — | entre empresas |
| construction_materials | Materiais de Construção | Material | — | entre empresas |
| plastic | Plástico | Material | — | entre empresas, requisição especial |
| fuel | Combustível | Material | — | entre empresas |
| fertilizer | Fertilizante | Material | — | entre empresas |
| copper_wire | Fios de cobre | Material | — | entre empresas |
| ppe | EPIs | Equipamento | — | entre empresas |
| school_supplies | Materiais escolares | Equipamento | — | entre empresas |
| hospital_supplies | Materiais hospitalares | Equipamento | — | entre empresas, requisição especial |
| flour | Farinha | Material | — | entre empresas |
| sugar | Açúcar | Material | — | entre empresas |
| cheese | Queijo | Material | — | entre empresas |
| butter | Manteiga | Material | — | entre empresas |
| ground_coffee | Café em pó | Material | — | entre empresas |
| cocoa_butter | Manteiga de cacau | Material | — | entre empresas |
| processed_meat | Carne processada | Material | — | entre empresas |
| clothes | Roupas | Equipamento | — | entre empresas, varejo |
| furniture | Móveis | Durável | permanente | entre empresas, varejo |
| paper | Papel | Equipamento | — | entre empresas, varejo |
| pen | Caneta | Equipamento | — | entre empresas, varejo |
| shoes | Calçados | Equipamento | — | entre empresas, varejo |
| uniform | Uniforme | Equipamento | — | entre empresas |
| bread | Pão | Alimento | consumível | entre empresas, varejo |
| chocolate | Chocolate | Alimento | consumível | entre empresas, varejo |
| pasta | Macarrão | Alimento | consumível | entre empresas, varejo |
| hamburger | Hambúrguer | Alimento | consumível | entre empresas, varejo |
| juice | Suco | Alimento | consumível | entre empresas, varejo |
| ice_cream | Sorvete | Alimento | consumível | entre empresas, varejo |
| sun_dried_meat | Carne de Sol | Alimento | consumível | entre empresas, varejo |
| soda | Refrigerante | Alimento | consumível | entre empresas, varejo |
| car | Carro | Durável | permanente | entre empresas, varejo |
| electronic_components | Componentes eletrônicos | Material | — | entre empresas |
| battery | Bateria | Material | — | entre empresas |
| cellphone | Celular | Durável | permanente | entre empresas, varejo |
| computer | Computador | Durável | permanente | entre empresas, varejo |
| improvised_weapons | Armas Improvisadas | Militar | militar | — |
| improvised_armor | Armaduras Improvisadas | Militar | militar | — |
| militia_medical_kit | Kit Médico Improvisado | Militar | consumível, militar | — |
| military_weapons | Armas Militares | Militar | militar | fornecimento ao Exército |
| military_armor | Armaduras Militares | Militar | militar | fornecimento ao Exército |
| military_medical_kits | Kits de Primeiros Socorros do Exército | Militar | consumível, militar | fornecimento ao Exército |

### 4. Valores provisórios `[PROV]` (GD 2026-10-14, Q3)

Os números que este documento não dá são **provisórios**, calibráveis no Bot Test sem redesenhar a arquitetura. A fonte de verdade deles é `catalog/provisional.py`; o comando `manage.py list_provisional` exporta cada linha (por produto e parâmetro, com fonte). Estrutura (insumos, níveis qualitativos, estrelas dos produtos industriais, categorias, canais) vem deste documento e **não** é sobrescrita por valor provisório.

#### 4.1 Parâmetros gerais

| Parâmetro | Valor | Regra | Fonte | Status |
|---|---|---|---|---|
| recipe_input_quantity | 1 | uma unidade de cada ingrediente declarado | GD 2026-10-14 Q3 | PROV |
| recipe_yield | 1 | uma unidade do produto final por execução | GD 2026-10-14 Q3 | PROV |
| matriz_min_stars | 1 | uniforme para toda matéria-prima (o 22 não diferencia) | GD 2026-10-14 Q3 | PROV |
| matriz_yield | 1 | unidades por execução de produção da Matriz | GD 2026-10-14 Q3 | PROV |
| army_min_stars | 2 | estrela mínima dos produtos militares do Exército (Industrial) | GD 2026-10-14 Q4 | PROV |
| raw_base_price | 10.00 | preço-base de referência da matéria-prima | GD 2026-10-14 Q3 | PROV |
| value_added_per_star | 5.00 | valor agregado por execução e por estrela mínima (produto sem estrela conta 1) | GD 2026-10-14 Q3 | PROV |
| bread_profile | medium/no_effect | perfil de consumo do Pão (o 22 não declarava) | GD 2026-10-14 Q5 | PROV |
| nutrition_amount[none] | 0 | ganho de Nutrição por unidade consumida (escala 0-100) pelo nível qualitativo do 22 | GD 2026-10-14 Q3 | PROV |
| nutrition_amount[almost_none] | 5 | ganho de Nutrição por unidade consumida (escala 0-100) pelo nível qualitativo do 22 | GD 2026-10-14 Q3 | PROV |
| nutrition_amount[low] | 15 | ganho de Nutrição por unidade consumida (escala 0-100) pelo nível qualitativo do 22 | GD 2026-10-14 Q3 | PROV |
| nutrition_amount[medium] | 30 | ganho de Nutrição por unidade consumida (escala 0-100) pelo nível qualitativo do 22 | GD 2026-10-14 Q3 | PROV |
| nutrition_amount[high] | 50 | ganho de Nutrição por unidade consumida (escala 0-100) pelo nível qualitativo do 22 | GD 2026-10-14 Q3 | PROV |
| qol_intensity[no_effect] | 0 | magnitude do efeito temporário de QoL (debuff é negativo) | GD 2026-10-14 Q3 | PROV |
| qol_intensity[small_buff] | 0.05 | magnitude do efeito temporário de QoL (debuff é negativo) | GD 2026-10-14 Q3 | PROV |
| qol_intensity[medium_buff] | 0.10 | magnitude do efeito temporário de QoL (debuff é negativo) | GD 2026-10-14 Q3 | PROV |
| qol_intensity[debuff] | 0.05 | magnitude do efeito temporário de QoL (debuff é negativo) | GD 2026-10-14 Q3 | PROV |

#### 4.2 Preço-base de referência por produto

Valor de **referência** (matéria-prima = 10,00; produto feito = soma dos insumos ÷ rendimento + 5,00 × estrelas, sem estrela conta 1). Não é preço de mercado.

| Chave | Produto | Preço-base [PROV] |
|---|---|---|
| wheat | Trigo | 10.00 |
| milk | Leite | 10.00 |
| sugar_cane | Cana | 10.00 |
| coffee_bean | Grão de café | 10.00 |
| cocoa | Cacau | 10.00 |
| meat | Carne | 10.00 |
| eggs | Ovos | 10.00 |
| leather | Couro | 10.00 |
| wool | Lã | 10.00 |
| fruit | Fruta | 10.00 |
| wood | Madeira | 10.00 |
| resin | Resina | 10.00 |
| latex | Látex | 10.00 |
| natural_oil | Óleo natural | 10.00 |
| herbs | Ervas | 10.00 |
| sand | Areia | 10.00 |
| stone | Pedra | 10.00 |
| chemicals | Químicos | 10.00 |
| oil | Petróleo | 10.00 |
| rubber | Borracha | 10.00 |
| iron | Ferro | 10.00 |
| copper | Cobre | 10.00 |
| silica | Sílica | 10.00 |
| coal | Carvão | 10.00 |
| salt | Sal | 10.00 |
| lithium | Lítio | 10.00 |
| gold | Ouro | 10.00 |
| silver | Prata | 10.00 |
| diamond | Diamante | 10.00 |
| cement | Cimento | 25.00 |
| steel | Aço | 30.00 |
| planks | Tábuas | 15.00 |
| glass | Vidro | 20.00 |
| construction_materials | Materiais de Construção | 100.00 |
| plastic | Plástico | 20.00 |
| fuel | Combustível | 25.00 |
| fertilizer | Fertilizante | 20.00 |
| copper_wire | Fios de cobre | 15.00 |
| ppe | EPIs | 105.00 |
| school_supplies | Materiais escolares | 160.00 |
| hospital_supplies | Materiais hospitalares | 100.00 |
| flour | Farinha | 15.00 |
| sugar | Açúcar | 15.00 |
| cheese | Queijo | 15.00 |
| butter | Manteiga | 20.00 |
| ground_coffee | Café em pó | 20.00 |
| cocoa_butter | Manteiga de cacau | 25.00 |
| processed_meat | Carne processada | 20.00 |
| clothes | Roupas | 15.00 |
| furniture | Móveis | 60.00 |
| paper | Papel | 30.00 |
| pen | Caneta | 45.00 |
| shoes | Calçados | 15.00 |
| uniform | Uniforme | 45.00 |
| bread | Pão | 20.00 |
| chocolate | Chocolate | 70.00 |
| pasta | Macarrão | 55.00 |
| hamburger | Hambúrguer | 75.00 |
| juice | Suco | 35.00 |
| ice_cream | Sorvete | 50.00 |
| sun_dried_meat | Carne de Sol | 25.00 |
| soda | Refrigerante | 70.00 |
| car | Carro | 135.00 |
| electronic_components | Componentes eletrônicos | 40.00 |
| battery | Bateria | 40.00 |
| cellphone | Celular | 115.00 |
| computer | Computador | 120.00 |
| improvised_weapons | Armas Improvisadas | 65.00 |
| improvised_armor | Armaduras Improvisadas | 55.00 |
| militia_medical_kit | Kit Médico Improvisado | 115.00 |
| military_weapons | Armas Militares | 70.00 |
| military_armor | Armaduras Militares | 60.00 |
| military_medical_kits | Kits de Primeiros Socorros do Exército | 120.00 |
