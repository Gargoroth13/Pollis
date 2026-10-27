# Polis — CHANGELOG DEV

Registro das decisões importantes de design e desenvolvimento que precisam permanecer visíveis para os agentes.

---

## 2026-10-27 — G12 provisória (regra A), propostas detalhadas de G5/G6 e orientação do GD (`design/10a` §10–§12)

**Orientação do GD (2026-10-27).** G5: opção B como arquitetura final (prédios com nível ligados à estrela, Construtora e materiais; não eliminar do Bot Test); antes de fechar a regra, detalhar a proposta. G6: opção B (aprovação automática só se o zoneamento e as demais restrições permitirem, sem contornar restrições nem leis; gancho para aprovação política); custo sem inventar. **G12: opção A como regra provisória** para destravar alimentos e madeira, provedor substituível, e esclarecer lotes com depósito. P1.09 segue se não comprometer dependências. H6 e H8 continuam provisórios. Nenhum merge.

**G12 implementado.** `properties.sites.terrain_of` é o ponto único: sem depósito → produtos **comuns** (Agro + Extrativismo sem `resource` no catálogo); com depósito → o recurso do lote **e** (`DEPOSIT_LOTS_ALSO_COMMON = True` `[PROV]`, aguarda confirmação) os comuns; petróleo e minerais nunca sem depósito. `TERRAIN_TYPE_UNDEFINED` fica só para provedores sem dado. `location_view` expõe a regra (`G12-A-PROV`, provisória). Testes: sem depósito, mineral, petróleo, chave desligada, troca do ponto único (opção B simulada), `COMPANY_SITE_INVALID`.

**G5/G6 detalhados sem implementar** (`design/10a` §11–§12). G5: ponto de interpretação 11.0 do `10` §16 (teto × exigência; recomendada: exigência, nível do prédio ≥ estrela), níveis 1–5, Construtora ≥ k★, uma empresa por prédio, industrial com um tipo sem nível (Construtora ≥ 2★), sem subtipos, consumo de materiais na obra por parâmetro (depende da P1.05b para preço real), `REQUIRE_BUILDING_FOR_LOCATION` desligado. G6: com o zoneamento padrão (`{c:{c}}`) a opção B **não aprova nada** no Bot Test; custo gratuito por parâmetro (`USE_CHANGE_FEE_CENTS = 0`, >0 recusado) até haver natureza em `24`.

## 2026-10-27 — P1.07c (parcial) — Localização de empresas e terreno da Matriz (`design/10` §16-17, §29; `02` §2.1; `08` §8-§12; lacunas em `design/10a` §8–§10)

