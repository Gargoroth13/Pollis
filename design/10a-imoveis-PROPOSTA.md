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
| **P1.07c** | Localização de empresas, terreno da Matriz (`production.register_site_provider`) | **parcial** (§8): feito o que o design define; **G5** (tipos comercial/industrial), **G6** (mudança de uso) e **G12** (tipo de terreno rural sem depósito) aguardam o GD (§10) |

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

Para concluir a **P1.07c**: **G5**, **G6** e **G12** (§10: trecho do design, opções, recomendação e impacto). O que não depende delas já está implementado (§8).

Da P1.07b nenhuma decisão **bloqueia** a próxima etapa; as lacunas H1–H10 (§7) seguem provisórias (**H6** e **H8** para o GD vetar). G1 precisa ser decidida antes de o Bot Test ligar os bots.

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
- **Terreno da Matriz** (02 §2.1): o provedor de terreno de `companies.production` agora existe. O terreno é **derivado dos depósitos reais do lote rural** (08 §12-15): petróleo → Extrativismo, minerais → Mineração, e a Matriz produz **o produto do recurso do lote** (a chave do recurso é a do produto; teste confere o setor). Recusas novas em `set_production`: `PRODUCT_NOT_IN_TERRAIN`, `TERRAIN_TYPE_UNDEFINED` (lote rural **sem** depósito: ver **G12**). O Trabalho da Matriz confere o terreno (`COMPANY_SITE_INVALID`, bloqueio antes de gastar Energia).
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
**Design atual.** `10` §16: "A estrela da empresa determina o nível de imóvel comercial que ela pode ocupar. Isso se aplica especialmente ao Varejo. A empresa precisa atender simultaneamente: requisitos de localização; de tipo de imóvel; de estrela; de atividade." §17: industriais "precisam possuir uma localização compatível com seu tipo de atividade". §6 só tem números para o residencial. `02a` registra "Nível de imóvel comercial: a definir com `10` §16". Fluxo `10` §34: lote → leilão → empresa adquire → **Construtora constrói** → empresa ocupa → opera. O catálogo de obras (`companies.params.CONSTRUCTION_PROJECTS`) só tem os 4 residenciais.

| Opção | O que é | Bot Test | Sistemas posteriores |
|---|---|---|---|
| **A. O lote basta** | Sem prédios comerciais/industriais no Bot Test: a empresa se localiza num lote da categoria certa; a estrela não limita o imóvel | Rampa mais curta (leilão → localizar → operar); Construtora só demanda moradia; ignora o "nível" do §16 | Acrescentar níveis depois é aditivo (nova coluna/regra); aluguel comercial e imposto de propriedade ficam sem base de prédio |
| **B. Prédios comerciais/industriais com nível** | Tipos novos (ex.: comercial níveis 1–4; industrial 1 tipo ou por sub-tipo) com Construtora mínima, estrela mínima da empresa e obra no catálogo; localizar exige o prédio | Cadeia mais longa (leilão → obra com materiais → localizar): bots dependem de Construtoras e de Materiais de Construção; mais pontos de estrangulamento e de aprendizado | Base natural para aluguel comercial (handler `rent` com empresa inquilina, H3), imposto de propriedade (G11), capacidade de Varejo, expansão por estrela |
| **C. Híbrida** | Estrela 1 opera em lote; níveis ≥ 2 exigem prédio | Rampa curta e progressão por estrela com prédio | Mais regras a manter; o corte "★1 sem prédio" é invenção a validar |

**Recomendação (técnica e de gameplay): B**, com níveis = estrelas (nível *k* exige empresa ≥ *k*★ e Construtora ≥ *k*★, espelhando o residencial de 1★–4★), **um prédio por empresa** no Bot Test, **industrial com 1 tipo** (sub-tipos só se `22` os diferenciar), e a exigência de localização **ligada por parâmetro** (permite começar o Bot Test com o lote bastando — equivale a A — e ligar o prédio quando a cadeia de Construtoras estiver madura). Números: o GD define; se preferir, entram como `[PROV]` com os valores acima. Justificativa: é o fluxo que o `10` descreve, cria demanda real para a Construtora, e dá base ao aluguel comercial e ao imposto. A é a escolha segura **só** se o GD quiser adiar o nível comercial.

**O que o GD precisa responder:** (1) A, B ou C; (2) se B: nº de níveis e relação estrela→nível; (3) estrela mínima da Construtora por nível; (4) industrial: 1 tipo ou por sub-tipo; (5) quantas empresas por prédio; (6) a exigência de localização vale já para Varejo/Industrial/Serviços?

