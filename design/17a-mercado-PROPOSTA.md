# 17a — Mercado: o que está definido e o que falta decidir (proposta)

> **Status:** DRAFT — PROPOSTA (nada aqui vira mecânica antes da decisão do Game Director)
>
> Origem: ao iniciar P1.05 foi verificado que o `17` (FINAL — BOT TEST) define a **transparência** do mercado (histórico, médias,
> tendência, oferta, produção, consumo, custos da empresa), mas **nenhum documento define o mecanismo** que gera as vendas: anúncios,
> quem fixa preços, taxas e matching. `05` §13/§16 diz apenas que existe um "Mercado de Jogadores" com "fricções próprias" e lista
> "Taxas do Mercado de Jogadores" e "Regras detalhadas do Mercado de Jogadores" em §22 (questões em aberto). CLAUDE.md §13: parar na
> ambiguidade e registrar.

## 1. O que foi implementado (P1.05a) sem inventar regra

- Camada de dados do `17`: `market.recording.record_sale` (ponto único de integração), histórico imutável, agregados diários por produto, histórico agregado de custos da empresa, estatísticas (média ponderada 24 h, menor/maior preço, produção/consumo reais, tendência 7×7, "Sem dados", gráficos de 30 dias, visão geral), relatório de custos (7×7, principal contribuição observada) e `audit_market`.
- Regra de integração: **só há venda no histórico se o dinheiro já se moveu** (lançamento `SALE` do comprador ao vendedor, pelo valor total, não estornado). Quem concluir vendas (Varejo, entre empresas, Mercado de Jogadores, contratos) chama `record_sale` na mesma transação do pagamento.
- Oferta ("estoque disponível"): `market.rollup.register_supply_provider`. Sem provedor, o indicador é "Sem dados" (não 0).

## 2. O que NÃO foi implementado (falta decisão)

| # | Lacuna | Por que bloqueia | Opções |
|---|---|---|---|
| 1 | **Quem fixa o preço de venda do Varejo** e como o jogador o consulta/compra (`02` §11 só define capacidade de venda) | Sem preço e pagamento não há `SALE` do Varejo | (a) o Dono/Vendedor define o preço por produto na loja; (b) preço derivado de regra do catálogo; (c) outro |
| 2 | **Mercado de Jogadores**: anúncio (quem anuncia, preço fixo × oferta/lance, prazo, cancelamento), matching e liquidação | `05` §13 só cita a existência e "fricções próprias" | (a) anúncios de preço fixo, compra direta; (b) livro de ofertas; (c) leilão |
| 3 | **Compra entre empresas** (insumos): como uma empresa encontra e compra de outra (preço, estoque do vendedor) | `trade.purchase_refusal` define só *quem pode comprar o quê* | mesmo mecanismo do item 2 estendido a empresas, ou contrato (`18`) |
| 4 | **Taxas/impostos de venda**: percentual, quem paga, destino, e se o lançamento é `SALE` único ou `SALE` + `TAX_SALES` | `05` §22 e `11` deixam em aberto; `24` tem a natureza `TAX_SALES` | (a) sem taxa no 1º Bot Test; (b) taxa fixa paga pelo vendedor à União |
| 5 | **Definição de oferta** ("estoque disponível" do `17` §17.5): estoque anunciado × estoque total das empresas | Decide o provedor de oferta | (a) soma dos anúncios abertos; (b) estoque total de empresas que vendem |
| 6 | **Venda estornada**: o histórico é imutável e a estatística continuaria contando; hoje a auditoria acusa `SALE_PAYMENT_REVERSED` | Estorno é correção técnica (`24`) | (a) deixar acusar; (b) permitir um registro de anulação no histórico que as médias ignorem |

## 3. Próximo passo técnico após a decisão (P1.05b)

Implementar o mecanismo escolhido sobre `record_sale`, ligar o Varejo (`companies.retail.fulfill_sale`) e a compra entre empresas (`companies.stock.credit_stock`) ao pagamento + registro na mesma transação, registrar o provedor de oferta, expor as ações no Action Registry (mesmas para Bots e jogadores) e cobrir com testes de ponta a ponta (dinheiro conservado, estoque, histórico, estatísticas).