**Decisão de execução (instrução do GD, 2026-10-26).** G5 e G6 não podem parar a etapa: foi implementado tudo o que o design define sem elas; nenhum valor ou regra permanente foi inventado para contornar os bloqueios. A P1.07c vem empilhada sobre a P1.07b (#25).

**Entregue (app `properties`, `companies.production`):** `CompanyLocation` (uma empresa ↔ um lote **da própria empresa**; migração `0003`); ação `set_company_location` (só o Dono; `lot` nulo = sai do lote); o **uso** do lote exigido pelo tipo vem do zoneamento (`geography.zoning`): Matriz → rural, Industrial → industrial, Varejo/Serviços → comercial; Construtora e Financeira não são localizáveis; venda do lote encerra a localização (`buy_property`); o lote fica OCUPADO. **Terreno da Matriz:** provedor de terreno (`production.register_site_provider`) derivado dos **depósitos reais** do lote rural (petróleo → Extrativismo; minerais → Mineração; a Matriz produz o produto do recurso do lote) e novo provedor de produtos do terreno; `set_production` ganha `TERRAIN_TYPE_UNDEFINED` e `PRODUCT_NOT_IN_TERRAIN`; o Trabalho da Matriz confere o terreno (`COMPANY_SITE_INVALID`, antes de gastar Energia). `audit_properties` invariante 9.

**Não feito por depender do GD (documentado em `design/10a` §10, com trecho do design, opções, recomendação e impacto):** **G5** tipos de imóvel comercial/industrial e estrela → nível (e, por consequência, **exigir** localização para vender/produzir/trabalhar e aluguel comercial: J4); **G6** mudança de uso e aprovador; **G12** (nova) tipo de terreno de lote rural **sem depósito** — enquanto não houver resposta nenhuma Matriz agro/extrativista não-petróleo pode produzir (`TERRAIN_TYPE_UNDEFINED`); a cadeia de alimentos/madeira do Bot Test fica parada, mineração e petróleo funcionam.

**Lacunas J1–J8** (`design/10a` §9) `[PROV]`/técnicas: só lote da própria empresa; uma empresa por lote; troca de lote imediata e gratuita; Serviços localizáveis em comercial. **H6 e H8 da P1.07b seguem provisórios** (não foram necessários aqui).

**Prova:** testes de localização, venda, terreno, auditoria e registro (`properties/tests/test_sites.py`), concorrência (`SitesConcurrencyTests`; a corrida venda × localizar é só-PG), regressões de `companies.production`. Resultados das suítes completas: ver o PR.

## 2026-10-26 — P1.07b — Unidades, residência ativa, Aluguel e QoL do imóvel (`design/10` FINAL — BOT TEST §6.1, §9–§15; lacunas em `design/10a` §6–§7)

**Decisão de execução.** Segue a ordem da P1.07 (a, b, c). A P1.07b vem empilhada sobre o PR de preparo do motor (#24: cessão de parte), que por sua vez está sobre a P1.07a (#23). Nada saiu do escopo do Bot Test.

**Entregue (app `properties`):** `Unit`, `ActiveResidence`, `Tenancy`, `RentListing`; `housing` (direito de morar, `set_residence`, QoL do prédio como provedor `residence_building`); `rent` (handler `RentHandler` do tipo `rent` do motor de `18`, `list_rent`/`unlist_rent`/`rent_unit`, venda do imóvel alugado cedendo os contratos via `reassign_party`); invariantes 6–8 em `audit_properties`; migração `0002` (cria unidades dos imóveis existentes). Aluguel pago do inquilino ao locador com natureza `RENT`, sem imposto; inadimplência e quebra seguem o motor (obrigação, `defaulted`, `max_failures`). Ações novas no registro: `set_residence`, `list_rent`, `unlist_rent`, `rent_unit`.

**G9 resolvida pelo texto do design** (`04` §24, `10` §14): moradia inicial = ausência de `ActiveResidence`. Não foi necessário perguntar ao GD.

**Lacunas H1–H10** em `design/10a` §7 (prazo fixo; sem reajuste; inquilino jogador; ocupação a partir de `starts_on`; despejo = quebra por `max_failures`; `parties_merged` se o inquilino compra; um residente por unidade; volta voluntária à moradia inicial **para decisão do GD se indesejada**; dívidas ficam com o antigo locador).

**Prova:** 14 testes de moradia + 32 de aluguel + 7 de concorrência PG (inquilinos simultâneos, aceites simultâneos, venda × aceite, venda × morar, anúncio × morar, moradores simultâneos). Mutação dos locks (remover `select_for_update` num ponto por vez, 3–4 rodadas de `RentConcurrencyTests`): `rent.py` ativação 1/3, fechamento da venda 2/3, anúncio 2/3, `rent_unit` 2/4; `housing.py` trava do lote 1/4, trava do jogador 4/4. Os testes de corrida **não** detectam toda mutação em toda rodada (dependem de temporização); as unicidades do banco (`Tenancy.contract_id`, `ActiveResidence.unit/player`) são a segunda linha de defesa. Três testes de corrida entre tabelas (venda × aceite, venda × morar, anúncio × morar) só valem em PostgreSQL (`skipUnless`, como em `ledger/tests/test_scenario_concurrency.py`), porque dependem do `FOR UPDATE` do lote. **Bug real achado por esses testes:** `set_residence` não recusava morar numa unidade com anúncio de aluguel aberto (anúncio aberto + morador, até em sequência, e em PG em 1 de ~4 rodadas); corrigido com a recusa `UNIT_LISTED_FOR_RENT` (o dono retira o anúncio antes), invariante `OPEN_RENT_LISTING_ON_OCCUPIED_UNIT` na auditoria e testes.

## 2026-10-26 — P1.08b-prep — Cessão de parte e gancho de fim de contrato (motor de `design/18`; detalhes em `design/18a` §6)

**Por quê.** `10` §13 manda o aluguel acompanhar a venda do imóvel (o contrato continua e os pagamentos passam ao novo proprietário); o motor não tinha como trocar uma parte. Feito como PR separado para a P1.07b (Aluguel) ficar pequena e revisável.

**Entregue (app `contracts`):** `reassign_party` (cessão registrada em `ContractPartyChange` + evento `party_changed`; selo dos termos sobre as partes de origem; partes vigentes guardadas em cada ocorrência); fusão de partes encerra o contrato (`parties_merged`, sem multa); `Handler.on_ended` e `Handler.audit_success`; a execução diária relê as partes depois de travar o contrato; migração `0002` (preenche `sealed_parties`/`parties` dos contratos existentes); auditoria da cadeia de cessões e das partes de cada ocorrência.

**Prova:** 8 testes novos (+1 de concorrência em PG: cessão × execução diária, mutação sem a trava da cessão falha em 3 de 4 rodadas).

## 2026-10-25 — P1.07a — Propriedade de lotes, leilões, venda e obra com lote (`design/10` FINAL — BOT TEST; lacunas em `design/10a`)

**Decisão de execução.** P1.07 dividido em a (propriedade, leilão, venda, imóvel residencial, obra com lote), b (unidades, residência ativa, Aluguel como handler do motor de `18`, QoL) e c (localização de empresas, Matriz, mudança de uso). Nada saiu do escopo do Bot Test; só a ordem. A P1.07a vem empilhada sobre o PR #22 (contratos).

**Entregue (app `properties`):**
- `LotTitle` (dono atual; sem linha = governo), `TitleEvent` (histórico imutável e contínuo, com preço e chave do lançamento), `Auction`/`AuctionBid` (lances imutáveis), `Listing`, `Building`, `ConstructionSite`.
- Leilão: lance mínimo e crescente, sem reserva de fundos (conferido no lance e no encerramento), extensão por lance na janela final, encerramento no tick de 10 minutos (idempotente), `AUCTION_PAYMENT` ao Município do lote, título no mesmo ato; sem lances = `UNSOLD`; sem fundos = `INVALIDATED` (lacuna G2).
- Venda de imóvel: `SALE` sem imposto (`24` §24.7) + título; empresa age pelo Dono; recusada durante obra ativa.
- Obra com lote: `companies.construction` ganhou `lot` opcional com validador/hook de início (`register_start_validator/hook`); Imóveis valida dono = a própria Construtora, lote vazio, zoneamento permite moradia, sem anúncio/obra; a conclusão cria o `Building` e ocupa o lote na mesma transação do Trabalho.
- Ações no registro: `bid_auction`, `list_property`, `unlist_property`, `buy_property`; `lot` em `start_construction`. Abrir leilão é ferramenta do sistema (`open_auctions`), não ação de jogador (lacuna G1).
- `audit_properties` (invariantes 1–5) e `manage.py audit_properties [--json]`; `wipe_world` dos testes limpa as tabelas novas.
- Concorrência (PostgreSQL), provada por mutação: remover as travas de lance, de anúncio/início de obra e de compra faz os testes falharem; o fechamento do leilão resiste mesmo sem as travas porque a chave do lançamento e a unicidade do `TitleEvent` o protegem (as travas são defesa em profundidade).

**Fora desta etapa:** G1–G11 de `design/10a` (a G9, moradia inicial, é a que a P1.07b precisa do GD; há solução padrão sem mecânica nova).

## 2026-10-23 — P1.08a — Motor de Contratos (`design/18` FINAL — BOT TEST; lacunas em `design/18a`)

**Decisão de execução.** Contratos foi feito antes de Imóveis (P1.07) porque aluguel e obras de P1.07 dependem do motor. P1.08 dividido em a (motor + Fornecimento + Empréstimo), aluguel (P1.07), governamental (P1.09), militar (P1.17); nada saiu do escopo do Bot Test. Cada tipo é um *handler* registrado, o motor não os conhece.

**Antes:** `market.record_sale` e `audit_market` passam a aceitar pagamento tributado (`SALE` líquida + `TAX_SALES` do comprador = total), com testes.

**Entregue (app `contracts`):**
- `Contract` (termos congelados e selados por `terms_hash`; `save` recusa alteração), `ContractEvent` (histórico imutável e contínuo, `ref` único por tipo de evento) e `ContractExecution` (única por contrato e sequência = idempotência).
- Proposta/aceite (quem propõe já aceita; ativa com o 2º aceite; efeito do tipo no mesmo instante, desfeito se falhar), recusa, retirada, expiração de proposta vencida, quebra voluntária com multa real (`PENALTY`), quebra por `max_failures`, encerramento normal (`completed` / `completed_with_failures`).
- Execução no tick diário do mundo (prioridade 70) com catch-up; quitação das dívidas de contratos antes das novas ocorrências; reconciliação do histórico.
- Fornecimento (empresas): estoque + pagamento tributado (5% retido do valor) + `market.record_sale` (canal `contract`) em um ato tudo-ou-nada. Empréstimo (jogadores): desembolso `LOAN_PRINCIPAL`, parcelas `LOAN_REPAYMENT`/`LOAN_INTEREST`, falha vira obrigação.
- 5 ações no Action Registry (`propose/accept/decline/withdraw/break_contract`), mesmas recusas em disponibilidade e execução.
- `audit_contracts` (+ `manage.py audit_contracts [--json]`): invariantes 1 (contrato/termos/contadores/agenda), 2 (histórico), 3 (dinheiro e estoque por ocorrência, multa), 4 (chaves órfãs).
- Concorrência provada por mutação em PostgreSQL: remover as travas de execução e de aceite faz 5 dos 6 testes de concorrência falharem.

**Decisões do GD (2026-10-24), aplicadas no mesmo PR:** ocorrência falha é perdida (não refeita); `max_failures` = falhas **consecutivas** (cumprida zera, `consecutive_failures`); juros simples com taxa e **total congelados** nos termos (`interest_total_cents`); quebra de empréstimo: principal restante vira obrigação, juros futuros cancelados; fornecimento só entre empresas (SALE líquida + `TAX_SALES`); qualidade entregue congelada na entrega (limitação: o estoque guarda uma qualidade média por produto); multa não paga numa quebra **não impede a quebra** — vira UMA obrigação pendente (`PENALTY_UNPAYABLE` removido); calendário, reserva de fundos (nenhuma; verificação+transferência atômicas), responsabilidade por código (`Handler.RESPONSIBILITY`, auditada) e quitação global confirmados. Detalhes e testes em `design/18a` §5.

## 2026-10-22 — P1.06a — Núcleo de Escolas (`design/03` REVIEW; proposta e lacunas em `design/03a`)

**Decisão de execução.** O `03` está em REVIEW e depende de sistemas ainda não implementados (Imóveis P1.07, Orçamento P1.09, Mercado P1.05b) e tem parâmetros em aberto. P1.06 foi dividido em a–d; nada foi removido do escopo do Bot Test. Valores numéricos ausentes entram como `[PROV]` em `schools/params.py`; estruturas ausentes/ambíguas estão em `design/03a` e nas "Decisões necessárias do Game Director".

**Entregue (app `schools`):**
- `School` (pública sem dono / particular com dono; estrela; materiais em cache), escola pública de origem por bairro (criada no primeiro uso, índice único parcial), `Enrollment` (uma ativa por jogador; histórico contínuo).
- Matrícula inicial automática (hook de criação `travel.schools`, depois de `travel`): só públicas; nunca recusada por falta de vaga (registrado em `03a`, decisão 1). Troca de escola (`change_school`, no Action Registry): só no mesmo bairro, recusa `SCHOOL_FULL` quando a capacidade é conhecida; travas jogador → escola.
- Capacidade = residências do bairro × 1,5 (`Explained`), via provedor (`register_residence_provider`; P1.07). Sem provedor: "Sem dados".
- Materiais (`school_supplies`): limite por estrela `[PROV]`, trilha imutável, entrada só por compra (pagamento ligado em P1.05b), decaimento `[PROV]` 2%/dia HALF_EVEN.
- Qualidade diária (tick diário do mundo, prioridade 60): retrato dos materiais da TRILHA antes do início do dia (independe da ordem de compra no segundo exato da virada) → qualidade = base (1:1, limitada pela estrela) + bônus de professores (0 até P1.06b); decaimento depois do retrato; idempotente; `QualityDay` imutável com `Explained`.
- `audit_schools` (+ `manage.py audit_schools [--json]`): invariantes 1 (escolas), 2 (materiais/cadeia/decaimento), 3 (matrículas contínuas, mesmo bairro, todo jogador com escola), 4 (qualidade recalculada).
- Concorrência em PostgreSQL provada por mutação: remover a trava da escola em `change_school`, `credit_materials` e `run_cycle` faz os testes correspondentes falharem.

**Fora desta etapa:** professores/diretor/salários e mensalidade (P1.06b), universidade e diplomas (P1.06c), ligações com Imóveis/Orçamento/Mercado (P1.06d). O fator de escola do Estudar continua neutro (1) até o GD definir o mapeamento qualidade → ganho de skill (`03a`, decisão 2).

## 2026-10-22 — P1.05a — Transparência de Mercado (`design/17`; proposta em `design/17a`)

**Contexto e decisão.** O `17` (FINAL — BOT TEST) define a transparência do mercado, mas nenhum documento define o **mecanismo** que produz vendas (anúncios, quem fixa preço, taxas, matching; `05` §13/§22 lista isso como questão em aberto). Conforme CLAUDE.md §13, o mecanismo **não foi inventado**: implementou-se tudo o que o `17` define, com um único ponto de integração, e a proposta/lacunas foram registradas em `design/17a-mercado-PROPOSTA.md` e levadas às "Decisões necessárias do Game Director". Nada do escopo do Bot Test foi removido: o mecanismo é a etapa **P1.05b**, bloqueada só pela decisão.

**Entregue (app `market`):**
- `recording.record_sale`: histórico imutável (`MarketTransaction`: produto, quantidade, preço unitário e total em centavos, instante, dia de competência, comprador/vendedor, canal, chave do pagamento). Só registra se existir **um** lançamento `SALE` do comprador ao vendedor pelo valor total, não estornado (sem venda sem dinheiro real movido); idempotente pela chave do pagamento; recusas com código. Não move dinheiro.
- Agregação (`rollup`): histórico bruto → dia fechado (`DailyProductStat`, `CompanyCostDay`, `RollupMark`) → páginas leem o agregado. Fechamento sob demanda e pelo tick diário (prioridade 90), idempotente e seguro com concorrência (unicidade); dia corrente nunca gravado (calculado ao vivo). Retrato da oferta só em tick processado no próprio dia.
- `stats`: preço médio ponderado 24 h (ex.: 10×R$10 + 100×R$20 = R$ 19,09), menor/maior preço só de vendas concluídas, produção e consumo **reais** (eventos de estoque/inventário; comprar/vender ≠ consumir), oferta via provedor (sem provedor = "Sem dados"), tendência 7 dias × 7 anteriores ponderada, gráficos de 30 dias, visão geral (altas, quedas, volume). "Sem dados" nunca vira 0 nem `base_price` (17.9/17.20). Cada indicador devolve valor + detalhamento (`20`).
- `costs.company_cost_report`: últimos 7 dias fechados × 7 anteriores por categoria (insumos `input:<produto>`, salários, impostos), variação %, diferença em R$ e **principal contribuição observada** (maior diferença na direção do total; texto sem causalidade exata). Salário = líquido pago; IR aparece em "impostos" (ambos saem da conta da empresa); lançamentos estornados não contam.
- `audit_market` (+ `manage.py audit_market [--json]`): invariantes 1 (venda × lançamento `SALE`, aritmética, dia, partes), 2 (agregado = histórico bruto recalculado, marcas, dia fechado antes de terminar), 3 (sem negativos). Acusa `SALE_PAYMENT_REVERSED`.
- Índices `(operation, at)` em `companies.StockMovement` e `inventory.InventoryMovement` (consultas por janela de tempo); número de consultas de `product_stats` independente do tamanho do histórico (testado).

**Observações técnicas.** `ensure_closed` tem caminho rápido de 1 consulta quando os dias fechados são contíguos. Um evento bruto que chegue com `at` num dia já fechado seria visto pela auditoria como divergência de agregado (o relógio do jogo não retrocede, então não é esperado). Testes de concorrência provados por mutação (remover o tratamento de `IntegrityError` em `record_sale` e `close_day` faz 4 de 5 falharem em PostgreSQL).

## 2026-10-21 — P1.04e — Varejo e Construtora (`design/02` §4, §11, §12; `10` §6)

Quinta fatia de P1.04. Branch `dev/p1.04e-varejo-construtora`, empilhada sobre o PR #18 (P1.04d); PR próprio; **não mergeado**. Nenhuma parte do Bot Test foi removida ou adiada; o que depende de outro sistema (lote/propriedade do imóvel, mercado e preço de venda) tem ponto de integração explícito, nunca valor ou mecânica inventada.

### O que foi entregue
- **Permissões de compra** (`companies/trade.py`, `02` §4): derivadas do catálogo, sem lista paralela. Produtora (Matriz/Industrial) só compra insumo de receita que **ela** pode produzir (tipo, estrela, receita pronta); Varejo só compra o que revende (canal `retail_sale`); demais tipos ainda sem operação que consuma produtos → `NO_VALID_USE`; o produto precisa do canal `inter_company`. `credit_stock(PURCHASE)` passa a aplicar a regra (o mercado, P1.05, pergunta `purchase_refusal(comprador, produto)` antes de fechar a venda).
- **Varejo** (`companies/retail.py`, `02` §11): cada Trabalhar do Vendedor soma **capacidade de venda do dia** (mesmo registro `SupportWork`, `kind=salesperson`); capacidade do dia = `floor(soma das contribuições)`, não passa para o dia seguinte. `fulfill_sale` (serviço que o mercado chamará) consome **1 de estoque e 1 de capacidade por venda** (`SALES_CAPACITY_EXCEEDED`, `INSUFFICIENT_STOCK`, idempotente por chave, só o Varejo, só produto `retail_sale`); `SalesCapacityUse` imutável ligado ao movimento de estoque `sale`. Não move dinheiro.
- **Construtora** (`companies/construction.py`, `02` §12; `10` §6): `start_construction` (ação do Action Registry, só o Dono) inicia **uma obra ativa por vez** (índice único parcial), projeto = os 4 tipos residenciais de `10` §6 com a Construtora mínima do design (1★/2★/3★/4★). Cada Trabalhar de funcionário da Construtora faz a obra andar de 0% a 100% (skill, especialização no projeto, bônus do Engenheiro; `ConstructionWork` imutável ligado ao salário pago); sem obra ativa o Trabalho é bloqueado antes de gastar Energia (`COMPANY_NO_PROJECT`); com 100% a obra é concluída e a Construtora pode iniciar outra. `register_completion_hook` é o ponto onde Imóveis (P1.07) criará o imóvel.
- `audit_companies`: invariantes 12 (vendas × movimentos de estoque × capacidade) e 13 (obras: progresso = soma dos trabalhos, salário pago, uma ativa, sequências, estrela do projeto). Migração `0005_retail_construction`.
- **Correção de um bug da P1.04c**: o bloqueio "empresa sem produto" valia para funcionários de qualquer tipo de empresa; agora só Matriz/Industrial produzem (Serviços/Financeira seguem trabalhando; Construtora usa a obra). Teste novo cobre.

### Interpretações técnicas `[PROV]` (sem alterar mecânica; para confirmação do GD) — em `companies/params.py` e `provisional_table()`
- Capacidade de venda por Trabalhar = 10 × skill (Carisma) × especialização (`retail:sales`); estoque (500×★) fica maior que a capacidade potencial de um vendedor/dia (§11.2).
- Trabalhos para concluir (a 100%, eficiência base): baixa simples 50, alta simples 400, baixa luxo 100, alta luxo 600. As estrelas mínimas vêm de `10` §6; os números de trabalho são `[PROV]`.
- O excedente além de 100% no último Trabalhar se perde. A quantidade de funcionários da Construtora não entra como fator próprio (cada funcionário já soma trabalhos).
- A skill do vendedor/funcionário é a do momento do hook (antes do ganho da própria ação), como em P1.04c/d.

### Lacunas/dependências encontradas (registradas, não decididas)
- **Lote e contrato da obra**: `10` §5 diz que a obra é contratada pelo dono do lote e `10` §28 que a Construtora é prestadora; `02` §12 diz que o Dono "escolhe e inicia". A obra aqui não tem lote nem cliente; o vínculo (e o pagamento, `PUBLIC_WORKS_PAYMENT` ou contrato privado) é de P1.07/P1.09/`18`.
- **Cancelar/abandonar obra**: não definido no design; hoje a obra só termina concluindo.
- **Materiais de obra** e consumo operacional (`02` §10): limitação conhecida (Q10).
- **Venda entre empresas**: a checagem do comprador existe (`purchase_refusal`); o preço, a oferta e a entrega são do mercado (P1.05). Compra de insumos de Serviços/Construtora/Financeira: sem uso definido.
- Imóvel concluído, propriedade e QoL do imóvel: P1.07.

### Verificação (executada no estado final da branch)
- PostgreSQL 16, suíte completa: **1203 testes OK** (1175 + 28 novos: permissões de compra, Varejo, Construtora, auditoria, concorrência).
- SQLite, suíte completa: **1203 testes OK (13 pulados que exigem PostgreSQL)**.
- `manage.py check` e `makemigrations --check` limpos nos dois bancos; `companies` 3× no PostgreSQL (164 testes cada, com a concorrência de vendas e obras).
- Mutação das travas (empresa e item de estoque; empresa e obra) faz os dois testes de concorrência novos falharem.

### Locking (PostgreSQL)
Protocolo inalterado: jogador → empresa → (estoque/obra sob a trava da empresa) → registro monetário. Mutações verificadas: sem a trava da empresa e do item de estoque, as vendas simultâneas passam da capacidade (18 > 10); sem a trava da empresa/obra, os construtores simultâneos somam progresso errado. Os testes de concorrência falham nesses casos, logo não são vacuosos.

## 2026-10-20 — P1.04d — Cargos de suporte: Engenheiro e Advogado (`design/02` §9, §13, §22)

Quarta fatia de P1.04. Branch `dev/p1.04d-suporte`, empilhada sobre o PR #17 (P1.04c); PR próprio; **não mergeado**. Nenhuma parte do Bot Test foi removida ou adiada.

### O que foi entregue
- **Engenheiro** (`companies/support.py`): cada Trabalhar soma `base × fator de skill × fator de especialização` ao **bônus do dia** da empresa; a produção por trabalho dos funcionários de produção passa a ser multiplicada por `1 + bônus do dia` (passo `engineering_bonus` no detalhamento de `output_per_work`). O bônus reinicia sozinho a cada dia (soma por empresa/cargo/dia de competência de `SupportWork`; sem tarefa de limpeza). Sem teto artificial: o limite é estrutural (estrela × nº de Engenheiros × Energia), como o §9.1 manda.
- **Advogado**: cada Trabalhar soma à **redução do dia**; o multiplicador de risco de Burnout dos funcionários da empresa passa a ser `1 − redução` (piso de 1% aplicado por `players.rules`) sobre os ganhos de **Trabalhar e Estudar**; Lazer não é afetado (§9.2). Integra-se por um novo ponto genérico de `players`: `register_burnout_risk_provider` / `resolve_burnout_risk` (mesmo desenho do provedor de atividade: só vale quando quem chamou não informa `burnout_risk`; jogadores reais e Bots pelo mesmo caminho; a pré-visualização da ação mostra o mesmo valor que será pago).
- **Limite de vagas por estrela**: Engenheiros e Advogados abertos ou ocupados ≤ estrela (`SUPPORT_LIMIT_REACHED` em `open_position`, também no Action Registry).
- **Especialização** (§13): Engenheiro no produto da empresa; Advogado na própria atividade (`support:lawyer`).
- `SupportWork` imutável (ligado ao salário pago pela mesma ação) e `audit_companies` invariante 11 (toda contribuição tem o salário pago; dia correto; valor = detalhamento; vagas de suporte dentro do limite).
- Migração `0004_support_work`. O salário de Engenheiro/Advogado é o mesmo da P1.04b (por ação de Trabalhar, `WAGE`); o Trabalho deles não é bloqueado por produto/setup/estoque (só quem produz é).

### Interpretações técnicas `[PROV]` (sem alterar mecânica; para confirmação do GD) — em `companies/params.py` e `provisional_table()`
- Contribuição por Trabalhar: Engenheiro 0,02 e Advogado 0,02 × fator de skill (`1 + nível × 0,02`, mesma curva da produção) × fator de especialização (`1 + pontos × 0,01`). Calibração do alvo do §9.1 (~2,5×): 5★, 5 Engenheiros, 5 trabalhos cada (barra de Energia = 100/20), nível máximo e sem especialização → `25 × 0,02 × 3 = 1,5` → 2,5× (verificado por teste; é alvo de balanceamento, não teto). O §9.2 não dá alvo para o Advogado: mesma forma e mesma base.
- Vagas de suporte por estrela = estrela (`02a` §2.3).
- Beneficiários do Advogado: ocupantes de cargos da empresa **exceto o Dono** (o Dono não é um emprego contratado, §16), inclusive o próprio Advogado e o Engenheiro.
- O efeito vale para as ações **depois** da contribuição no mesmo dia (a própria ação do Advogado usa o acumulado até então).
- A skill/especialização usadas são as do momento do hook (antes do ganho da própria ação, os hooks das Empresas rodam antes dos de Skills), como na produção.

### Lacunas/dependências encontradas
- Fórmula exata do efeito dos cargos de suporte e alvo do Advogado: o §9 diz "outros parâmetros definidos pelo sistema" (valores acima `[PROV]`, calibráveis pelos Bots).
- Limite de funcionários por estrela continua sem definição (`02a` lacuna 7).

### Verificação (executada no estado final da branch)
- PostgreSQL 16, suíte completa: **1175 testes OK** (1148 + 27 novos: suporte, provedor de risco, concorrência).
- SQLite, suíte completa: **1175 testes OK (13 pulados que exigem PostgreSQL)**.
- `manage.py check` e `makemigrations --check` limpos nos dois bancos; `companies` 3× no PostgreSQL (136 testes cada, com a concorrência de suporte).
- Mutação: sem as travas do Dono/empresa em `open_position`, o teste de vagas simultâneas falha (2 ou 4 vagas abertas em 1★).

### Locking (PostgreSQL)
Protocolo inalterado: jogador → empresa → registro monetário. O hook de suporte trava a empresa antes de gravar. A corrida por vagas de suporte é serializada pelo jogador Dono (e pela empresa); o teste de concorrência falha se as duas travas forem removidas (as quatro aberturas simultâneas passam), logo não é vacuoso.

## 2026-10-20 — P1.04c — Produção e estoque empresarial (`design/02` §5-8, §11.1, §13, §18-20; `22`)

Terceira fatia de P1.04. Branch `dev/p1.04c-producao-estoque`, empilhada sobre o PR #16 (P1.04b); PR próprio; **não mergeado**. Nenhuma parte do Bot Test foi removida ou adiada; o que depende de outro sistema (terreno da Matriz, materiais operacionais, estrelas por upgrade) tem ponto de integração explícito e recusa clara, nunca valor inventado.

### O que foi entregue
- **Estoque empresarial** (`companies/stock.py`): posse de Produtos do catálogo por empresa (distinta do inventário do jogador), quantidades inteiras, qualidade média por unidade (desconhecida = `NULL`, nunca 0), trilha imutável `StockMovement` (chave idempotente, origem, destino, operação, `Explained`), capacidade por estrela (`STOCK_FULL`). Entrada externa só `PURCHASE` (`credit_stock`) e saída externa só `SALE` (`debit_stock`): produção e consumo de insumo só existem dentro do Trabalho. A camada **não move dinheiro**; quem compra/vende (P1.05/P1.08/P1.04e) liga o pagamento ao movimento na mesma transação.
- **Escolha de produto** (`set_production`, ação do Action Registry, só o Dono): um produto por vez; recusas explicadas (`NOT_OWNER`, `COMPANY_TYPE_CANNOT_PRODUCE`, `PRODUCT_NOT_FOR_COMPANY_TYPE`, `STARS_TOO_LOW` com o que falta, `PRODUCTION_NOT_READY` via `check_production_ready`, `ALREADY_PRODUCING`, `COOLDOWN_ACTIVE`, `MATRIX_SITE_UNDEFINED`, `PRODUCT_OUTSIDE_TERRAIN_CATEGORY`). Troca = **setup** (empresa fora de operação, 6 h `[PROV]`) + **cooldown** (7 dias `[PROV]`); a primeira escolha é livre e sem espera `[PROV]`. Histórico imutável `ProductionChange`.
- **O Trabalho do funcionário de produção produz** (hook de `perform_action`, mesma transação, mesmo caminho de jogadores e bots): unidades = base × fator da skill relevante × fator da especialização × rendimento do catálogo; a fração fica em `carry` (nada se perde). Insumos saem do estoque da empresa pela receita; faltou insumo ou espaço, produz o que cabe (como o limite de salário `01` §1.7); sem nada possível, o Trabalho é **bloqueado antes** (provedor de bloqueio, sem gastar Energia, sem pagar salário). A especialização do funcionário cresce no produto trabalhado (`ActivityContext.specialization_key`, `skills.specialization_value`).
- **Qualidade** (§8): cada unidade entra com a skill relevante de quem trabalhou; o estoque guarda a média por unidade; o teto da estrela se aplica na leitura (`MIN`).
- `audit_companies` ganhou as invariantes 8 (estoque = soma dos movimentos, qualidade, capacidade), 9 (toda produção ligada a um salário de trabalho pago de um funcionário daquela empresa e insumos consumidos conferem) e 10 (histórico da linha, cooldown, `carry`).
- Provedor de terreno para a Matriz (`register_site_provider`): ponto de integração com P1.07; sem provedor, produto de Matriz é recusado.

### Interpretações técnicas `[PROV]` (sem alterar mecânica; para confirmação do GD) — todas em `companies/params.py` e em `provisional_table()`
- Base de 1 unidade por Trabalho; fator de skill `1 + nível × 0,02` (curva `linear_prov`, usada quando o balanceamento de Skills não define outra); fator de especialização `1 + pontos × 0,01`.
- Capacidade de estoque 500 × estrela; teto de qualidade 100 × estrela (documentados em `design/02a` §2.3).
- Setup 6 h e cooldown 7 dias (`02` §5.3 dá só a ordem de grandeza).
- Produzem: Matriz (matéria-prima) e Industrial (produtos de fabricação). Varejo/Serviços/Construtora/Financeira não escolhem produto aqui (Varejo vende em P1.04e; Construtora tem obra).
- Só o funcionário de produção (`WORKER`) produz; Dono/Engenheiro/Advogado/Vendedor trabalham sem produzir e sem ser bloqueados.

### Lacunas/dependências encontradas
- **Custo fixo da troca de produto** (`02` §5.3): o `24` não tem natureza nem destino; valor `[PROV]` = 0 e qualquer valor > 0 é recusado (`PRODUCTION_CHANGE_COST_UNDEFINED`) até o GD definir.
- **Categoria da empresa Industrial** e **terreno da Matriz**: dependem de P1.07 (hoje a Industrial aceita qualquer produto de fabricação com estrela suficiente; a Matriz exige o provedor).
- **Materiais operacionais** (`02` §10): limitação conhecida (Q10), a retomar na integração.
- **Unidade do salário, curva de skill, capacidade/teto por estrela**: valores `[PROV]` acima.

### Verificação (executada no estado final da branch)
- PostgreSQL 16, suíte completa: **1148 testes OK** (1116 + 32 novos: produção/estoque, auditoria, registro, concorrência).
- SQLite, suíte completa: **1148 testes OK (13 pulados que exigem PostgreSQL)**.
- `manage.py check` e `makemigrations --check` limpos nos dois bancos; `companies` 3× no PostgreSQL (114 testes cada, com a concorrência de produção/estoque).
- Uma falha apareceu na primeira rodada completa (`skills`: a curva `[PROV]` registrada no registro de curvas quebrava o teste "só a curva neutra é embutida"); corrigida mantendo a curva `[PROV]` dentro das Empresas, sem registrá-la em Skills.

### Locking (PostgreSQL)
Protocolo: jogador → empresa (serializa linha de produção, estoque e movimentos) → registro monetário. Bug real encontrado só em PostgreSQL pelo teste de concorrência: `select_for_update` sobre `select_related` de FK nula (`FOR UPDATE cannot be applied to the nullable side of an outer join`) → `of=("self",)`. Mutação (tirar a trava da empresa em produção e estoque) faz o teste de concorrência falhar (soma errada do estoque e deadlock), logo ele não é vacuoso.

## 2026-10-20 — P1.04b — Cargos, mural e salários (`design/02` §15-16; `24` §24.12-24.13)

Segunda fatia de P1.04. Branch `dev/p1.04b-cargos-mural`, empilhada sobre o PR #15 (P1.04a); PR próprio; **não mergeado**. Nenhuma parte do Bot Test foi removida ou adiada.

### Decisões do Game Director registradas (mensagem de 2026-10-19)
Gravadas em `design/02-empresas.md` §25 e em `design/24` §24.12.5 (política por tipo):
1. **Estrelas**: toda empresa nasce com 1★ `[PROV]`; progressão por melhorias compradas com o caixa da empresa, custo crescente por estrela. **Antes de implementar a progressão**, a proposta (custos, limites, desbloqueios, lacunas) está em `design/02a-estrelas-PROPOSTA.md` (DRAFT). A progressão virou a fatia **P1.04f** e só é implementada após as lacunas 1–4 do documento.
2. **Caixa insuficiente**: salário de trabalho e salário do Dono usam **`PENDING`** (obrigação registrada e auditável, sem criar dinheiro, sem pagamento duplicado).
3. **Aprovação de candidatos**: **somente o Dono**; sem delegação nesta fase.
4. Confirmadas: aporte = `DONATION`/`company_capital`; localização e ocupação da empresa entram com P1.07 (continuam no escopo do Bot Test).

### O que foi entregue
- **Cargos e mural** (`companies/jobs.py`): vagas (`WORKER`, `ENGINEER`, `LAWYER`, `SALESPERSON`) abertas/fechadas só pelo Dono, com salário e requisitos de skill (`01` §1.9, reaproveita `SkillRequirement`); mural público paginado com `requirements_met` e o detalhamento do que falta por observador (None quando não há observador); candidatura, retirada, aprovação e rejeição (só o Dono), pedido de demissão e demissão. Um emprego contratado por jogador (restrição de banco; o Dono não conta). Trilha imutável de eventos (`PositionEvent`).
- **Salário do funcionário**: devido a **cada ação de Trabalhar** (hook de `perform_action`, mesma transação, mesmo caminho de jogadores e bots), natureza `WAGE`, pagador = conta da empresa, política `PENDING`, IR retido. `WorkWage` liga a ação ao pedido do registro monetário.
- **Salário do Dono**: devido **por dia**, folha em **um lote** no tick diário do mundo (`OWNER_SALARY`, `PENDING`). Idempotente por (empresa, dia); catch-up de vários dias paga cada dia uma vez; empresa fundada depois do tick não recebe aquele dia.
- **Quitação de pendências**: no tick diário a empresa quita antes da folha do dia, da competência mais antiga para a mais nova (R4). Obrigações nunca são recriadas nem pagas duas vezes.
- **Provedor de atividade** (`players.hooks.register_activity_provider`): o cargo informa o `ActivityContext` do Trabalho (a skill relevante cresce); só vale quando o chamador não informou `activity`. Sem emprego, Trabalhar continua livre e sem salário (P0.04).
- **Limites W/S/T**: `payroll.limits_for` (registrado sob demanda sem sobrepor outro provedor): W = R$ 50/dia e T = sem teto (padrões de `11` §11.1), S = nível da skill relevante do cargo × 1,5 (`skills`).
- 8 ações no Action Registry (`open_position`, `close_position`, `apply_position`, `withdraw_application`, `approve_application`, `reject_application`, `dismiss_employee`, `resign`), com as mesmas funções de recusa na disponibilidade e na execução.
- `audit_companies` ganhou as invariantes 4–7 (cargos/vagas, candidaturas, salário de trabalho, folha do Dono sem dia pulado nem duplicado).

### Interpretações técnicas (sem alterar mecânica; para confirmação do GD)
- **Unidade do salário**: do funcionário = valor **por ação de Trabalhar** (o `01` §1.7 fala em limite diário "e não por clique", o que pressupõe pagamento por clique); do Dono = valor **por dia** (`24` §24.13: folha diária). O `02` não fixa a unidade.
- **Skill relevante por cargo** `[PROV]` (`01` §1.8 delega a Empresas): Físico = funcionário de produção; Inteligência = Dono, Engenheiro, Advogado; Carisma = Vendedor. Tabela auditável em `companies/params.py`.
- **Cargos por tipo** `[PROV]`: Varejo contrata vendedores; os demais tipos, funcionários de produção; todos podem ter Engenheiro e Advogado.
- **IR sobre salário** = 5% (padrão da lei em `11` §11.1) até o sistema de leis (P1.12) existir; território tributário vazio → União.
- Ao sair (demissão ou pedido), a vaga é **encerrada** (o Dono abre outra); salários já devidos permanecem como obrigação.
- Candidatura: quem já tem emprego pode se candidatar; a regra de um emprego é aplicada na aprovação; na contratação, as outras candidaturas pendentes do contratado e as da vaga são canceladas (`CANCELLED`, com motivo).
- Um Trabalho com caixa disponível é pago na hora, sem fila; a ordem "mais antiga primeiro" vale na quitação.
- O Dono pode se candidatar a vaga da própria empresa (o design não proíbe; nada de dinheiro novo, o limite diário `S` vale para os dois salários).
- Sem limite de vagas por empresa nem de funcionários: o `02` §14 só diz que estrelas "podem influenciar" (depende da proposta de estrelas).

### Lacunas/dependências encontradas
- **Lei antitruste** (`11` §11.1: "máximo de empresas do mesmo tipo por proprietário", padrão 1): é lei paramétrica de P1.12 e ainda não limita a fundação (P1.04a); P1.12 precisa de um ponto de recusa em `found_company`.
- **Estrelas** (`02a`): lacunas 1–8 do documento.
- Bloqueios por empresa parada/setup e produção chegam em P1.04c; Engenheiro/Advogado têm cargo mas sem efeito até P1.04d; vendedor até P1.04e.

### Verificação (executada no estado final da branch)
- PostgreSQL 16, suíte completa: **1116 testes OK** (1059 + 57 novos: cargos/mural, salários e folha, registro, auditoria, concorrência).
- SQLite, suíte completa: **1116 testes OK (13 pulados que exigem PostgreSQL)**.
- `manage.py check` e `makemigrations --check` limpos nos dois bancos; `companies` 3× no PostgreSQL (82 testes cada, com a concorrência de cargos/salários).

### Locking (PostgreSQL)
Protocolo: jogadores em id crescente → empresa → vaga → candidatura → registro monetário. A limpeza de candidaturas de outras empresas só atualiza linhas, e `PositionEvent` usa ids simples (sem FK de jogador) para não tomar `FOR KEY SHARE` fora do protocolo (ciclo possível). A folha do tick trava contadores (jogador, dia) e depois contas em id crescente, a mesma ordem de quem paga um Trabalho. Mutação provou o teste de corrida (remover os travamentos de empresa/vaga faz `applications racing a close` falhar).

## 2026-10-19 — P1.04a — Empresas: núcleo (`design/02` §16-17)

Primeira fatia de P1.04 (Empresas é grande demais para um PR revisável; a divisão abaixo é de ordem de execução, **nenhuma parte sai do Bot Test**). Branch `dev/p1.04a-empresas-nucleo`, empilhada sobre o PR #14 (P1.02a); PR próprio; **não mergeado**.

### O que foi entregue
- App `companies`: `Company` (tipo, fundador, estrela, custo cobrado, chave do lançamento), `Position` (cargo; só o **Dono** nesta fatia) e `CapitalContribution` (aporte, imutável).
- **Fundação** (`found_company`, ação do Action Registry): custo por tipo do `02` §17 (Varejo 15.000; Serviços 25.000; Matriz 40.000; Construtora 60.000; Industrial 80.000; Financeira 100.000 reais), cobrado do fundador para o caixa federal (`COMPANY_FOUNDING`, `24` Q2); cria a empresa, a conta `COMPANY` (sem caixa) e o **cargo Dono** ocupado pelo fundador com o salário que ele definiu (`02` §16). Dinheiro movido, nunca criado; recusas sem efeito.
- **Aporte de capital** (`fund_company`): o Dono move dinheiro existente para a conta da empresa (resolve a questão do `24` "capital inicial da empresa = transferência do dono"). Não existe retirada nem distribuição (Q9).
- `audit_companies` (cargo Dono único e ocupado, conta da empresa, lançamentos de fundação e de aporte) e `manage.py audit_companies [--json]`.
- Protocolo de bloqueio documentado: jogador → empresa → contas do ledger.

### Interpretações técnicas (preservam o design; para confirmação, não bloqueiam)
- **Natureza do aporte**: a lista de naturezas do `24` é fechada e não tem "aporte"; usei `DONATION` com categoria `company_capital` (não é remuneração nem venda, não gera imposto). Se o GD preferir uma natureza própria, é mudança do `24`.
- **Estrela inicial** = 1 `[PROV]` (`companies/params.py`, tabela auditável).
- Nome da empresa: 1–80 caracteres; unicidade não exigida (o design não pede). Sem limite de empresas por jogador (o design não limita).

### Verificação (executada no estado final da branch)
- PostgreSQL 16, suíte completa: **1059 testes OK** (1034 + 25 novos de `companies`).
- SQLite, suíte completa: **1059 testes OK (13 pulados que exigem PostgreSQL)**.
- `manage.py check` e `makemigrations --check` limpos nos dois bancos; `companies` + registro 3× no PostgreSQL (82 testes cada, incluindo concorrência: fundações simultâneas do mesmo fundador, aportes + fundações, fundadores cruzados sem deadlock).

### Lacunas reais de design encontradas (não inventei; ficam visíveis)
1. **Como uma empresa ganha estrelas** (e quantas ela tem ao nascer em definitivo): não está em nenhum documento (`02` §14 só diz que estrelas definem limites; `14` ranqueia por estrelas, `10` §16 as usa para imóvel comercial). Bloqueia Engenheiros/Advogados por estrela, estoque por estrela, teto de qualidade e a estrela mínima das receitas na produção.
2. **Política de caixa insuficiente no salário** (`PENDING` ou `REFUSE`, `24` §24.x): o ledger suporta os dois; falta escolher para empresas.
3. **"Pessoa autorizada" a aprovar candidatos** (`02` §15): o design não define como o Dono autoriza alguém.
4. **Localização**: `02` define que a empresa tem localização, mas `10` §29 diz que "onde a empresa pode operar" e "qual imóvel ela ocupa" pertencem a Imóveis (P1.07; `08` §5: transições de ocupação são do `10`). Esta fatia não inventa lote/ocupação; a ligação entra com P1.07.

## 2026-10-19 — P1.02a — Auto-consumo de alimentos (`design/04` §16)

Implementa o §16 integralmente, sem alterar a mecânica. Branch `dev/p1.02a-auto-consumo`, **empilhada sobre o PR #12** (P1.02); PR próprio; **não mergeado**. Auto-consumo é obrigatório no primeiro Bot Test e a regra já estava definida; a separação em PR é de tarefa, não de escopo.

### O que foi entregue
- **Configuração** (`inventory.AutoConsumption`, ação `auto_consumption` no Action Registry, alvo `{"enabled": bool, "preferred": produto | None}`): habilitar/desabilitar e escolher (ou limpar) o alimento preferido; o preferido precisa ser alimento consumível do catálogo (mesmas recusas do consumo manual). Sem custo de Energia/dinheiro (o design não define).
- **Execução** (`inventory/auto.py`): hook de acesso (`players.hooks`, On Access) no fim do catch-up. Com Nutrição ≥ 10 não consulta nada; com `Nutrição < 10` e Auto-consumo habilitado: 1) preferido, se houver no inventário; 2) senão o alimento disponível de menor ganho de Nutrição; repete enquanto Nutrição < 10 e houver elegível; para ao atingir/ultrapassar 10; sem elegível, nada. Sem polling por jogador.
- **Mesmas regras do manual**: `services.consume_locked` é o núcleo único (item → efeito → quantidade reduzida) usado por `consume` e pelo hook; o efeito de Nutrição/Comida é `players.services.apply_food_locked` (extraído de `consume_food`, que o reutiliza). Sem bônus especial; o efeito de Comida substitui o anterior.
- **Sem recursão**: o hook não chama `consume`/`sync_player`; opera sobre o jogador que o catch-up já travou (em memória) e tem guarda de reentrada. `consume` manual passou a usar `locked_player` (um único catch-up por consumo).
- **Trilha e auditoria**: movimento de consumo com `reference_kind="auto_consumption"` e `explained` (`automatic`, `nutrition_before`, regra de escolha, preferido, candidatos com ganho). `audit_inventory` ganhou o invariante 4 (consumo automático só abaixo do limiar, de alimento, como consumo).