### G6 — Mudança de uso e quem aprova
**Design atual.** `10` §21: "Um imóvel pode mudar de finalidade, desde que o governo aprove a alteração" (comercial↔residencial, industrial→outro uso permitido); "a mudança não é realizada livremente pelo proprietário"; o pedido é analisado por zoneamento vigente, leis federais, restrições do lote e projetos especiais. §33: "[ABERTO: quem aprova a mudança de uso]". `11` §11.7: alteração de zoneamento **por lei** não existe no primeiro Bot Test; "não existem leis municipais". §23: demolição e reforma profunda **não** existem no Bot Test.

| Opção | O que é | Bot Test | Sistemas posteriores |
|---|---|---|---|
| **A. Fora do Bot Test** | Nenhuma mudança de uso; o uso é o do zoneamento do lote | Menos ações; coerente com `11` §11.7 e `10` §23 | O pedido entra com P1.12 (Leis) |
| **B. Aprovação automática pelas regras** | O pedido é aceito se o zoneamento (`geography.zoning`, com overrides de lei) permite o novo uso; sem aprovador humano; fica registrado (histórico) | Ação nova simples, sem dependência política; sem dinheiro novo | Um aprovador político entra depois por gancho (`register_use_change_approver`), sem refazer o modelo |
| **C. Aprovador político** | O Executivo (federal; ou autoridade a definir) aprova cada pedido | Exige jogadores/bots em cargos e fila de pedidos; bloqueia o Bot Test se o cargo estiver vago | Alinhado ao design, mas depende de `06` (Política) e de definição de competência |

**Recomendação: B** para o Bot Test (aprovação = o zoneamento vigente permite), com gancho para o aprovador político da opção C quando `06`/`11` estiverem prontos. Como não há demolição (§23) e os tipos de imóvel são fixos, na prática B só se aplica a **lotes vazios** e a prédios cujo tipo continue válido no novo uso (o que depende de G5). Se o GD preferir A, nada é implementado agora e o item vira dependência de P1.12.

**O que o GD precisa responder:** (1) A, B ou C; (2) se C: quem aprova; (3) o pedido tem custo (hoje não existe natureza monetária para ele em `24`)?

### G12 — Tipo de terreno de lote rural **sem depósito** (descoberto na P1.07c; bloqueia a Matriz agro/extrativista)
**Design atual.** `02` §2.1: "a categoria da Matriz é determinada pelo tipo de terreno em que ela está localizada" (Terreno Agro → Matriz Agro). `08` §12: lotes rurais permitem Agropecuária, Extrativismo (inclui petróleo) e Mineração; petróleo e minerais vêm de **depósitos** distribuídos espacialmente (§13-15). O `08` **não define** o tipo de um lote rural sem depósito, nem de onde vêm Agropecuária (Trigo, Leite, …) e o Extrativismo que não é petróleo (Madeira, Resina, …). O gerador só guarda depósitos (petróleo + 9 minerais).

| Opção | O que é | Bot Test | Sistemas posteriores |
|---|---|---|---|
| **A. Lote rural sem depósito = Agro + Extrativismo não-petróleo** | Regra única: depósito acrescenta Mineração/petróleo; sem depósito, o lote permite os produtos agro e os extrativos comuns | Resolve já a cadeia de alimentos e materiais; sem escassez territorial para agro | Simples; geografia de agro/madeira fica uniforme (sem "regiões ricas") |
| **B. Atributo de terreno por lote, gerado** | Cada lote rural recebe um tipo (agro / extrativista / mineral) ou fração de cada, com distribuição espacial agrupada como os recursos (08 §13) | Mais fiel ao `08` ("regiões"); exige regerar o mundo/migração e parâmetros (frações) | Base para riqueza regional, transporte e preço regional |
| **C. O dono escolhe o terreno ao localizar a Matriz** | O tipo é escolha do jogador | Contradiz "determinada pelo terreno" (`02` §2.1) | Remove escassez territorial |

**Recomendação: B** no destino, mas **A como regra inicial `[PROV]`** para destravar já a cadeia de alimentos do Bot Test (e migrar para B sem alterar a API: o provedor de terreno já é o ponto de troca). Impacto: sem uma resposta, **nenhuma Matriz agro nem extrativista não-petróleo pode produzir** (a cadeia de alimentos e de madeira fica parada); mineração e petróleo já funcionam com os depósitos reais.

**O que o GD precisa responder:** (1) A, B ou C; (2) se B: frações de agro/extrativista/mineral por lote rural; (3) um lote com depósito também permite agro/extrativismo comum?
