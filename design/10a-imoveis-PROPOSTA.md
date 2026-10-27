# 10a — Imóveis: o que foi implementado (P1.07a–c) e o que depende de decisão (proposta)

> **Status:** PROPOSTA — o `10` está FINAL — BOT TEST e define a estrutura; este documento registra as **lacunas** encontradas ao
> implementar a primeira etapa (propriedade, leilão, venda, obra com lote) e a **menor solução técnica** usada em cada uma
> (CLAUDE.md §13). Valores numéricos ausentes estão `[PROV]` em `properties/params.py` (tabela auditável `provisional_table()`).
> Nenhuma mecânica nova foi criada.

## 1. Etapas de P1.07

| Etapa | Conteúdo | Estado |
|---|---|---|
| **P1.07a** | Propriedade de lotes (título + histórico), leilão público com extensão, venda entre proprietários, imóvel residencial construído, obra da Construtora ligada ao lote, auditoria, ações no Action Registry | implementada |
| **P1.07b** | Unidades e ocupação, residência ativa, **Aluguel** (handler `RENT` no motor de `18`), venda de imóvel alugado mantendo o contrato, QoL estrutural, moradia inicial | implementada (§6) |
| **P1.07c** | Localização de empresas, terreno da Matriz (`production.register_site_provider`) | **parcial** (§8): feito o que o design define; **G12** resolvida provisoriamente pela regra A (GD 2026-10-27, §10); **G5** (tipos comercial/industrial) e **G6** (mudança de uso): direção do GD registrada (B e B), detalhes em §11–§12 |

## 2. O que a P1.07a entrega (app `properties`)

- **Título** (`LotTitle`: dono atual; sem linha = governo, `10` §2) e **histórico de aquisição imutável** (`TitleEvent`, cadeia contínua por lote, preço e chave do lançamento monetário; `10` §3).
- **Leilão público** (`10` §4): lance mínimo, lances crescentes, **extensão** por lance na janela final (`10` §4.3), encerramento no tick de 10 minutos do mundo (idempotente), pagamento do arrematante ao **Município do lote** (`AUCTION_PAYMENT`, `24` Q2), transferência do título no mesmo ato. Sem lances → `UNSOLD`; arrematante sem fundos → `INVALIDATED`.
- **Venda entre proprietários** (`10` §8): anúncio a preço do dono, compra = `SALE` do comprador ao vendedor **sem imposto** (`24` §24.7) + título; empresa age pelo Dono.
- **Imóvel** (`Building`, `10` §5-6): os 4 tipos residenciais (unidades, QoL, estrela mínima), um por lote, lote passa a OCUPADO; segue o título do lote (`10` §3 "mesmo ativo").
- **Obra com lote** (`10` §5, §28): `start_construction` aceita `lot`; a Construtora só constrói no lote **que é dela**, vazio, onde o zoneamento permite moradia (`geography.zoning`), sem anúncio nem obra ativa; a conclusão (no mesmo Trabalho que conclui) cria o imóvel.
- Ações no registro (mesmo caminho para bots e humanos): `bid_auction`, `list_property`, `unlist_property`, `buy_property` (+ `lot` opcional em `start_construction`). Abrir leilão **não** é ação de jogador (ver G1).
- `audit_properties` (+ `manage.py audit_properties [--json]`), `manage.py open_auctions` (ferramenta do sistema/Dev).
- Gancho para leis futuras: `services.register_eligibility` (quem pode dar lance/comprar; `10` §4.1 "requisitos legais"). Nenhuma regra registrada.

## 3. Parâmetros

| Parâmetro | Valor | Estado |
|---|---|---|
| Tipos de imóvel (unidades / QoL / estrela) | baixa simples 1/+0/1★; baixa luxo 1/+0,3/3★; alta simples 20/+0,1/2★; alta luxo 20/+0,4/4★ | **GD** (`10` §6, "parâmetros iniciais"; "~20" → 20) |
| Duração do leilão | 1 dia de jogo | `[PROV]` (`10` §4.2 diz "parâmetro do sistema") |
| Janela de extensão / extensão | 10 min / 10 min (soma ao encerramento atual) | `[PROV]` (`10` §4.3) |
| Aumento mínimo do lance | 1 centavo | `[PROV]` (`10` §4.1 "podem aumentar o valor") |
| Categorias leiloáveis | residencial, comercial, industrial, rural | `[PROV]` (`10` §2 "disponíveis para desenvolvimento") |

## 4. Lacunas e como foram tratadas

Cada lacuna diz se **bloqueia a próxima etapa** (P1.07b) ou pode ficar provisória.