### Interpretações técnicas (preservam o design; registradas por honestidade técnica)
- "Elegível" = alimento do catálogo com valores especificados (NULL é recusado pelo consumo manual, `NULL ≠ 0`) **e ganho de Nutrição > 0**, com ≥ 1 unidade no inventário. Um alimento de ganho 0 (hoje Sorvete e Refrigerante `[PROV]`) não resolve a fome e, se contasse como "menor ganho", seria consumido até acabar sem nunca encerrar o laço. Eles continuam consumíveis manualmente.
- Empate no menor ganho: desempate determinístico pela chave do produto (ordem alfabética). O design não o define; não afeta o gameplay de forma material.
- Limiar 10 é do design (`inventory.constants.AUTO_CONSUME_BELOW`), não `[PROV]`.
- O momento é o do processamento lazy (fim do catch-up, estado em `now`), não retroativo ciclo a ciclo: coerente com "durante o processamento lazy do estado do jogador" e com o guia de continuidade.

### Verificação (executada no estado final da branch)
- PostgreSQL 16, suíte completa: **1034 testes OK** (998 + 36 novos: 33 de Auto-consumo + 3 de concorrência).
- SQLite, suíte completa: **1034 testes OK (13 pulados que exigem PostgreSQL)**.
- `manage.py check` e `makemigrations --check` limpos nos dois bancos; arquivo de concorrência do `inventory` 3× no PostgreSQL (8 testes cada).
- Mutação: trocar o núcleo pelo `consume` público no hook faz 8 testes (não-recursão e repetição) falharem; código restaurado.
- Coberto: configuração e recusas; preferido; alternativa de menor ganho; desempate; preferido inelegível (NULL); ganho 0 e não-alimento; repetição, parada em 10 e após ultrapassar; fim do alimento; ausência de elegível; mesmas regras do manual (Nutrição, efeito, trilha); substituição do efeito de Comida; Nutrição ≤ 100 e dinheiro intacto; trilha/auditoria (inclusive movimento forjado); fome acumulada com o tempo tratada no próximo acesso e não antes; todos os caminhos lazy (`sync_player`, `locked_player`, `get_snapshot`, `check_action`, `available_actions`, `execute_action`); não-recursão (um `_catch_up` por acesso); concorrência no PostgreSQL (acessos simultâneos consomem uma vez; acesso × envio da última unidade tem um vencedor; envios cruzados + acessos sem deadlock).

