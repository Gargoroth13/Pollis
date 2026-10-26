# 10a — Imóveis: o que foi implementado (P1.07a) e o que depende de decisão (proposta)

> **Status:** PROPOSTA — o `10` está FINAL — BOT TEST e define a estrutura; este documento registra as **lacunas** encontradas ao
> implementar a primeira etapa (propriedade, leilão, venda, obra com lote) e a **menor solução técnica** usada em cada uma
> (CLAUDE.md §13). Valores numéricos ausentes estão `[PROV]` em `properties/params.py` (tabela auditável `provisional_table()`).
> Nenhuma mecânica nova foi criada.

## 1. Etapas de P1.07

| Etapa | Conteúdo | Estado |
|---|---|---|
| **P1.07a** (esta) | Propriedade de lotes (título + histórico), leilão público com extensão, venda entre proprietários, imóvel residencial construído, obra da Construtora ligada ao lote, auditoria, ações no Action Registry | implementada |
| P1.07b | Unidades e ocupação, residência ativa, **Aluguel** (handler `RENT` no motor de `18`), venda de imóvel alugado mantendo o contrato, QoL estrutural, moradia inicial | a fazer |
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
| G9 | **Moradia inicial** dos jogadores (lotes OCUPADOS sem `Building`) | Não tocada; auditoria não exige `Building` em lote OCUPADO | **Sim, para P1.07b** (residência ativa/aluguel) |
| G10 | Lance **proxy**/máximo automático e desempate no mesmo instante | Não existem; o lance é aceito em ordem de trava, um por vez | Não |
| G11 | Imposto sobre propriedade (`TAX_PROPERTY`) | Não cobrado nesta etapa; segue Orçamento/Leis (P1.09/P1.12) | Não |

## 5. Decisões necessárias ao Game Director (apenas as da próxima etapa)

Para **P1.07b** (unidades, moradia, aluguel): **G9** — como entra a moradia inicial dos jogadores (mantida como está, sem prédio, e a "residência ativa" aponta um lote OCUPADO; ou criar um `Building` inicial por lote residencial gerado). A P1.07b parte da primeira opção (nenhuma mecânica nova) se não houver resposta.

O restante (G1–G8, G10–G11) pode continuar provisório sem comprometer a correção desta etapa; G1 precisa ser decidida antes de o Bot Test ligar os bots.