| # | Lacuna | Solução técnica atual | Bloqueia P1.07b? |
|---|---|---|---|
| G1 | **Quem abre leilões e quando** (o `10` §4 descreve o leilão, não o gatilho; `NPC` econômico é proibido) | Só `open_auction`/comando `open_auctions` (sistema/Dev). Nenhum leilão abre sozinho. | Não (mas o Bot Test precisa de lotes à venda: decidir antes de ligar os bots) |
| G2 | Leilão cujo arrematante **não consegue pagar** (`10` §4.4 exige fundos, não diz o que ocorre sem eles) | Fundos conferidos no lance e no encerramento (sem reserva); sem fundos → `INVALIDATED`, lote segue do governo, nenhum dinheiro se move | Não |
| G3 | Contrato **privado de obra** entre o dono do terreno e a Construtora (`10` §5; `18` 18.2 não tem tipo "obra") | A Construtora constrói **só no próprio lote** (`10` §28 diz que o lote é dela); depois vende pelo anúncio | Não |
| G4 | Obra **sem lote** (`02` §12 × `10` §5/§28): o P1.04e permite iniciar sem lote | Mantida (compatibilidade), **não gera imóvel**; com `lot` gera. Cancelar/abandonar obra segue em aberto | Não |
| G5 | Tipos de imóvel **comercial/industrial** e estrela → nível comercial (`10` §16-17 sem números) | Só os 4 residenciais existem; comercial/industrial entram na P1.07c | **Sim, para P1.07c** |
| G6 | Mudança de **uso** do lote e quem aprova (`10` §33 "[ABERTO]") | Zoneamento (`geography.zoning`) decide; sem processo de mudança | P1.07c |
| G7 | Requisitos de **estrela/elegibilidade** para dar lance | Nenhum (gancho `register_eligibility` pronto) | Não |
| G8 | Quais residências contam para a **capacidade de escola** (construídas × potenciais; `03a` decisão 1) | Provedor `schools.register_residence_provider` **não** registrado | Não (P1.06d) |
| G9 | **Moradia inicial** dos jogadores (lotes OCUPADOS sem `Building`) | **Resolvida pelo texto do design** (`04` §24, `10` §14): moradia inicial = **ausência** de `ActiveResidence`; básica, neutra em QoL, fora da capacidade. Nada a criar nos lotes gerados | Não (resolvida na P1.07b) |
| G10 | Lance **proxy**/máximo automático e desempate no mesmo instante | Não existem; o lance é aceito em ordem de trava, um por vez | Não |
| G11 | Imposto sobre propriedade (`TAX_PROPERTY`) | Não cobrado nesta etapa; segue Orçamento/Leis (P1.09/P1.12) | Não |

## 5. Decisões necessárias ao Game Director (apenas as da próxima etapa)

- **G12 (provisória, GD 2026-10-27):** regra A em vigor; falta confirmar como vale para lote **com** depósito (§10; hoje: depósito acrescenta).
- **G5** (direção B): fechar os 8 pontos de §11 (começando por **11.0**, a interpretação do `10` §16). **G6** (direção B): 3 pontos de §12.
- **H6 e H8** (P1.07b) seguem **provisórios**, não decisões definitivas. G1 (quem abre leilões) continua necessária antes de ligar os bots.

## 6. O que a P1.07b entrega

- **Unidades** (`Unit`, 1..N por imóvel, criadas na conclusão da obra; a migração cria as dos imóveis existentes) e **residência ativa** (`ActiveResidence`, um jogador numa unidade; `set_residence`). **Direito de morar**: ser o proprietário (jogador) da unidade sem contrato em vigor, ou o inquilino de um contrato `rent` que já começou. Empresa não mora. Sem linha = moradia inicial (G9).
- **QoL do imóvel** (`10` §6.1): provedor `residence_building` em `players.qol` soma o `qol_bonus` do prédio da unidade onde o jogador mora (explicado em passos; moradia inicial = 0).
- **Aluguel** como tipo `rent` do motor de contratos (`18`): anúncio (`RentListing`: valor por período, periodicidade diária/semanal/mensal, multa e `max_failures` opcionais), contrato proposto e aceito num só ato por `rent_unit`, ou pelas ações genéricas de contrato. Pagamento periódico do inquilino ao locador, natureza `RENT`, **sem imposto**; falta de fundo vira obrigação (`18`), `defaulted` e, por `max_failures` falhas consecutivas, quebra por inadimplência. Ao fim do contrato (encerrado, quebrado, cancelado) a residência do inquilino volta à moradia inicial e a unidade fica livre.
- **Venda de imóvel alugado** (`10` §13): `buy_property` cede ao comprador, via `contracts.reassign_party`, os contratos em curso do prédio (PR de preparo do motor); o inquilino continua morando, os pagamentos futuros vão ao novo dono, dívidas já vencidas ficam com o antigo; o antigo dono perde a residência no prédio; anúncios de aluguel abertos são cancelados. Se o **inquilino** compra o imóvel, o contrato se encerra por `parties_merged` (H6).
- Ações no registro: `set_residence`, `list_rent`, `unlist_rent`, `rent_unit`. Auditoria: invariantes 6–8 (unidades × prédio, residente com direito, aluguel × título/unidade).