---

## 2026-10-18 — P1.02 — Inventário implementado (app `inventory`)

Implementa `design/05` (REVIEW) sobre a base integrada (#8 → #9 → #10 → #11 já mergeados em `main`). Branch `dev/p1.02-inventario`, PR #12. **Não mergeado; aguarda autorização do Game Director.**

### O que foi entregue
- **Posse** (`inventory/models.py`): `InventoryItem` (jogador → produto → quantidade inteira, só existe com quantidade > 0); categorias vêm do catálogo (`inventory_of` agrupa por `Product.category`; nada é duplicado).
- **Trilha imutável** `InventoryMovement` (05 §19): origem, destino, produto, delta, quantidade resultante, tipo, instante, referência e `Explained`; idempotente por `key`. `InventoryItem.quantity` é cache; a verdade auditável é a soma dos movimentos.
- **Entrada/saída externas** (`credit`/`debit`): restritas a `purchase`/`production` e `sale`. Compra, Varejo e produção ainda não existem; o ponto de entrada está pronto, sem inventar quem o chama.
- **Consumir** (05 §5-6; `04` §15): ação `consume` no Action Registry (alvo PRODUTO). Alimento → Nutrição (limitada ao espaço disponível, `Explained` com `food_nutrition` e `nutrition_room`) + efeito temporário de QoL na categoria FOOD (substitui o anterior, regra de `04`). Valores NULL do catálogo recusam com `UNSPECIFIED_DESIGN_VALUE`.
- **Correio** (05 §11-12): ação `send_item` (alvo PARAMS `{recipient, product, quantity}`). Taxa = `MAX(mínima, valor_de_referência × percentual)`, valor de referência = `base_price × quantidade`, cobrada do remetente para a União (`Nature.MAIL_FEE`) pelo `ledger.transfer`; sem envio gratuito; o `Shipment` guarda o detalhamento da taxa.
- **Auditoria** (`audit_inventory`, `manage.py audit_inventory [--json]`): posse = Σ movimentos e `quantity_after`; operação x sinal; envios x movimentos x lançamento `MAIL_FEE`.
- **Registry**: novos tipos de alvo `PRODUCT` e `PARAMS` em `players/registry.py`; as duas ações usam as mesmas recusas dos serviços (sem caminho privilegiado para Bots).

### Valores `[PROV]` (Q3 de 2026-10-14: provisórios permitidos se auditáveis; `inventory/params.py`)
- Percentual da taxa de correio: **10%**; taxa mínima: **R$ 1,00** (100 centavos); duração do efeito temporário de alimento: **3600 s**. Todos calibráveis; origem registrada no código. Arredondamento da taxa: HALF_EVEN, uma única vez.

### Decisões técnicas (não alteram a mecânica; registradas por honestidade técnica)
- Consumir é **uma unidade por ação**. Alimento sem efeito de QoL (NO_EFFECT / intensidade 0) não aplica efeito temporário e **não** substitui o existente. Produto não alimento recusa com `NO_CONSUMPTION_EFFECT`.
- Correio: o design não prevê custo de Energia nem regra de localização; nenhum foi criado. Envio a si mesmo recusado (`SAME_PLAYER`). Quantidades são inteiras.
- **Protocolo de bloqueio** (docstring de `inventory/services.py`): 1) linhas `Player` envolvidas em ordem crescente de pk; 2) `InventoryItem` em ordem crescente de player_id; 3) contas do ledger.

### Bug real encontrado e corrigido (PostgreSQL)
Envios cruzados (A→B e B→A simultâneos) davam deadlock em 3/3 execuções: o INSERT com FK toma `FOR KEY SHARE` na linha `Player` referenciada, que conflita com o `FOR UPDATE` da outra transação. Correção: `send_item` trava as duas linhas `Player` em ordem crescente de pk antes de qualquer outra coisa. Coberto por teste de concorrência (5 execuções consecutivas no PG sem falha).

### Verificação (executada no estado final da branch)
- PostgreSQL 16, suíte completa: **998 testes OK** (941 anteriores + 57 do `inventory`).
- SQLite, suíte completa: **998 testes OK (13 pulados que exigem PostgreSQL)**.
- `manage.py check` e `makemigrations --check` limpos nos dois bancos.
- Envios cruzados A↔B (`test_crossing_sends_between_two_players_never_deadlock_and_conserve_items_and_money`): passa no PostgreSQL (3 execuções do arquivo de concorrência, 5 testes cada). Mutação feita para provar que o teste vale: sem o bloqueio ordenado das duas linhas `Player`, ele falha com `deadlock detected` (2/2 execuções); código restaurado.

### Fora do escopo DESTE PR (continua no Bot Test; cada item tem etapa própria)
- **Auto-consumo** (`04` §16): **obrigatório no primeiro Bot Test; a regra já está definida no `04` §16 e NÃO aguarda decisão de mecânica** (a nota anterior desta entrada que o chamava de "decisão pendente do GD" estava errada e foi removida). É a tarefa **P1.02a**, imediatamente depois deste PR (`TASK_QUEUE.md`). Separação de tarefa, não redução de escopo. Armadilha conhecida: o gatilho vive no processamento lazy (`_catch_up`), e `consume()` público chama `sync_player()` → `_catch_up()`; a P1.02a reutiliza a mesma regra de negócio sobre o jogador já travado, sem reentrar no catch-up.
- **Mercado de Jogadores, Varejo e compra** (05 §13-16): P1.05/P1.04; este PR entrega os pontos de entrada/saída (`credit`/`debit`).
- **Estado ativo** (roupa/veículo/residência, 05 §7-10): depende de Roupas/Imóveis/Veículos; segue planejado nessas etapas.
- Estoque empresarial (05 §17): estrutura distinta, em P1.04.
- As quatro pendências herdadas do P1.01 **já haviam sido resolvidas na P0.02**; nenhuma bloqueou.

### Revisão consolidada do diff (correções incluídas no PR)
- `_apply`: a releitura após `IntegrityError` era recursiva e ilimitada; uma violação real de restrição recursaria sem fim. Agora relê **uma** vez e, se o erro persiste, ele sobe (teste novo).
- `send_item`: a recusa de pagamento rotulava qualquer falha do ledger como `INSUFFICIENT_FUNDS`; agora propaga o código real do ledger.
- `inventory_of`: a ordem das categorias dependia da collation do banco; agora é ordenada em Python.

---

## 2026-10-16 — P0.07b — registro monetário implementado (app `ledger`)

Implementa `design/24` (FINAL — BOT TEST) sem alterar a mecânica. Branch `dev/p0.07b-ledger`, empilhada sobre o PR #10 (que sobre #9 → #8). **Não mergeada; aguarda auditoria externa e aprovação do Game Director.**

