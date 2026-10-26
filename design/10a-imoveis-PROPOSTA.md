# 10a — Imóveis: o que foi implementado (P1.07a–b) e o que depende de decisão (proposta)

> **Status:** PROPOSTA — o `10` está FINAL — BOT TEST e define a estrutura; este documento registra as **lacunas** encontradas ao
> implementar a primeira etapa (propriedade, leilão, venda, obra com lote) e a **menor solução técnica** usada em cada uma
> (CLAUDE.md §13). Valores numéricos ausentes estão `[PROV]` em `properties/params.py` (tabela auditável `provisional_table()`).
> Nenhuma mecânica nova foi criada.

## 1. Etapas de P1.07

| Etapa | Conteúdo | Estado |
|---|---|---|
| **P1.07a** | Propriedade de lotes (título + histórico), leilão público com extensão, venda entre proprietários, imóvel residencial construído, obra da Construtora ligada ao lote, auditoria, ações no Action Registry | implementada |
| **P1.07b** | Unidades e ocupação, residência ativa, **Aluguel** (handler `RENT` no motor de `18`), venda de imóvel alugado mantendo o contrato, QoL estrutural, moradia inicial | implementada (§6) |
| P1.07c | Localização de empresas (comercial/industrial), terreno da Matriz (`production.register_site_provider`), mudança de uso | a fazer |

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

Para **P1.07c** (empresas e Matriz): **G5** — tipos de imóvel comercial/industrial e a relação estrela → nível comercial (`10` §16-17 não dão números); **G6** — mudança de uso do lote e quem aprova (`10` §33 "[ABERTO]"). A P1.07c não começa a implementação desses tipos sem essa resposta.

Da P1.07b nenhuma decisão **bloqueia** a próxima etapa; as lacunas H1–H9 (§7) seguem provisórias. G1 precisa ser decidida antes de o Bot Test ligar os bots.

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
| H9 | Dívidas de aluguel na venda; propostas abertas na venda | Dívidas ficam com o antigo locador; propostas abertas falham no aceite com `LANDLORD_NOT_OWNER` |

Seguem abertos (fora da P1.07b): limite de propriedade por jogador (lei), imposto de propriedade (G11), aluguel comercial, empresa inquilina.