## 7. Lacunas da P1.07b (nenhuma mecânica nova; escolhas técnicas mínimas)

| # | Lacuna | Solução usada |
|---|---|---|
| H1 | O motor exige `ends_on` para pagamentos periódicos; `10` §9 não fala em prazo | Contrato de **prazo fixo** (`starts_on`..`ends_on`); renovar = novo contrato |
| H2 | Reajuste do aluguel (`10` §11 fala em lei de controle; `11` ainda não existe) | **Sem reajuste**: termos congelados (`18a`); a lei entra com P1.12 |
| H3 | Quem pode alugar: `10` §9 trata de moradia; aluguel comercial depende de P1.07c | Inquilino **jogador** (residencial); empresa inquilina em P1.07c |
| H4 | Quando começa o direito de ocupar | Quando `starts_on` é alcançado (`10` §9 "pagamento → ocupação"); o aceite exige `starts_on` futuro |
| H5 | Despejo (`10` §12) sem regra de prazo | Despejo = **quebra por inadimplência** quando `max_failures` (opcional; nulo = nunca) é atingido; só então a residência volta ao inicial |
| H6 | Inquilino compra o imóvel alugado | Contrato `closed` com `parties_merged`, sem multa (o design não prevê) |
| H7 | Uma pessoa por unidade (casais dependem de casamento, não definido) | Um residente por unidade |
| H8 | Voltar à moradia inicial por escolha (`set_residence` com `unit` nulo) | Permitido (sem custo); **marcado para o GD** se não for desejado |
| H10 | Dono quer morar numa unidade que anunciou para aluguel | Recusa `UNIT_LISTED_FOR_RENT` (simétrica a `list_rent` × `UNIT_OCCUPIED`): retira o anúncio antes |
| H9 | Dívidas de aluguel na venda; propostas abertas na venda | Dívidas ficam com o antigo locador; propostas abertas falham no aceite com `LANDLORD_NOT_OWNER` |

Seguem abertos (fora da P1.07b): limite de propriedade por jogador (lei), imposto de propriedade (G11), aluguel comercial, empresa inquilina.

## 8. O que a P1.07c entrega (parte que o design define)

- **Localização de empresa** (`CompanyLocation`; ação `set_company_location`, só o Dono): a empresa opera num **lote que ela possui**, cujo **uso** é o do seu tipo segundo o **zoneamento** (`geography.zoning`, 10 §22): Matriz → rural (08 §12), Industrial → industrial (08 §9), Varejo → comercial (08 §8; 10 §16), Serviços → comercial (08 §8, "quando a atividade exigir"). Um lote abriga uma empresa; o lote fica OCUPADO; deixar o lote ou vendê-lo (`buy_property`) encerra a localização.
- **Terreno da Matriz** (02 §2.1): o provedor de terreno de `companies.production` existe e a decisão está num **único ponto**, `properties.sites.terrain_of` (G12, regra A **provisória**, §10): produtos **comuns** (Agropecuária e Extrativismo não-petróleo: os sem `resource` no catálogo) em qualquer lote rural; produtos de **depósito** (petróleo e os 9 minerais: os com `resource`) só no lote que tem o depósito. Recusas em `set_production`: `PRODUCT_NOT_IN_TERRAIN`, `PRODUCT_OUTSIDE_TERRAIN_CATEGORY`; `TERRAIN_TYPE_UNDEFINED` fica para provedores que não saibam o tipo (ex.: opção B sem dado). O Trabalho da Matriz confere o terreno (`COMPANY_SITE_INVALID`, bloqueio antes de gastar Energia).
- Auditoria: invariante 9 (tipo localizável, lote da empresa, sem imóvel residencial, lote OCUPADO, sem obra ativa).

## 9. Lacunas da P1.07c (escolhas técnicas mínimas; nada novo foi criado como mecânica)