### O que foi entregue
- **Contas e lançamentos** (`ledger/models.py`, `services.py`): contas por tipo; lançamentos imutáveis (modelo, queryset e restrições de banco), em centavos inteiros, com natureza fechada, referência obrigatória, saldos antes/depois e `Explained`; transações atômicas e idempotentes por `key` (mesmo conteúdo devolve o original, conteúdo diferente = `IDEMPOTENCY_CONFLICT`); contas travadas em ordem de id; `MAX_AMOUNT = 10^15` `[PROV]`; estorno técnico que espelha e aponta o original (nunca de emissão, remuneração ou sumidouro). Saldo não-negativo (exceto `ISSUANCE`) também é restrição do banco.
- **Saldo bruto / reservado / disponível**; reservas (`hold`/`release_hold`, consumo por `HoldUse` na mesma transação); `quote`/`can_afford` sem mover dinheiro.
- **Retenções genéricas** (`open_retention`/`retain`/`release_retention`, destino escolhido por quem chama) e **interface de roteamento tributário** (`register_tax_resolver`/`route_tax`/`post_taxed_payment`; padrão União; ambiguidade = `TAX_ROUTE_AMBIGUOUS`; compra da União com imposto à União não gera lançamento para ela mesma). Nenhum módulo militar importado (P1.17 conecta).
- **Sumidouro** só recebe; **dotações de cenário** como única fonte de emissão (`SCENARIO_GRANT`, zero explícito vale, ausente recusa com `SCENARIO_GRANT_UNSPECIFIED`, idempotente por conta).
- **Obrigações pendentes** (`ledger/obligations.py`): fora do caixa, quitação por competência e id, parcial permitida, imposto recolhido em parcelas que fecham o total, cancelamento com motivo.
- **Remuneração** (`ledger/remuneration.py`): `submit_remuneration` → `liquidate_remuneration` (lote em ordem estável pela chave intrínseca) e `pay_remuneration_now`; contadores `C_S`/`C_T`/`C_P`; reserva política derivada sem dupla subtração (`P_liberada`); `W > S`, `T` binding, soldo excedente descartado sem obrigação; políticas `PENDING`/`REFUSE`; imposto de renda sobre o bruto; `Explained` completo por pedido; `preview_remuneration` para feedback. Limites (`W`,`S`,`T`) e salário político devido vêm de **provedores** registrados pelos sistemas donos; sem provedor a liquidação recusa.
- **Viagem**: handler de pagamento (`PLAYER → UNION`, `TRAVEL_FEE`) que só cobra com cenário monetário ativo; `check_action` informa `INSUFFICIENT_FUNDS` sem cobrar. Em `travel.services`, `register_payment_handler` ganhou `active=` e `check_funds=` opcionais (comportamento anterior preservado).
- **Jogador**: conta criada com o jogador (hook) e dotação do cenário ativo.
- **Auditoria** (`audit_ledger`, exit code ≠ 0) reconstrói saldos a partir do log e confere os invariantes 1–13 e contadores; **métricas** (`ledger_metrics`).

### Decisões técnicas registradas (não alteram mecânica; ver `24` §24.19.1)
`PENDING` sem caixa vira obrigação do bruto inteiro; `REFUSE` não toca contadores; roteamento tributário ambíguo desfaz o lote; chave da viagem é composta (`travel:<jogador>:<instante>:<origem>:<destino>`) porque o pagamento ocorre antes de a `Journey` existir; `P_liberada` substitui a marcação "dia liquidado" (mesmo efeito, aceita dois pedidos políticos no mesmo dia); operações do registro recebem só inteiros em centavos (`from_reais` converte e recusa o que não for exato).

### Pendências conhecidas (tarefas seguintes)
Provedor de `W`/`S`/`T` a partir de `skills`/`11` (P1.04/P1.12) e provedor do salário político (P1.11); valores de dotação do cenário (P1.18, configuração); política de caixa insuficiente por tipo (P1.04/P1.17/P1.09); ligação do tratamento (P0.04) a um prestador; resolvedor tributário militar (P1.17). Nenhuma delas bloqueia o registro.

### Testes
250 testes no app (`ledger/tests/`; 148 na primeira entrega + 23 da primeira correção + 22 da revisão consolidada + 30 da correção da emissão + 9 da serialização da configuração + 18 da imutabilidade da linha de dotação): transações, propriedade com sequência aleatória (conservação a cada passo), rotas, imutabilidade, estorno, idempotência, atomicidade, reservas, retenções, roteamento, dotações, obrigações, remuneração (inclui 20 permutações de chegada com resultado idêntico), integração com viagem e jogador, auditoria (adulteração direta no banco), concorrência (threads). Suíte completa: 917 testes OK em PostgreSQL 16 (0 pulados) e em SQLite (9 pulados: o teste do banco esperado e os 8 de ordem estrita, só PostgreSQL), após a imutabilidade da linha de dotação; `check` e `makemigrations --check` limpos.

### Documentos alterados
`24` (centavos nos serviços, chave da viagem, `P_liberada`, §24.19.1), `TASK`, `TASK_QUEUE`, `CHANGELOG_DEV`.

### P0.07b — estado `active` do cenário pelo ORM (2026-10-18)

> **Ajuste de precisão (mesma data, commit seguinte):** a permissão virou `_activation_permit` (privada) e o texto abaixo foi corrigido para o limite de confiança real; +4 testes de fronteira (números na seção "Fronteira" ao fim desta entrada).

Revisão do commit `28036d7`: `_ScenarioQuerySet.update()` só entrava no protocolo de bloqueio quando `name` estava nos argumentos; `update(active=...)` passava direto, e `active=True` pelo ORM contornava a validação das dotações exigidas feita por `activate_scenario()`. Correção pontual, sem alterar decisões econômicas.
1. **Ativar só pelo serviço.** `activate_scenario()` valida as dotações exigidas (já com tudo travado) e só então concede `_activation_permit(pk)` (mecanismo **interno e privado**, variável de contexto, só para aquele cenário e só dentro do bloco; usado em um único ponto, dentro de `activate_scenario`). As transições para ativo pelos caminhos comuns do ORM são recusadas com `ScenarioActivationForbiddenError` (`SCENARIO_ACTIVATION_FORBIDDEN`): `QuerySet.update` (valor ou expressão), `save` (também com `update_fields`; instância "nova" com pk explícito, que o Django grava como UPDATE), `bulk_update`, `bulk_create` (cenário nasce inativo), `create`/`get_or_create`/`update_or_create`. Upsert em lote de cenários é recusado. `save(update_fields=[...sem "active"])` não ativa; manter ativo o que já está ativo é no-op permitido; uma instância velha não reativa um cenário que o serviço desativou.
2. **Protocolo.** `update`/`bulk_update`/`save` que tocam `name` ou `active` travam **todos** os cenários em ordem de pk como primeiro passo e só depois leem e decidem (nova `bulk_update` de `LedgerScenario`, antes sem guarda própria). Desativar é livre, mas sob o mesmo protocolo. Sem lock novo fora da ordem.
3. **Contorno do mesmo tipo achado no teste, corrigido junto** (`ScenarioGrantLine.save`): uma instância "nova" com o pk de uma linha já usada, apontando para outro cenário sem histórico, movia a linha (a auditoria acusava `GRANT_LINE_MISSING`), porque a leitura do estado guardado dependia de `_state.adding`. Agora depende só de `pk is not None`. Mesma regra para renome de cenário por `save`.
4. **Testes (+17; `ledger` = 270)**: `test_scenario_activation_guard.py` (14, SQLite e PostgreSQL: caminhos de `update`, `save`, criação, `bulk_*`, permissão restrita ao cenário e ao bloco, serviço ainda recusa cenário incompleto e o ORM não contorna, instância velha, desativação em todos os caminhos, renome/exclusão inalterados, pk explícito em linha de dotação); `test_scenario_concurrency.py`: 1 de propriedade (2 ativações pelo serviço × 2 ativações proibidas pelo ORM × 2 desativações, 4 rodadas: sem deadlock, nunca ativo o incompleto, no máximo um ativo, auditoria limpa; SQLite e PostgreSQL) e 2 determinísticos só PostgreSQL (uma thread pausada segurando os bloqueios, a outra espera e termina depois: desativação pelo ORM × ativação pelo serviço × `update`/`save` proibidos; e a ordem inversa). O teste antigo "banco recusa dois ativos" passou a usar SQL direto (o ORM agora recusa antes). O auxiliar `fund_account` restaura o cenário ativo anterior pelo `activate_scenario`.
5. **Os testes detectam a falha**: com a guarda de ativação neutralizada (e a correção do pk explícito revertida), 12 verificações falham (10 FAIL + 2 ERROR, em PostgreSQL); com o `update` de `active` sem o bloqueio inicial, os 2 estritos de PostgreSQL falham ("deveria estar esperando"/"não chegou a travar").

**Evidências reais**
- PostgreSQL 16.15 (cluster local descartável, `POLIS_EXPECT_DB=postgresql`): suíte completa → `Ran 937 tests ... OK` (0 pulados); `test_scenario_concurrency` + `test_concurrency` + `test_grant_line_immutability` + `test_scenario_activation_guard` repetidos 12 vezes → 12 × `Ran 59 tests ... OK`.
- SQLite: suíte completa → `Ran 937 tests ... OK (skipped=13)` (o teste do banco esperado e 12 só de PostgreSQL); as mesmas quatro suítes repetidas 15 vezes → 15 × `Ran 59 tests ... OK (skipped=13)`; `manage.py test ledger`: 270 testes (13 pulados).
- `manage.py check` sem problemas; `makemigrations --check --noinput` → `No changes detected` (SQLite e PostgreSQL).

**Limitações restantes**: `_activation_permit` **não revalida nada** (a validação das dotações exigidas é do `activate_scenario`, sob os bloqueios globais, antes de concedê-la) e **não é defesa contra código Python que a chame de propósito**: a recusa do ORM evita a ativação acidental pelos caminhos comuns. Difere da `_GrantPermit`, que é revalidada em `_check_grant`. A fronteira é garantida por convenção e por teste (nome privado, nenhum outro módulo a importa, um só ponto de uso dentro de `activate_scenario`, e a permissão só é concedida depois da validação). SQL direto segue fora do alcance da guarda (a restrição única parcial do banco ainda impede dois ativos); a ordem estrita só foi exercitada em PostgreSQL 16 (`READ COMMITTED`, uma instância local, `fsync` desligado), sem CI.

**Fronteira (ajuste de precisão)**: `activation_permit` → `_activation_permit` (privada; nenhum outro módulo a importa; um único ponto de uso, dentro de `activate_scenario`). Nenhuma mudança de comportamento da guarda. +4 testes em `test_scenario_activation_guard.py` (agora 18; `ledger` = 274): a permissão não é exposta pelos módulos públicos; o único uso fora de `models.py` está dentro de `activate_scenario` (verificado por AST); o serviço só a concede depois de validar (recusa por dotação ausente ou cenário inexistente: a permissão nem é concedida; ativação ok: concedida uma vez, para o pk certo, em transação atômica, com as linhas exigidas já explícitas); todos os papéis exigidos continuam validados.
- PostgreSQL 16.15: suíte completa → `Ran 941 tests ... OK` (0 pulados); as quatro suítes afetadas, uma execução → `Ran 63 tests ... OK`.
- SQLite: suíte completa → `Ran 941 tests ... OK (skipped=13)`; `manage.py test ledger`: 274 testes (13 pulados).
- `manage.py check` sem problemas; `makemigrations --check --noinput` → `No changes detected` (SQLite e PostgreSQL).
- As repetições (12× PostgreSQL, 15× SQLite) citadas acima foram da versão anterior; nesta rodada o código só mudou de nome e em comentários, e as suítes afetadas rodaram uma vez em PostgreSQL.

---

### P0.07b — ordem global de bloqueio na guarda de `ScenarioGrantLine` (2026-10-18)

Revisão do commit `9e15929`: a guarda lia os cenários da linha, travava esse conjunto em ordem de pk, **relia** os dados e `_check_line_changes()` podia travar cenários adicionais achados só na releitura (ex.: outra operação moveu a linha para outro cenário enquanto a primeira esperava). Cada chamada a `lock_scenarios()` era ordenada, mas a sequência não: ciclo possível com `activate_scenario()`. Corrigido sem alterar nenhuma decisão de design nem enfraquecer a guarda.
1. **Abordagem escolhida (a mais segura para o escopo)**: toda mutação de configuração (`activate_scenario`, `set_grant_line`, qualquer escrita ORM em `ScenarioGrantLine`, renome/exclusão de `LedgerScenario`) trava **todos** os cenários em ordem crescente de pk, numa única instrução (`lock_all_scenarios()`), **como primeiro bloqueio**; só depois lê dados. Nenhuma verificação trava mais nada. Cenário referenciado que não esteja no conjunto travado (criado/removido entre as leituras) → `ScenarioSetChangedError` (`SCENARIO_SET_CHANGED`, repetir a operação), nunca um bloqueio fora de ordem. Emissão: contas por id e depois **um** cenário (o emissor), nada depois. Sem ciclo possível.
2. **Protocolo documentado** em `ledger/models.py`, `ledger/services.py` e `design/24` §24.11 (pontos 1–3). Regra: não compor emissão e mutação numa mesma transação externa. `set_grant_line` passou a usar o mesmo conjunto travado.
3. **Testes** (+3, `ledger` = 253): propriedade em SQLite e PostgreSQL (dois movimentos, ou movimento e exclusão, da mesma linha sem histórico com uma ativação concorrente: terminam, configuração final consistente, no máximo um cenário ativo, `audit_ledger().ok`); e dois testes determinísticos **só PostgreSQL** (`PostgresLockOrderWithMovingLineTests`): mover × mover e mover × excluir a mesma linha sem histórico, com ativação concorrente, forçando o intercalamento por portões nas chamadas de `lock_scenarios`; verificam ausência de deadlock, configuração final e que, depois da emissão, a linha continua imutável.
4. **O teste detecta a falha**: rodados contra o `models.py`/`services.py` do `9e15929`, em PostgreSQL, os dois testes determinísticos falham com `deadlock detected` real na thread da ativação; contra o código novo passam.

**Evidências reais**
- PostgreSQL 16.15 (cluster local descartável, UTF8, `POLIS_EXPECT_DB=postgresql`): suíte completa → `Ran 920 tests ... OK` (0 pulados); `test_scenario_concurrency` + `test_concurrency` + `test_grant_line_immutability` repetidos 15 vezes → 15 × `Ran 42 tests ... OK`.
- SQLite: suíte completa → `Ran 920 tests ... OK (skipped=11)` (o teste do banco esperado e 10 de ordem estrita, só PostgreSQL); as mesmas três suítes repetidas 15 vezes → 15 × `Ran 42 tests ... OK (skipped=11)`. App `ledger` em SQLite: `Ran 253 tests ... OK (skipped=11)`.
- `manage.py check` sem problemas; `makemigrations --check --noinput` → `No changes detected` (SQLite e PostgreSQL).

**Limitações restantes**: a ordem estrita e o deadlock evitado só foram exercitados em PostgreSQL 16 (`READ COMMITTED`, uma instância local, `fsync` desligado); sem CI em PostgreSQL; em SQLite os 10 testes estritos são pulados. Quem chama as operações de configuração com `SCENARIO_SET_CHANGED` precisa repetir a operação (nenhum chamador de produção existe ainda). SQL direto continua fora do alcance da guarda (contido por `GRANT_HISTORY_INCONSISTENT` e pela auditoria).

---

### P0.07b — imutabilidade efetiva da linha de dotação (2026-10-17)

Única ressalva importante da auditoria independente (Grok, "aprovado com ressalvas" para o Bot Test): a imutabilidade de `ScenarioGrantLine` após a primeira dotação existia só no serviço `set_grant_line`; o ORM (`update`, `delete`, `save`...) e "excluir e recriar" a contornavam. Escopo único; nenhuma decisão de design alterada.
1. **Guarda no modelo** (`ledger/models.py`): com dotação histórica para o par (cenário, papel), a linha não muda de valor, **cenário nem papel** e não é excluída por `save` (inclusive `update_fields`), `QuerySet.update`, `bulk_update`, `bulk_create` (upsert em lote recusado), `update_or_create`, `delete` (instância, `QuerySet`, cascata), `_raw_delete` e `_base_manager` (`Meta.base_manager_name`, migração `0003`). Recusa `GrantLineLockedError` (`GRANT_LINE_LOCKED`). Recriar a linha de um par com histórico com valor diferente do emitido também é recusado (inserção, `set_grant_line` ou mover outra linha para o par); repor o valor histórico é permitido. Para o renome ou a exclusão do cenário (que escapariam da regra pela referência por nome), cenário com dotações não muda de nome nem é excluído.
2. **Protocolo de bloqueio respeitado**: a guarda trava os cenários envolvidos em ordem crescente de pk e consulta o histórico **depois** do bloqueio (`lock_scenarios`, o mesmo do serviço de emissão); uma emissão em andamento termina antes. A verificação roda antes do `delete` do Django (o `pre_delete` fica só como última defesa), porque uma recusa dentro do `atomic(savepoint=False)` do Collector envenenaria uma transação externa.
3. **Segunda defesa em `_check_grant`**: antes de autorizar emissão nova, o valor configurado tem de coincidir com todas as dotações históricas do cenário e papel; senão recusa com **`GRANT_HISTORY_INCONSISTENT`** (detalhe: valor configurado e valores históricos), sem gravar nada. A auditoria continua detectando a divergência histórica (`GRANT_AMOUNT_MISMATCH`). `set_grant_line` passou a recusar também a recriação com valor diferente do histórico.
4. **Comportamento normal preservado**: chamadas que não alteram nada, linhas e cenários sem dotações, outros papéis e outros cenários continuam livres.
5. **Testes** (+18, `ledger` = 250): `test_grant_line_immutability.py` (12): exclusão (instância, queryset, em lote, cascata, `_base_manager`, `_raw_delete`), alteração (queryset, `F()`, instância, `update_fields`, `bulk_update`, `update_or_create`, upsert, serviço), renome do cenário, **exclusão e recriação com valor alterado não emite o valor adulterado**, **linha adulterada por SQL direto: emissão nova recusada, auditoria aponta as antigas, nenhuma transação, lançamento ou saldo novo**, recriação por SQL, idempotência e fluxos normais; concorrência em `test_scenario_concurrency.py`: 2 de propriedade (SQLite e PostgreSQL: `update`/`delete` do ORM × emissão) e 4 de ordem estrita só em PostgreSQL (`update`, `delete`, `save` e exclusão do cenário esperam a emissão em andamento e são recusados).
6. **Os testes detectam a falha**: com a guarda do modelo neutralizada, em PostgreSQL, 15 verificações falham (as de exclusão do cenário continuam recusadas pelo `pre_delete`); com a checagem de `_check_grant` neutralizada, os 2 testes de SQL direto falham.

**Evidências reais**
- PostgreSQL 16.15 (cluster local descartável, UTF8, `POLIS_EXPECT_DB=postgresql`): suíte completa → `Ran 917 tests ... OK` (0 pulados; os 8 testes de ordem estrita rodaram); `test_scenario_concurrency` + `test_concurrency` + `test_grant_line_immutability` repetidos 15 vezes → 15 OK (39 testes cada).
- SQLite: suíte completa → `Ran 917 tests ... OK (skipped=9)` (o teste do banco esperado e os 8 de ordem estrita, que exigem PostgreSQL); as mesmas três suítes repetidas 15 vezes → 15 OK.
- `manage.py check` sem problemas; `makemigrations --check --noinput` → `No changes detected` (SQLite e PostgreSQL).

**Limitações restantes**: SQL direto (fora do ORM) continua possível por definição; ele é contido pela recusa de emissões novas (`GRANT_HISTORY_INCONSISTENT`) e detectado pela auditoria, não impedido (um trigger de banco seria a única barreira real e não faz parte deste escopo). A ordem estrita de bloqueio só foi exercitada em PostgreSQL 16 (`READ COMMITTED`, uma instância local, `fsync` desligado); em SQLite esses 8 testes são pulados. As demais pendências das entradas abaixo continuam (sem CI em PostgreSQL, `ValueError` dos serviços com tipo de conta inválido, provedores P1.x).

---

### P0.07b — serialização da configuração de dotações com a emissão (2026-10-17)

O Game Director aprovou as três interpretações da correção anterior (mapa fechado de cinco papéis, empresas fora; cenário **ativo** para emissão nova, replay idempotente permitido depois da desativação; linha com dotações é imutável). Última questão técnica da revisão: `_check_grant()` travava o cenário, mas `set_grant_line()` não participava do protocolo, e `activate_scenario()` travava só o cenário ativado. Corrigido sem alterar nenhuma decisão de design.
1. **`set_grant_line()`** roda numa transação atômica: trava o cenário (`FOR UPDATE`, o mesmo bloqueio da emissão), **relê** a linha e as dotações já emitidas depois de adquirir o bloqueio e então grava; `GRANT_LINE_LOCKED` mantido. Antes, validar uma dotação e alterar a linha antes do commit podia emitir um valor diferente da linha final.
2. **`activate_scenario()`** trava **todos** os cenários em ordem crescente de pk (`_lock_scenarios`), relê as linhas e só então desativa os outros e ativa o escolhido. Antes, duas ativações simultâneas travavam cada uma o seu cenário e depois tentavam atualizar o outro: deadlock em PostgreSQL. Agora elas se serializam, e uma emissão em andamento (que segura o cenário emissor até confirmar) termina antes da ativação.
3. **Protocolo único e sem ciclo** (documentado no código e no `design/24` §24.11): emissão = contas em ordem de id e depois um cenário; `set_grant_line` = um cenário; `activate_scenario` = todos os cenários em ordem de pk. Ninguém espera por conta segurando cenário.
4. **Defesa em profundidade**: restrição única parcial `ledger_single_active_scenario` (no máximo um cenário com `active = true`), migração `0002_single_active_scenario`.
5. **Testes** (`ledger/tests/test_scenario_concurrency.py`, 9): *propriedades* em SQLite e PostgreSQL (alteração de linha × emissão nunca emite valor que contradiga a linha final; 6 ativações simultâneas × 4 rodadas sem deadlock e com exatamente um ativo; ativação × emissão; o banco recusa dois ativos; alteração falha mantém a configuração) e *ordem estrita* só em PostgreSQL (4 testes: uma thread segura o bloqueio no meio da operação e a outra tem de esperar e terminar depois: alteração de linha × emissão, ativação × emissão, emissão × ativação, ativação × ativação). Verificam valor emitido, configuração final, no máximo um ativo e `audit_ledger().ok`.
6. **Os testes detectam a corrida**: rodados contra o código anterior à correção (em PostgreSQL), 5 dos 9 falham (alteração de linha sem bloqueio; ativações simultâneas com deadlock; emissão que não espera a ativação; restrição de banco); contra o código novo, os 9 passam. Os dois testes de propriedade de emissão × linha/ativação passam nos dois códigos, porque a janela da corrida real é minúscula: quem prova a ordem são os testes de ordem estrita.

**Evidências reais**
- PostgreSQL 16.15 (cluster local descartável, UTF8, `POLIS_EXPECT_DB=postgresql`): suíte completa → `Ran 899 tests ... OK` (0 pulados, os 4 testes de ordem estrita rodaram); `test_scenario_concurrency` + `test_concurrency` repetidos 15 vezes → 15 OK.
- SQLite: suíte completa → `Ran 899 tests ... OK (skipped=5)` (os pulados: o teste do banco esperado e os 4 de ordem estrita, que exigem PostgreSQL); as mesmas duas suítes de concorrência repetidas 15 vezes → 15 OK; `ledger`: 232 testes.
- `manage.py check` sem problemas; `makemigrations --check --noinput` → `No changes detected` (SQLite e PostgreSQL).

**Pendências residuais**: as das entradas abaixo (sem CI em PostgreSQL; uma única instância local com `fsync` desligado; `ValueError` dos serviços com tipo de conta inválido; provedores P1.x; permissão de emissão protegida por revalidação e não por inacessibilidade em Python). Novas: a cobertura de ordem estrita é só em PostgreSQL 16 com `READ COMMITTED` (padrão); `grant_for_role` lê o cenário ativo e a linha antes de pedir a emissão sem bloquear, e a revalidação em `_check_grant` recusa se a configuração mudou nesse intervalo (recusa, nunca valor errado).

---

### P0.07b — bloqueio P0 da emissão (2026-10-17)

Achado da revisão externa do commit `7c6238a`: `SCENARIO_GRANT` era aceita por `transfer()`/`post_transaction()` (`ISSUANCE` → conta operacional) sem validar a dotação, e `grant_scenario_allocation()` só verificava se o cenário existia. Corrigido sem reabrir decisões de mecânica (design/24 §24.11).
1. **Via única de emissão, no serviço.** `post_transaction` recusa `SCENARIO_GRANT` (`ISSUANCE_NOT_ALLOWED`, `why=grant_path_only`) sem uma permissão interna (`_GrantPermit`) que só `grant_scenario_allocation` cria e que tem de descrever exatamente a transação (uma perna, destino, valor, chave `grant:<cenário>:<conta>`, referência, `explained`). Mesmo com permissão, `_post` revalida a dotação **dentro da transação, com as contas travadas**: uma permissão forjada só consegue o que o cenário já configurou, uma vez por conta. Chamar `transfer()`/`post_transaction()` com a natureza, a chave e a referência corretas é recusado.
2. **Validação da dotação** (`grant_scenario_allocation`): cenário existente e **ativo** (`SCENARIO_NOT_FOUND`, `SCENARIO_NOT_ACTIVE`); papel conhecido (`GRANT_ROLE_UNKNOWN`) com linha explícita (`SCENARIO_GRANT_UNSPECIFIED`); papel compatível com o tipo da conta (`GRANT_ROLE_ACCOUNT_MISMATCH`); valor **exatamente** igual à linha (`GRANT_AMOUNT_MISMATCH`). Sem valor padrão novo e sem emissão alternativa.
3. **Auditoria — invariante 18**: cada dotação é reconferida só pelo log e pela configuração (cenário, `explained`, chave, transação de uma perna, duplicidade por (cenário, conta), papel, tipo de conta, linha, valor). Os testes incluem adulteração direta no banco e emissão inválida que contorna a validação do serviço (a auditoria não confia nele).
4. **Testes**: novo `ledger/tests/test_emission.py` (29 casos): transferência direta a partir de `ISSUANCE`, `post_transaction` direto com `SCENARIO_GRANT` (inclusive imitando a dotação exata), permissão reaproveitada ou forjada, valor divergente (acima e abaixo), papel incompatível, papel desconhecido/vazio, linha ausente ou `NULL`, cenário inexistente/inativo/desativado por outro, replay após desativação, e a auditoria; cada recusa confere que saldos, lançamentos e transações ficaram idênticos. Mais um teste de concorrência (dotações paralelas à mesma conta emitem uma vez).

**Decisões técnicas a confirmar pelo Game Director** (o design 24 não as define; não alteram mecânica de jogo, mas fixam interpretação):
- **Mapa fechado papel → tipo de conta** (`GRANT_ROLE_KINDS`): `player`→jogador/Bot, `union`→União, `state`→Estado, `municipality`→Município, `militia_bank`→banco de milícia, que é exatamente o que o §24.11 nomeia. **Empresas não são papel de dotação** (o §24.11 não as lista). Os testes, que usam contas de empresa, registram um papel só de teste por `mock.patch.dict`; o mapa de produção não muda.
- **"Autorizado pelo estado do cenário" = cenário ATIVO.** Ativar já exige todas as linhas explícitas (§24.11); só um cenário fica ativo.
- **Linha que já gerou dotações não muda de valor** (`GRANT_LINE_LOCKED`), para a auditoria comparar cada dotação com a linha; `set_grant_line` também recusa papel fora do mapa.

**Evidências reais**
- PostgreSQL 16.15 (cluster local descartável, UTF8, `POLIS_EXPECT_DB=postgresql`): suíte completa → `Ran 890 tests ... OK` (0 pulados); `test_concurrency` repetido 15 vezes seguidas → 15 OK; `test_concurrency` + `test_emission` repetidos 10 vezes (antes do teste de concorrência de emissão) → 10 OK.
- SQLite: suíte completa → `Ran 890 tests ... OK (skipped=1)`; `ledger`: 223 testes; `manage.py check` sem problemas e `makemigrations --check --noinput` → `No changes detected` (SQLite e PostgreSQL).
- Um teste novo falhou de forma intermitente na primeira versão (expectativa do teste, não do código): divergências concorrentes recebem `GRANT_AMOUNT_MISMATCH` se chegam antes da dotação válida e `IDEMPOTENCY_CONFLICT` se chegam depois (mesma chave, conteúdo diferente). Ambas são recusas corretas; a asserção passou a exigir "exatamente uma OK, as outras recusadas por um desses dois códigos".

**Pendências residuais**: as mesmas da entrada abaixo (sem CI em PostgreSQL; uma única instância local; `ValueError` dos serviços com tipo de conta inválido; provedores P1.x). Novas: o estado *ativo* do cenário só é exigido na emissão (a auditoria não o reconfere, pois muda depois); e a permissão `_GrantPermit` é protegida por revalidação, não por inacessibilidade em Python (quem importa o módulo privado ainda a constrói, mas só emite o já configurado).

---

### P0.07b — revisão técnica consolidada (2026-10-17)