| # | Lacuna | Solução usada |
|---|---|---|
| J1 | Com que direito a empresa ocupa o lote (propriedade? aluguel? 10 §29 "aquisição e ocupação") | Só lote **da própria empresa** (título). Aluguel comercial depende de G5 |
| J2 | Quais tipos têm localização (08 §8 diz "varejo e serviços... quando a atividade exigir"; Construtora/Financeira não são citadas) | Matriz, Industrial, Varejo, Serviços. Construtora (constrói no lote que possui, 10 §28) e Financeira: **não localizáveis** |
| J3 | Quantas empresas por imóvel/lote | Uma (`[PROV]`; vale até G5 definir imóvel comercial/industrial) |
| J4 | **Exigir** localização para operar (vender no Varejo, produzir na Industrial, Trabalhar): o 10 §16 exige "localização, tipo de imóvel, estrela e atividade" **juntos**, e o tipo/estrela dependem de G5 | **Não exigido** (exceto Matriz, que já dependia do terreno). A localização existe e é consultável; ligar a exigência é decisão dentro de G5 |
| J5 | Atrito para mudar a empresa de lote | Nenhum: imediato e gratuito `[PROV]` |
| J6 | Venda do lote com a empresa localizada | A localização acaba (o comprador é outro dono); o lote volta a "vazio" |
| J7 | Lote com imóvel residencial como sede de empresa | Recusado (`LOT_HAS_BUILDING`): residência não é imóvel comercial/industrial |
| J8 | Produtos de Matriz em lote com depósito | Só o(s) do recurso do lote (08 §12 "não são escolhidos livremente") |

## 10. Decisões pendentes de design (G5, G6, G12)

### G5 — Tipos de imóvel comercial/industrial e estrela → nível
> **Direção do GD (2026-10-27): opção B como arquitetura final.** Proposta detalhada e pendências em §11.

**Design atual.** `10` §16: "A estrela da empresa determina o nível de imóvel comercial que ela pode ocupar. Isso se aplica especialmente ao Varejo. A empresa precisa atender simultaneamente: requisitos de localização; de tipo de imóvel; de estrela; de atividade." §17: industriais "precisam possuir uma localização compatível com seu tipo de atividade". §6 só tem números para o residencial. `02a` registra "Nível de imóvel comercial: a definir com `10` §16". Fluxo `10` §34: lote → leilão → empresa adquire → **Construtora constrói** → empresa ocupa → opera. O catálogo de obras (`companies.params.CONSTRUCTION_PROJECTS`) só tem os 4 residenciais.

| Opção | O que é | Bot Test | Sistemas posteriores |
|---|---|---|---|
| **A. O lote basta** | Sem prédios comerciais/industriais no Bot Test: a empresa se localiza num lote da categoria certa; a estrela não limita o imóvel | Rampa mais curta (leilão → localizar → operar); Construtora só demanda moradia; ignora o "nível" do §16 | Acrescentar níveis depois é aditivo (nova coluna/regra); aluguel comercial e imposto de propriedade ficam sem base de prédio |
| **B. Prédios comerciais/industriais com nível** | Tipos novos (ex.: comercial níveis 1–4; industrial 1 tipo ou por sub-tipo) com Construtora mínima, estrela mínima da empresa e obra no catálogo; localizar exige o prédio | Cadeia mais longa (leilão → obra com materiais → localizar): bots dependem de Construtoras e de Materiais de Construção; mais pontos de estrangulamento e de aprendizado | Base natural para aluguel comercial (handler `rent` com empresa inquilina, H3), imposto de propriedade (G11), capacidade de Varejo, expansão por estrela |
| **C. Híbrida** | Estrela 1 opera em lote; níveis ≥ 2 exigem prédio | Rampa curta e progressão por estrela com prédio | Mais regras a manter; o corte "★1 sem prédio" é invenção a validar |

**Recomendação (técnica e de gameplay): B**, com níveis = estrelas (nível *k* exige empresa ≥ *k*★ e Construtora ≥ *k*★, espelhando o residencial de 1★–4★), **um prédio por empresa** no Bot Test, **industrial com 1 tipo** (sub-tipos só se `22` os diferenciar), e a exigência de localização **ligada por parâmetro** (permite começar o Bot Test com o lote bastando — equivale a A — e ligar o prédio quando a cadeia de Construtoras estiver madura). Números: o GD define; se preferir, entram como `[PROV]` com os valores acima. Justificativa: é o fluxo que o `10` descreve, cria demanda real para a Construtora, e dá base ao aluguel comercial e ao imposto. A é a escolha segura **só** se o GD quiser adiar o nível comercial.

**O que o GD precisa responder:** (1) A, B ou C; (2) se B: nº de níveis e relação estrela→nível; (3) estrela mínima da Construtora por nível; (4) industrial: 1 tipo ou por sub-tipo; (5) quantas empresas por prédio; (6) a exigência de localização vale já para Varejo/Industrial/Serviços?

### G6 — Mudança de uso e quem aprova
> **Direção do GD (2026-10-27): opção B** (aprovação automática só se zoneamento e demais restrições permitirem, com gancho para aprovação política). Detalhes, consequências e custo em §12.

**Design atual.** `10` §21: "Um imóvel pode mudar de finalidade, desde que o governo aprove a alteração" (comercial↔residencial, industrial→outro uso permitido); "a mudança não é realizada livremente pelo proprietário"; o pedido é analisado por zoneamento vigente, leis federais, restrições do lote e projetos especiais. §33: "[ABERTO: quem aprova a mudança de uso]". `11` §11.7: alteração de zoneamento **por lei** não existe no primeiro Bot Test; "não existem leis municipais". §23: demolição e reforma profunda **não** existem no Bot Test.

| Opção | O que é | Bot Test | Sistemas posteriores |
|---|---|---|---|
| **A. Fora do Bot Test** | Nenhuma mudança de uso; o uso é o do zoneamento do lote | Menos ações; coerente com `11` §11.7 e `10` §23 | O pedido entra com P1.12 (Leis) |
| **B. Aprovação automática pelas regras** | O pedido é aceito se o zoneamento (`geography.zoning`, com overrides de lei) permite o novo uso; sem aprovador humano; fica registrado (histórico) | Ação nova simples, sem dependência política; sem dinheiro novo | Um aprovador político entra depois por gancho (`register_use_change_approver`), sem refazer o modelo |
| **C. Aprovador político** | O Executivo (federal; ou autoridade a definir) aprova cada pedido | Exige jogadores/bots em cargos e fila de pedidos; bloqueia o Bot Test se o cargo estiver vago | Alinhado ao design, mas depende de `06` (Política) e de definição de competência |

**Recomendação: B** para o Bot Test (aprovação = o zoneamento vigente permite), com gancho para o aprovador político da opção C quando `06`/`11` estiverem prontos. Como não há demolição (§23) e os tipos de imóvel são fixos, na prática B só se aplica a **lotes vazios** e a prédios cujo tipo continue válido no novo uso (o que depende de G5). Se o GD preferir A, nada é implementado agora e o item vira dependência de P1.12.

**O que o GD precisa responder:** (1) A, B ou C; (2) se C: quem aprova; (3) o pedido tem custo (hoje não existe natureza monetária para ele em `24`)?

### G12 — Tipo de terreno de lote rural **sem depósito** — **REGRA A PROVISÓRIA (GD 2026-10-27)**
**Decisão do GD.** Opção A como regra **provisória**, para destravar a cadeia de alimentos e madeira, mantendo o provedor de terreno substituível para evoluir à opção B sem reescrever os consumidores. **Prioridade de desbloqueio** (registrada em TASK/TASK_QUEUE).

**Design atual (que continua sem definir o tipo).** `02` §2.1: "a categoria da Matriz é determinada pelo tipo de terreno" (Terreno Agro → Matriz Agro; o dono escolhe o produto dentro da categoria). `08` §12: lotes rurais permitem Agropecuária, Extrativismo (inclui petróleo) e Mineração; os minerais "são definidos pelo sistema geográfico"; petróleo e minerais vêm de **depósitos** (§13-15). O `08` não define o tipo de um lote sem depósito.

**Como a regra A foi implementada (`properties/sites.py::terrain_of`, `params.TERRAIN_RULE = "G12-A-PROV"`):**
| Lote rural | Produtos que a Matriz pode escolher |
|---|---|
| **Sem depósito** | **Comuns**: Agropecuária (Trigo, Leite, Cana, Grão de café, Cacau, Carne, Ovos, Couro, Lã, Fruta) + Extrativismo **não-petróleo** (Madeira, Resina, Látex, Óleo natural, Ervas, Areia, Pedra, Químicos, Borracha). **Nunca** petróleo nem mineral |
| **Com depósito(s)** | O(s) recurso(s) **do próprio lote** (petróleo → Extrativismo; mineral → Mineração) **e**, `[PROV]` `DEPOSIT_LOTS_ALSO_COMMON = True`, também os comuns |

**Lotes com depósito (esclarecimento pedido pelo GD).** A regra A só fala do lote sem depósito. Para o lote **com** depósito há duas leituras do `08` §12; a implementada é a primeira, por ser a que o texto do `08` §12 sustenta ("lotes rurais permitem ... as três áreas"; o depósito define só QUAL recurso espacial existe, que "não é escolhido livremente"):
1. **Depósito acrescenta** (implementada, `[PROV]`): o lote com ferro sustenta ferro **e** os produtos comuns. Efeito no Bot Test: nenhum lote rural fica "preso" a uma só atividade; a escassez é só do recurso espacial (que continua exclusivo de quem tem o depósito). Risco: lote com depósito raro vale mais (ouro + agro), o que já é o efeito desejado da escassez.
2. **Depósito substitui**: o lote com depósito sustenta **só** o(s) recurso(s) dele. Efeito: mais fiel a "um terreno, uma categoria macro" (`02` §2.1); torna lotes agro e lotes minerais mutuamente exclusivos e reduz a oferta de lotes para agro/madeira onde há muitos depósitos. Basta `DEPOSIT_LOTS_ALSO_COMMON = False` (testado nos dois valores).
**O que o GD ainda precisa confirmar:** qual das duas leituras vale para lote com depósito (hoje: 1, provisória).