Segunda rodada pedida pelo Game Director antes da auditoria externa final; nenhuma decisão de mecânica foi reaberta.
1. **Obrigação pendente**: `open_obligation` compara também `tax_rate` e `tax_territory` na idempotência (mesma chave com qualquer um diferente = `IDEMPOTENCY_CONFLICT`). Para a comparação ser exata, a alíquota é validada e normalizada a 6 casas (`0.1`, `"0.10"` e `Decimal("0.100000")` são a mesma) e o território deve ser vazio ou `tipo:id`; o mesmo vale para `submit_remuneration` (antes uma alíquota com mais de 6 casas era arredondada calada pelo banco e um território malformado só falhava na quitação).
2. **Dia de competência efetivo**: calculado antes do payload canônico, que agora tem `request` (o pedido; o hash identifica a requisição) e `competence_day` (efetivo, sempre presente). O dia derivado do relógio não entra no hash, para um reenvio depois da meia-noite continuar idempotente. A auditoria sempre exige que o dia efetivo do payload seja o de todos os lançamentos (`TRANSACTION_DAY_MISMATCH`); dia informado diferente do efetivo é achado.
3. **Auditoria de `uses`**: soma por reserva dos consumos registrados nas transações comparada a `original_amount − amount` (`HOLD_CONSUMPTION_MISMATCH`); reserva inexistente (`HOLD_USE_UNKNOWN_HOLD`), de outra conta (`HOLD_USE_ACCOUNT_MISMATCH`) e `uses` malformado (`TRANSACTION_USES_INVALID`) são achados estruturados; alterar `uses` no banco e recalcular o hash continua sendo detectado. Novo invariante 17.
4. **PostgreSQL real**: PostgreSQL 16.15 (cluster descartável local, UTF8, porta 54329) com `DATABASE_URL`; `POLIS_EXPECT_DB=postgresql` confirmado por teste que não foi pulado. Novos testes de concorrência: duas chaves consumindo a mesma reserva, reserva × pagamento disputando o saldo, três quitações concorrentes do mesmo devedor.

**Evidências reais**
- PostgreSQL 16.15: `manage.py test` completo → `Ran 860 tests ... OK` (0 pulados); `test_concurrency` repetido 15 vezes seguidas → 15 OK.
- SQLite: `manage.py test` completo → `Ran 860 tests ... OK (skipped=1)` (o pulado é o teste que só roda com `POLIS_EXPECT_DB`); `manage.py check` sem problemas; `makemigrations --check --noinput` → `No changes detected` (SQLite e PostgreSQL).
- Sonda (descartada, não versionada) em PostgreSQL: 60 rodadas × 8 threads com a mesma chave e o mesmo conteúdo → todas OK com a mesma transação; das 420 requisições repetidas, 11 acharam o vencedor na checagem inicial e 409 na reconferência depois do travamento das contas; **nenhuma** chegou à violação de chave única. Ou seja, em PostgreSQL o travamento resolve a corrida antes da gravação; o caminho `IntegrityError → relê o vencedor` só é exercitado de forma determinística (simulação da checagem cega) e não foi observado numa corrida real.
- Achado de ambiente (não do código): um cluster PostgreSQL SQL_ASCII recusa JSON com acentos (`\u00e7`); produção deve usar UTF8, como o cluster dos testes acima.

**Pendências residuais**
- Não há CI neste repositório: a execução em PostgreSQL foi manual e local (comandos acima); fica para a infraestrutura de testes.
- Os serviços (não a auditoria) ainda levantam `ValueError` ao operar se acharem um tipo de conta inválido no banco; não alterado por estar fora do pedido.
- Isolamento `READ COMMITTED` (padrão) assumido; níveis mais altos exigiriam tratar falhas de serialização.
- Provedores de `W`/`S`/`T` e do salário político, valores de dotação e demais itens de P1.x seguem pendentes (ver entrada anterior).

---

### P0.07b — correções antes da auditoria externa (2026-10-16)

Pedidas pelo Game Director sobre o PR #11; nenhuma altera decisão de mecânica.
1. **Idempotência sob concorrência** (`post_transaction`): mesma chave + mesmo conteúdo devolve SEMPRE a transação original, inclusive quando duas requisições disputam a criação (a perdedora desfaz o que fez, como reservas consumidas, e relê o vencedor; há também reconferência depois de travar as contas). `IDEMPOTENCY_CONFLICT` ficou só para conteúdo diferente. Mesmo contrato aplicado a reservas, obrigações e pedidos de remuneração (antes uma corrida podia levantar `IntegrityError`). Cada `Transaction` passou a guardar o conteúdo canônico (`payload`) além do `payload_hash`. Migração `0001` regenerada (o app ainda não foi mergeado nem aplicado em lugar algum).
2. **Imutabilidade em lote**: `Transaction` ganhou o mesmo manager protegido de `Entry`; `QuerySet.update`, `bulk_update`, `update_or_create`, `delete`, `_raw_delete` e `bulk_create(update_conflicts=True)` levantam `LedgerImmutableError`; `save()` de transação já gravada continua recusado.
3. **Auditoria robusta**: valores fora do domínio das enumerações (conta, natureza, estados, política) viram achado `INVALID_ENUM_VALUE`; cada seção roda isolada e falha inesperada vira `AUDIT_SECTION_FAILED`; novo invariante 16 confere chave, instante, ator, referência, dia, hash e conteúdo canônico de cada transação contra os lançamentos (adulteração direta de metadados é detectada mesmo com o hash recalculado); `ledger_metrics` tolera tipo de conta desconhecido.
4. Documento `24`: §24.5.3 (contrato de idempotência sob concorrência) e §24.17 (invariantes 6, 15 e 16).

**Evidências (2026-10-16):** `manage.py test` → `Ran 838 tests ... OK`; `manage.py test ledger` → 171 OK; `test_concurrency` repetido 10 vezes sem falha; `manage.py check` sem problemas; `makemigrations --check --noinput` → `No changes detected`.

**Limitação conhecida:** em SQLite a corrida real entre threads é serializada pelo banco, então o caminho da violação de chave única é exercitado de forma determinística nos testes (por simulação da checagem cega) e, em paralelo, pelos testes com threads; em PostgreSQL vale também o travamento de contas com `FOR UPDATE`. Os serviços (não a auditoria) ainda levantam `ValueError` se encontrarem um tipo de conta inválido no banco ao operar.

---

## 2026-10-15 — P0.07a — registro monetário (design/24, FINAL — BOT TEST)