**Mantém substituível.** Só `terrain_of` decide; `terrain_categories`/`terrain_products` (provedores registrados em `companies.production`) e `production.site_refusal` não mudam com a opção B. `location_view` expõe a regra e o detalhamento (`terrain`: regra, `provisional`, depósitos, se os comuns valem). Testes cobrem: sem depósito (agro e extrativo comum sim; petróleo e minerais nunca), com depósito mineral e de petróleo, chave desligada, troca do ponto único por um terreno fictício (opção B simulada) e a recusa `TERRAIN_TYPE_UNDEFINED` para provedor sem dado.

**Para a opção B (destino).** Gerar um tipo de terreno por lote (fração agro/extrativista/mineral, agrupado como os recursos, `08` §13), guardado em atributo do lote (migração + regeração do mundo de teste); `terrain_of` passa a lê-lo. Impacto: nenhum nos consumidores.

## 11. G5 — proposta detalhada (direção do GD, 2026-10-27: **opção B**, prédios com nível ligados à estrela, Construtora e materiais)

> **Estado:** PROPOSTA — nada abaixo está implementado nem vira regra definitiva antes da resposta do GD. Números marcados `[PROPOSTA]` são sugestões; se o GD preferir, entram como `[PROV]`.

### 11.0. Ponto de interpretação que precisa de resposta
`10` §16: "A estrela da empresa **determina o nível** de imóvel comercial que ela **pode ocupar**." Duas leituras:
- **(i) Teto**: empresa de *n*★ pode ocupar prédio de nível **≤ n**. Problema: nível maior seria só um custo sem exigência nem benefício; ninguém construiria acima do nível 1.
- **(ii) Exigência (recomendada)**: empresa de *n*★ precisa de prédio de nível **≥ n** (pode ocupar um maior, só não um menor). A empresa que cresce precisa de espaço maior; isso cria demanda recorrente por Construtoras e materiais e dá sentido a cada nível.
Recomendação: **(ii)**. Consequência ligada a **P1.04f** (progressão de estrelas, parada): "Melhorar empresa" para *n+1* só vale se o prédio atual tiver nível ≥ *n+1* (ou a empresa muda para outro). O ponto é uma recusa nova e explicada (`BUILDING_LEVEL_TOO_LOW`), registrada em `02a` quando a P1.04f for retomada.

### 11.1. Relação estrela da empresa ↔ nível do prédio
| Item | Proposta |
|---|---|
| Faixa de níveis | **1 a 5** `[PROPOSTA]`, igual à faixa de estrelas proposta em `02a` §2.1 (o catálogo já vai de 1★ a 5★) |
| Regra | Nível do prédio ≥ estrela da empresa (11.0 ii) |
| Quem precisa de prédio comercial | **Varejo** (explícito no `10` §16) e **Serviços** (`08` §8: "quando a atividade exigir"; o design não diz quais, `[PROV]` todos) |
| Quem não precisa de prédio comercial | **Matriz** (terreno rural, §10), **Industrial** (prédio industrial, 11.4), **Construtora** (constrói no lote que possui; `10` §28) e **Financeira** (o design não define localização; segue sem local até decisão) |
| Quando a exigência vale | Parâmetro `REQUIRE_BUILDING_FOR_LOCATION` (hoje desligado = o lote basta, equivale à opção A). Ligar no Bot Test quando houver Construtoras e materiais suficientes (11.5) |
| O que a exigência bloqueia | Varejo: vender (`retail.fulfill_sale`); Industrial: produzir no Trabalho; Serviços: Trabalhar; todos com recusa explicada (`20`) |

### 11.2. Estrela mínima da Construtora por nível
O residencial já usa estrela mínima crescente (1★, 2★, 3★, 4★ para os 4 tipos, `10` §6). Proposta para o comercial: **nível *k* exige Construtora ≥ *k*★** `[PROPOSTA]` (1★…5★). Justificativa: uma empresa de *n*★ só opera num prédio de nível ≥ *n*, e o prédio só pode ser construído por quem tem pelo menos aquela estrela, de modo que **a progressão de uma cadeia (Varejo ★5) depende da progressão de outra (Construtora ★5)**: interdependência real entre jogadores. Trabalho para concluir (`work_units`, `02` §12): dobra a cada nível a partir do residencial simples (50): 50 / 100 / 200 / 400 / 800 `[PROPOSTA]`.

### 11.3. Empresas por prédio
**Uma empresa por prédio** no Bot Test `[PROPOSTA]` (hoje já é uma por lote, J3). Alternativa: vários "conjuntos" por prédio como as unidades residenciais (`10` §6). Consequência da alternativa: exige alocação, aluguel por conjunto e capacidade; sem base no design. Mantém-se uma por prédio até o GD pedir o contrário. A oferta de lotes comerciais/industriais é do cenário (`lot_capacity`, `08` §19), então o teto de empresas operando é o número de lotes comerciais/industriais do mapa; **o GD/cenário deve garantir lotes suficientes** para a população de bots.

### 11.4. Imóveis industriais e subtipos
- `10` §17 só pede "localização compatível com seu tipo de atividade" e diz que a **capacidade** vem de funcionários, skills, especialização, **não** do prédio. Não cita estrela.
- Proposta: **um único tipo de prédio industrial**, **sem nível** (qualquer estrela da Industrial o ocupa), Construtora ≥ **2★** `[PROPOSTA]` (obra mais pesada que o residencial simples), `work_units` 200 `[PROPOSTA]`.
- **Subtipos** (Produção, Alimentícia, Bens de consumo, Tecnológica; produtos do Exército saem de "Industrial/Produção"): **não** criar prédio por subtipo, porque o `22` não os diferencia em requisito de imóvel. "Compatível com o tipo de atividade" é atendido por **prédio industrial em lote industrial** (zoneamento, `08` §9). Se o GD quiser prédios por subtipo, precisa dizer quais e por quê.

### 11.5. Construção, materiais e custos nos sistemas existentes
- **Hoje** (`02` §10, `GAP_FINISHINGS_UNDEFINED` resolvida por Q7): a obra **não consome produtos**; o único insumo é o Trabalho dos funcionários (`work_units`).
- **O catálogo já traz a cadeia**: `construction_materials` (Industrial/Produção, 3★) ← cimento, aço, madeira, vidro; Acabamentos = Tábuas + Vidro (`02a`/Q7).
- **Proposta**: cada obra consome, do **estoque da Construtora**, `construction_materials` + acabamentos em quantidade por projeto `[PROPOSTA a calibrar]`, retirados pela trilha imutável de estoque (`02` §11.1) **no início do Trabalho que avança a obra** (bloqueio antes de gastar Energia). Sem estoque, a obra para (`CONSTRUCTION_NO_MATERIALS`), nunca é criada do nada. Os materiais são **consumidos** (destruídos como bem), sem criar dinheiro.
- **Custos e dinheiro**: o custo da Construtora é (a) salários (`WAGE`, já existe) e (b) a compra dos materiais, que depende do **Mercado entre empresas (P1.05b, bloqueada por decisão do GD)**. Até a P1.05b, a única forma de ter materiais é a **produção própria/contratos de Fornecimento** (`18`, já implementado: `SALE`). O preço do prédio é o que o dono pedir no anúncio (`10` §8, sem imposto, `24` §24.7). Nenhuma nova natureza monetária é necessária.
- **Parâmetro**: `CONSTRUCTION_CONSUMES_MATERIALS` (desligado enquanto P1.05b/Fornecimento não bastarem). Evita travar a cadeia da Construtora no Bot Test e permite ligar sem reescrever.

### 11.6. O que pode avançar sem esses detalhes (e o que não)
| Parte | Situação |
|---|---|
| Generalizar `Building`/`params.BUILDING_TYPES` (famílias residencial/comercial/industrial, nível opcional, unidades opcionais) | **Pode avançar**, é refatoração sem regra nova; só vale a pena depois da resposta 11.0 (evita refazer). **Não feito agora.** |
| Provedor de "prédio da empresa" para Varejo/Industrial/Serviços e recusas `BUILDING_LEVEL_TOO_LOW`/`NO_BUILDING` | Depende de 11.0 e 11.1 |
| Aluguel comercial (empresa inquilina, H3) | Depende de 11.3 (quantas empresas por prédio) e de G5 fechada |
| Consumo de materiais na obra | Depende de 11.5 e, para o preço real, de P1.05b |
| Imposto de propriedade/IPTU comercial (G11) | Depende de P1.09/P1.12 |
| Ligação com P1.04f | Depende de 11.0 |
| Localização atual (lote basta), terreno, auditoria | **Já implementado** |

**Decisões do GD para fechar G5:** (1) 11.0: (i) ou (ii); (2) níveis 1–5 e regra nível ≥ estrela; (3) Construtora ≥ *k*★ e `work_units` por nível; (4) uma empresa por prédio; (5) industrial: um tipo sem nível, Construtora ≥ 2★ (ou outro); (6) subtipos industriais: sim/não; (7) consumo de materiais na obra: agora ou depois da P1.05b; (8) `REQUIRE_BUILDING_FOR_LOCATION`: ligar já ou depois.