Documento `design/24-Registro-Monetario-FINAL-BOT-TEST.md`, **sem código**. Incorpora Q1/Q2 e as decisões de 11.1.0, 09 §45, 18.14, 19.16 e 21.60. **Aprovado pelo Game Director em 2026-10-15** (PR #10), com as correções A–D e os ajustes de R1–R10 incorporados. Branch `dev/p0.07a-registro-monetario`.

### O que define
- **Contas** (`PLAYER`, `COMPANY`, `UNION`, `STATE`, `MUNICIPALITY`, `MILITIA_BANK`, `RETENTION`, `SINK`, `ISSUANCE`); **saldo bruto / reservado / disponível para gastar** como conceitos distintos; conservação só com saldos brutos: `soma(brutos)=0` e `emitido = brutos operacionais + retenções + sumidouro` (reservas **não** entram na fórmula).
- **Lançamentos** imutáveis, em centavos inteiros, com natureza, referência obrigatória, saldos antes/depois, `Explained`; transações atômicas, idempotentes, travamento em ordem de id; estorno auditado.
- **Reservas** (mesma conta) x **retenções genéricas** (conta de custódia, destino escolhido por quem libera); **interface de roteamento tributário** (`register_tax_resolver`/`route_tax`) sem módulo militar; a ligação com ações de milícia é da P1.17.
- **Obrigações pendentes** fora do caixa; quitação determinística; não cria dinheiro.
- **Contadores `C_S`/`C_T`/`C_P`**: reserva política derivada (`P_reservada = max(0, P_dia − C_P)`), consumida/liberada sem dupla subtração; **ordem de liquidação estável**: pedidos são submetidos e liquidados como lote ordenado por chave intrínseca (classe, competência, instante do fato, pagador, natureza, referência, key), invariante à permutação.
- **Dotações** (única fonte de emissão), zero explícito, ausência recusa o cenário; **sumidouro** só recebe; título e empréstimo transferem dinheiro de contas existentes.
- **Teto de déficit público — decisão do GD (2026-10-15)**: janela móvel de 360 dias anualizada, aplicada a União/Estados/Municípios; só novas despesas discricionárias são bloqueadas; títulos não reduzem o déficit nem contornam o teto (`24` §24.16; `11` atualizado; implementação na P1.09/P1.12).
- **Integração**: gancho de pagamento da viagem (P0.06.1), `check_action` com `can_afford`/`Explained`.

### R1–R10 aprovadas (ajustes do GD)
R2: compra do governo federal com imposto à própria União não gera lançamento de uma conta para ela mesma (compensação no `Explained`). R3: substituto sem retroativo; `P_reservada` reduzida pelo valor político reconhecido. R5: atribuição territorial de impostos federais é rastreamento, não receita municipal.

### Questões herdadas por tarefas seguintes (não bloqueiam a P0.07b)
P1.04 (política de caixa insuficiente no salário, capital inicial da empresa); P1.05/P1.08 (R2, momento do imposto da Requisição Especial); P1.06 (conta da escola particular); P1.09/P1.12 (categorias, comprometimento, dívida, teto de déficit); P1.11 (provedor do salário político devido); P1.17 (resolvedor tributário).

### Documentos alterados
`24` (novo), `09` (§45.3, §45.9), `11` (teto de déficit decidido), `TASK`, `TASK_QUEUE`, `CHANGELOG_DEV`.

---

## 2026-10-15 — P0.02 — catálogo `22` auditado e atualizado

Aplicação ao `22` e ao catálogo (`catalog`) das decisões aprovadas Q3–Q8, Q10 (GD 2026-10-14). **Estrutura** vem do `22`; **números** vêm só da tabela `[PROV]` (`catalog/provisional.py`), exportável por `manage.py list_provisional [--format text|json|markdown]`. Branch `dev/p0.02-catalogo-22` (PR sobre `dev/p0.01-consolidacao-documental`, pois o PR #8 ainda não foi mergeado).

### O que mudou
- **`design/22` (CRLF preservado):** Pão com perfil `média / sem efeito` (`[PROV]`); milícia "Kit Médico Improvisado"; tabela de receitas do Exército (Armas Militares = Aço+Madeira+Plástico, Armaduras Militares = Aço+Plástico, Kits de Primeiros Socorros do Exército = Lã+Materiais hospitalares; 2★ `[PROV]`; entidades distintas das improvisadas); novas §3 (classificação e canais, **gerada**) e §4 (parâmetros `[PROV]` e preço-base por produto, **geradas**). Um teste confere documento x código.
- **Catálogo:** 73 produtos, 29 matérias-primas, **44 receitas** (+3 do Exército), **8 alimentos** (+Pão). Novos campos em `Product`: `category` (Alimento/Material/Equipamento/Durável/Militar, **uma** por produto), tags `is_consumable`/`is_permanent`/`is_military`, `commercial_channels` (declarados: varejo, entre empresas, fornecimento ao Exército, requisição especial), `base_price` e `raw_yield` (`[PROV]`). Migração `catalog/0002_classification_and_provisional_values`.
- **Valores `[PROV]` (Q3/Q4/Q5):** receita 1 unidade de cada insumo → 1 unidade; Matriz 1★ e rendimento 1; Exército 2★; Nutrição 0/5/15/30/50 por nível; intensidade de QoL 0/0,05/0,10 (debuff −, magnitude 0,05); preço-base: matéria-prima 10,00 e produto feito = soma dos insumos ÷ rendimento + 5,00 × estrelas (sem estrela conta 1). São **referência**, não preço de mercado, e calibráveis mudando `provisional.py` + `sync_catalog`.
- **Classificação e canais (Q6/Q8):** nenhum canal inferido; Varejo só bens finais (alimentos, duráveis, roupas, calçados, caneta, papel); matérias-primas e intermediários só entre empresas; produtos do Exército só por contrato federal e fora de Varejo e do comércio entre empresas; Requisição Especial da milícia cobre exatamente os insumos diretos das receitas improvisadas (Aço, Madeira, Plástico, Lã, Materiais hospitalares). EPIs, materiais escolares/hospitalares e uniforme não estão no Varejo (uso institucional/operacional, Q10 fora da primeira implementação). Sem limite de capacidade de inventário nem de estoque do Exército (Q6). Sem produto Acabamentos (Q7).
- **Validação:** erros novos `CATEGORY_MISSING/INVALID`, `CATEGORY_SECTOR_MISMATCH`, `MILITARY_TAG_MISMATCH`, `FOOD_NOT_CLASSIFIED_AS_FOOD`, `FOOD_WITHOUT_PROFILE`, `CONSUMABLE_AND_PERMANENT`, `CHANNEL_INVALID`, `RETAIL_CHANNEL_NOT_FINAL_GOOD`, `MILITARY_IN_INTER_COMPANY_TRADE`, `ARMY_CHANNEL_NOT_ARMY_PRODUCT`, `ARMY_PRODUCT_IN_RETAIL`, `REQUISITION_NOT_A_MILITIA_INPUT`, `INVALID_RAW_YIELD`, `INVALID_BASE_PRICE`; removido `PROCURED_WITH_RECIPE`. Pendências novas (apenas se o valor voltar a faltar): `RAW_YIELD_UNSPECIFIED`, `BASE_PRICE_UNSPECIFIED`. NULL continua ≠ 0 e a recusa `UNSPECIFIED_DESIGN_VALUE` continua existindo.
- **Serviços:** `category_of`, `channels_of`, `has_channel`, `base_price_of`; `uses_of` inclui canais comerciais e ação militar; `check_production_ready` aceita os produtos do Exército (produzidos por empresas Industriais).
- **Auditoria dos critérios da fila:** Petróleo em Extrativismo ✔; usos compatíveis: todo produto declara ao menos um uso (teste); estrela mínima em todo produto produzido ✔ (milícia "Não existe"); múltiplos ingredientes ✔; catálogo utilizável como seed único (`sync_catalog` idempotente e atômico) ✔.

### Lacunas que permanecem (todas em `KNOWN_GAPS`)
| Código | Lacuna | Bloqueia |
|---|---|---|
| `GAP_OPERATIONAL_MATERIALS_UNDEFINED` | materiais operacionais e consumo por funcionário (`02` §10/§20). **Aprovado (Q10)**: fora da primeira implementação de Empresas | P1.04 (limitação conhecida) |
| `GAP_VEHICLE_RELATION_UNDEFINED` | produto Carro x veículo (veículos adiados, `04` §21) | sistema de veículos (futuro) |

**Decisão do GD (2026-10-15):** a empresa produtora dos produtos militares do Exército é **Industrial / Produção** (`catalog.constants.ARMY_PRODUCER_SECTOR`, `services.producer_sector_of`); a lacuna `GAP_ARMY_PRODUCER_SUBTYPE_UNDEFINED` foi **fechada** e sai de `KNOWN_GAPS`; a aplicação é da P1.04. Os produtos militares continuam entidades distintas dos improvisados da milícia. Valores `[PROV]` aprovados como pontos de partida do Bot Test, não definitivos. Duração do efeito alimentar e taxa de correio: P1.02.

Resolvidas nesta tarefa (as linhas da tabela da P1.01 acima ficam como histórico) — `GAP_ARMY_PRODUCER_SUBTYPE_UNDEFINED` (GD 2026-10-15), `GAP_FINISHINGS_UNDEFINED` (Q7), `GAP_MATRIZ_STARS_UNDEFINED`, `GAP_PRODUCTION_QUANTITIES_UNDEFINED`, `GAP_FOOD_VALUES_UNDEFINED`, `GAP_FOOD_PROFILE_BREAD_UNDECLARED`, `GAP_COMMERCIAL_USES_UNDECLARED`, `GAP_INVENTORY_CATEGORIES_UNDEFINED`, `GAP_BASE_PRICE_UNDEFINED` (todas por Q3–Q8 e valores `[PROV]`).

### Itens `[PROV]` que pertencem a tarefas seguintes (não decididos aqui)
- **P1.02 (Inventário):** duração do efeito temporário de alimento e taxa do correio (a taxa usará `base_price`, mas o percentual é `[PROV]` da P1.02); ordenação do auto-consumo "menor ganho".
- **P1.04 (Empresas):** aplicar o produtor do Exército = Industrial/Produção (decidido); salário do Dono.
- **Subsídio setorial (D16):** o catálogo já fornece categoria e canais; a lista de setores subsidiáveis é do `11`/P1.04, sem tabela paralela aqui.

### Testes
Reescritos os testes de `catalog` ao estado aprovado (130 testes): doc ↔ código (receitas, Exército, §3, §4), números só da tabela `[PROV]`, regras de classificação/canais, cada novo código de erro, estados "não especificado" simulados com produtos sintéticos, constraints do banco, carga/sync dos novos campos.

---

## 2026-10-14 — P0.01 — consolidação documental

Consolidação, em PR documental único (#8), das decisões aprovadas do Game Director (mensagens de 2026-10-12, 2026-10-13 e 2026-10-14, esta última com Q1–Q12 e confirmações). **Somente documentos**: nenhum código, teste ou migração foi alterado. `06`, `11` e `19` **permanecem em REVIEW** por dependências de execução (abaixo); `07` e `09` permanecem FINAL (alterações aditivas). O P0.01 é considerado concluído como fase de consolidação; isso **não** significa que todas as decisões D1–D25 estejam executadas: ver "Dependências".

### Decisões aprovadas e documentadas
- **Política (`06`, `11`, `07`):** D1 limite de mandatos consecutivos (padrão 2, mín. 1, máx. 10). D2 empate presidencial mantém segundo turno; sorteio com semente registrada para Prefeito, Governador e última cadeira da Câmara. D3 janela eleitoral de 7 dias; sem candidatos a nova janela começa imediatamente, titular permanece; sem titular o cargo fica vago; transferências não distribuídas ficam no nível superior; quórum sobre cadeiras ocupadas. D4 cenário configurável com ocupantes reais; "exercer" = posse + mandato estatutário completo; crédito de serviço anterior só por cenário; dois contadores (consecutivos x concluídos). D5 ciclos independentes por cargo, inclusive Câmara. D6 substituto indicado por cada titular, alterável com histórico; eleição extraordinária se inelegível/indisponível; vacância até a posse com prazos suspensos; assumir outro cargo vaga o anterior. D7 posse por deposição é exceção aos requisitos; emprego encerrado na posse de qualquer cargo político; propriedade preservada com restrição a contratos públicos; mandato por deposição conta para o limite consecutivo, não para experiência; liderança da milícia transferida. D8 pagadores (União: Presidente e Deputados; Estado: Governador; Município: Prefeito), acúmulo diário, obrigação pendente sem caixa. D9 `07` prevalece (só Presidente e Deputados formalizam projetos). D11 Carisma mínimo único. D12 pisos municipais sobre receitas de 30 dias, mesma base para Educação (5% constitucional), Saúde e Infraestrutura; União e Estados sem pisos. D13/D14 imposto sobre lucro e leis municipais fora do primeiro Bot Test. D15 mudanças de lei valem só para janelas abertas após a vigência; salários e parâmetros fiscais no tick efetivo. D16 campanhas (Deputado → Estado; conflito = mesmo tipo, território e período sobreposto; reserva na entrada em vigor, sem saldo não opera; custo do caixa federal ao sumidouro). D17 interregno após deposição. Leilão de lote não é contrato de fornecimento para `06.23`.
- **Salário (`11` 11.1.0, `01` §1.7):** dois contadores diários separados (`C_S` limite por habilidade, `C_T` teto legal incluindo salário político); salário político não consome `S` mas consome `T`; natureza do lançamento exclui doações, vendas, reembolsos, transferências, dotações, indenizações e dívidas; `T` aplicado ao total diário; cálculo determinístico independente da ordem (parcela política reservada); `W` prevalece sobre `S` baixo sem criar dinheiro nem passar `T`; soldo `W × m_patente` com excedente não pago e sem dívida. O `01` §1.7 foi reescrito para refletir isso (não há mais nota de divergência).
- **Dinheiro (`09` §45, `21` 21.60, `TASK_QUEUE` P0.07):** Q1 dotação inicial explícita por conta (humana ou Bot) como lançamento de emissão, fonte de emissão durante a formação da população, zero válido se explícito, ausência recusa o cenário, sem emissão periódica pela União. Q2 destinos: viagem, correio e fundação de empresa → caixa federal; leilão de lote público → Município do lote; milícia (fundação/melhorias) → sumidouro; campanhas → caixa federal como pagador e destino final no sumidouro; tratamento → hospital ou prestador do `04` §13 (já definido). Sumidouro = conta contábil identificada, fora do dinheiro em circulação, dentro da conservação contábil.
- **Catálogo e Empresas (aplicar na P0.02/P1.02/P1.04):** Q3 valores `[PROV]` autorizados, tabela auditável, receita-base 1:1. Q4 receitas militares do Exército provisórias (Industrial, 2★): Armas Militares, Armaduras Militares e Kits de Primeiros Socorros do Exército, com nomes distintos de Armas/Armaduras Improvisadas e Kit Médico Improvisado. Q5 Pão consumível. Q6 cinco categorias principais únicas e tags separadas; sem limite de capacidade do inventário do jogador nem do estoque institucional do Exército; reserva impede dupla promessa; sem produção sob encomenda. Q7 sem produto Acabamentos. Q8 usos comerciais declarados no catálogo. Q9 Dono: salário do cargo, sem lucro/dividendos. Q10 materiais operacionais fora da primeira implementação (limitação conhecida).
- **Militar (`19`):** D18a/b Exército federal, quartéis em Infraestrutura, atribuição territorial e retenção; D19 sem pressupor STF; D20 hospitalização por combate sem reduzir Saúde, ausência de fórmula de dano é limitação aprovada; D21 QoL nacional (snapshot diário, só no Poder Operacional da milícia); Q12 fallback (último snapshot, senão multiplicador 1 com "QoL nacional indisponível"); D22; D23 fluxos A e B; D24 princípio e receitas provisórias; D25 locais institucionais; Q11 multiplicadores `[PROV]` Militar 1×, Capitão 2×, General 4×, Marechal 6× (parâmetros fixos, não leis, sem validação automática contra cargos políticos).

### Documentos alterados
`06`, `07`, `09`, `10`, `11`, `18` (18.14), `19`, `01`, `04`, `14`, `21`, `22` (nota), `SITEMAP-REVIEW`, `TASK`, `TASK_QUEUE`, e `README`/`pendencias`/`implicacoes-tecnicas` (marcados obsoletos).

### Dependências de execução (não são decisões abertas de design)
- **P0.02:** aplicar ao `22` e ao catálogo as receitas militares, a renomeação dos produtos, o perfil do Pão, os valores `[PROV]`, categorias/tags, usos comerciais e categorias de subsídio. O texto atual do `22` e os testes do catálogo permanecem inalterados até lá (o `22` é lido por `catalog/tests`).
- **P0.07a/b:** contas, obrigações, contadores salariais, retenções, dotações, sumidouro, dívida pública.
- **P1.04:** salário do Dono. **P1.18:** cenário (R-BT-01, quartéis, saldos e estoques iniciais).
- **Sem proposta ainda:** teto de déficit público (após P0.07a); mecânica de zoneamento por lei e aprovador de mudança de uso (P1.07).

### Interpretações técnicas registradas (não alteram mecânica)
- **Dia de competência:** cada remuneração conta no contador do dia em que foi devida, e não do dia em que uma obrigação pendente seja paga; a ser detalhado no P0.07a.
- **Ordem entre pagamentos não políticos do mesmo jogador:** sequência do registro monetário, com desempate por identificador da obrigação.
- Sitemap §27–36 x dashboards do `21`: cobertos; lacuna corrigida ("Bot ruim vs sistema ruim", 21.51).

### Verificação
Ver o PR #8 (suíte completa, `check`, `makemigrations --check` e greps de consistência).

---

## 2026-10-12 — Action Registry (P1.03)

### Escopo
- **Implementado:** `players/registry.py` (registro, descritor do `21 §20`, consulta e execução) e `travel/registration.py` (Viajar). Ações registradas, com **ids estáveis**: `work`, `study`, `leisure` (registradas por `players`) e `travel` (registrada por `travel`, cada app no seu `ready()`, como os hooks). `Viajar` **não** entrou no enum `Action` (não tem custo de Energia, `04 §2.2`).
- **O registro descreve e delega; não reimplementa regra.** Disponibilidade e execução usam **a mesma função**: `players.services.action_refusal` (bloqueios e depois Energia, extraída de `perform_action`) e `travel.services.travel_refusal` (extraída de `start_travel`). A execução chama os serviços de sempre (`perform_action`, `start_travel`), que revalidam dentro da própria transação; hooks, provedores de bloqueio e atomicidade continuam valendo. Humanos e bots usam o mesmo caminho (`CLAUDE.md §5.4`).
- **Fora, como pedido:** Action Masking (`21 §21`, P1.19), infraestrutura de bots (P1.18), inventário, empresas, mercado, sistema financeiro. Nenhum comportamento de P0.04/P0.05/P0.06/P0.06.1 mudou; os 582 testes anteriores passam **sem edição**.

### Decisões do Game Director (2026-10-12) aplicadas
1. **Trabalho sem emprego, Estudo sem matrícula e Lazer sem atividade continuam como estão** (P0.04/P0.05 não foram alteradas para bloqueá-los). **Integração futura:** Empresas (P1.04) e Escolas (P1.x) devem entrar pelos mecanismos existentes — provedores de bloqueio (`register_block_provider`), `ActivityContext` e hooks de ação — e **não** por um caminho de execução separado.
2. **Contrato do descritor sem semântica inventada:** `category` e `visibility` valem `UNSPECIFIED` (o design não define taxonomia nem política); `cooldown` vale `NONE` (não existe mecanismo geral de cooldown; nenhum prazo foi inferido); `effects` são descritivos e executados pelo serviço dono; nenhuma regra de bot foi criada. Nenhum campo do `21 §20` ficou sem representação, então não houve conflito a consultar.
3. **Disponibilidade geral x validação de alvo:** `available_actions` **não enumera lotes**. Sem alvo, Viajar continua disponível em geral (`target_required=True`, `target_validated=False`); com alvo, valida o destino (`INVALID_DESTINATION`, `SAME_LOCATION`). Executar sem alvo é recusado com `TARGET_REQUIRED`. **A consulta é consultiva; a execução é a autoridade** e revalida tudo.
4. **Escopo de execução:** só as validações compartilhadas foram extraídas; parâmetros de contexto interno (`burnout_risk`, `effect`, `activity`) **não** entram pelo registro (`INVALID_PARAMS`, nunca ignorados em silêncio); nenhum custo foi inventado.

### Contrato do registro
- **Descritor:** `id`, `name`, `category`, `requirements`, `cost`, `cooldown`, `target` (`TargetSpec(kind, required)`), `effects`, `visibility`. `requirements` lista os códigos de recusa que as regras do dono podem produzir (um teste confere que nenhum código real escapa); os motivos concretos de um jogador vêm em `blocked_by`, inclusive os de provedores de outros sistemas (ex.: `TRAVELING`).
- **API:** `check_action(player_id, action_id, target=None)`, `available_actions(player_id)` (uma sessão sincronizada, custo constante), `execute_action(player_id, action_id, target=None, **params)`, `register_action`, `list_descriptors`, `get_descriptor`.
- **Códigos do registro:** `UNKNOWN_ACTION`, `INVALID_PARAMS`, `TARGET_REQUIRED`, `TARGET_NOT_ALLOWED`; os demais são os dos serviços. Alvo malformado (não inteiro, booleano, fora de int64) é `INVALID_PARAMS`; lote inexistente continua `INVALID_DESTINATION`.
- **Custo/preview (doc 20):** Energia vem de `Balance` (20/10/10 por padrão, segue overrides) e `burnout_change` é o `Explained` da regra (risco 1, o mesmo da execução); Viajar devolve o `quote_travel` com `Explained` de tempo e custo. O custo monetário é **calculado, não cobrado**: `payment` = `NO_PAYMENT_SYSTEM` (sem sistema de dinheiro), `NOT_REQUIRED` (custo 0) ou `WOULD_CHARGE` (há handler). `INSUFFICIENT_FUNDS` só existe na execução: o handler debita, então não dá para prever sem cobrar.

### Interpretações técnicas (reversíveis; não são regra de gameplay)
5. Ordem de `available_actions`: por `id` (determinística). `travel_refusal` preserva a ordem anterior (`INVALID_DESTINATION`, `ALREADY_TRAVELING`, `SAME_LOCATION`); `start_travel(None)` continua `INVALID_DESTINATION`.
6. A consulta sincroniza o jogador (trava + catch-up lazy, como `get_snapshot`) e é idempotente; o custo acima do catch-up é fixo, independente do tempo decorrido (o catch-up em si já era lazy).
7. Pelo registro, Trabalho/Lazer rodam sem `ActivityContext`/efeito (padrões do P0.04). Quando Empresas/Escolas/Atividades existirem, o contexto virá do sistema que o conhece, **não** do cliente; o ponto de extensão será desenhado nesse bloco (não foi criada abstração sem necessidade concreta).

### Verificação
- **642 testes** (582 anteriores, sem edição, + 60 novos); `check` e `makemigrations --check` limpos.
- Testes novos: contrato do descritor, requisitos declarados, proteção de parâmetros, alvo, disponibilidade geral x alvo, equivalência de recusas e de execução com os serviços diretos, preview/custo, hooks/provedores, atomicidade, custo de queries, e propriedades com sementes fixas (equivalência registro x serviço, previsão x execução, consultas extras sem efeito, determinismo, guarda de cobertura).
- **Mutação:** 34 mutantes nas regras novas e nas validações extraídas; 3 sobreviveram na primeira rodada (ordem de `available_actions`, fronteira `Energia == custo`, `start_travel(None)`) e ganharam testes; os 34 são detectados.

### Pendências registradas
- Máscara de ações para bots (`21 §21`) apoia-se em `available_actions`: **P1.19**.
- Empresas, Escolas e atividades de Lazer entram pelos mecanismos existentes (decisão 1); o contexto da atividade pelo registro será desenhado com esses sistemas.
- Categoria e visibilidade de ações, e qualquer cooldown geral, dependem de decisão de design (hoje `UNSPECIFIED`/`NONE`).
- Cobrança real da viagem depende do futuro sistema financeiro (inalterado desde o P0.06.1).

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