## 12. G6 — proposta detalhada (direção do GD, 2026-10-27: **opção B**, aprovação automática restrita, com gancho para aprovação política)

> **Estado:** PROPOSTA — nada implementado. Honestidade técnica (CLAUDE.md §13): **a opção B quase não tem caso aplicável no Bot Test**, pelos motivos abaixo.

### 12.1. O que a opção B significa
Aprovação **automática** só quando **todas** as condições valem; nenhuma delas pode ser contornada pela aprovação:
1. o **zoneamento** (`geography.zoning.decide`, incluindo overrides de lei) permite o novo uso no lote;
2. o imóvel não tem **moradores nem aluguel em vigor** (ninguém perde a casa por um pedido do dono), nem empresa operando que dependa do uso antigo;
3. sem **anúncio de venda/aluguel aberto, leilão ou obra ativa** no lote;
4. restrições do lote e regras especiais (`10` §21), via os mesmos ganchos de elegibilidade (`register_eligibility`);
5. o **ponto de integração político** (`register_use_change_approver`, hoje sem aprovador registrado = aprova) pode **apenas negar** além disso, **nunca aprovar o que 1–4 recusam**.
Recusa explicada (`20`) com a condição que falhou. Histórico imutável do pedido (quem, quando, uso antigo → novo, decisão, referência).

### 12.2. Consequências para o Bot Test (confirmadas contra o código)
- **Zoneamento padrão**: `geography.zoning.base_permissions` só permite cada categoria **nela mesma** (`{c: {c}}`) quando o cenário não define `zoning_permissions`. Logo, **com o zoneamento padrão toda mudança de uso é recusada** (`LOT_USE_NOT_ALLOWED`): no Bot Test padrão a opção B **não aprova nada**. Só passa a aprovar em cenários com mistura configurada (`Scenario.zoning_permissions`, decisão do GD de 2026-10-03) ou com leis de zoneamento (P1.12; `11` §11.7 diz que **não existem** no primeiro Bot Test).
- **Sem demolição/reforma** (`10` §23, `§32`): a mudança de um **prédio já construído** exige um **mapeamento de conversão** (residencial → comercial de qual nível? as unidades e a QoL somem) que o design não define e que depende de G5. Para **lote vazio**, "uso" é a categoria do lote, que é o próprio zoneamento (não há o que aprovar).
- Portanto, no Bot Test a B é: (a) o **ponto de integração** e a **função de decisão** corretos, (b) testável em cenário com zoneamento misto, (c) **sem efeito** no cenário padrão. Não bloqueia nada, e não deve ser tratada como cobertura do `10` §21 além disso.

### 12.3. Custo da mudança
Não há natureza em `24` para custo de mudança de uso (lista fechada, §24.8): **não inventei custo**.
| Opção | Efeito | Consequências |
|---|---|---|
| **a. Gratuito, parâmetro explícito** `USE_CHANGE_FEE_CENTS = 0` `[PROV]`; valor > 0 recusado (`USE_CHANGE_FEE_UNDEFINED`) | Sem dinheiro | Mesmo padrão já usado no custo da troca de produção (`PRODUCTION_CHANGE_COST_UNDEFINED`); sem risco de conservação; sem desincentivo a pedidos |
| **b. Nova natureza `USE_CHANGE_FEE`**: proprietário → **Município do lote** | Receita municipal; conservação preservada (transferência) | Muda o `24` (lista fechada) = decisão do GD; analogia com `AUCTION_PAYMENT` (lote → Município); entra no teto de déficit como receita do Município |
| **c. Reusar natureza existente** | — | **Não recomendado**: nenhuma natureza descreve o fato; falsearia a auditoria |
**Recomendação: (a) agora** (parâmetro explícito, recusa se > 0) e **(b) quando o GD definir um valor**, com destino Município (receita local, simétrico ao leilão) e sem sumidouro (não há motivo para destruir o dinheiro).

### 12.4. Dependências e o que pode avançar
- Função de decisão e gancho do aprovador: **podem ser escritos já**, mas sem ação visível não têm caso de uso; entram **com G5** (tipos de prédio e mapeamento de conversão).
- A integração com a aprovação política depende de `06`/P1.11 (cargos) e de `11` (competência); o gancho existe sem elas.

**Decisões do GD para fechar G6:** (1) confirmar B com as 5 condições de 12.1; (2) mapeamento de conversão de prédio construído (depende de G5) ou restringir a mudança de uso a cenários com zoneamento misto no Bot Test; (3) custo: (a) agora e (b) depois, ou valor/destino já.
