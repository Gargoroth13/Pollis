# 12a — Histórico do Mundo: implementação da P1.14a — lacunas técnicas e interpretações (PROPOSTA)

**Status:** PROPOSTA — documento de apoio ao `12 — Histórico do Mundo` (FINAL — BOT TEST). Nada aqui altera o design; cada linha é uma lacuna **técnica** onde o
`12` é silencioso, a escolha feita para não bloquear e o que o GD pode revisar. Valores sem fonte: `history/params.py::parameter_table()` (todos `[PROV]`).

## 1. O que a P1.14a entrega (app `history`, migração `0001`)
Notícia permanente e imutável (`NewsItem`: instante, categoria, manchete, texto, referência, dados estruturados de origem), publicação com **modelos de texto com variação
determinística**, idempotência por chave, **marco único** (restrição única no banco), **intervalo mínimo por indicador**, prioridade interna (12.13), feed público com
filtros e cursor estável, arquivo por mês, lista de marcos, auditoria (`audit_history`), Admin somente-leitura.

**Integrações ligadas:**
- `02 Empresas`: `found_company` envia o marco "primeira empresa de cada tipo" (12.5, 12.8), na mesma transação da fundação.
- `07 Leis`: aprovação pela Câmara, veto, derrubada de veto e entrada em vigor — **somente** se a `LawSpec` do catálogo tem `newsworthy=True` (12.6). O 12 não julga importância.
- `17 Transparência de Mercado`: tendência de 7 dias (`market.stats.trend`, o MESMO cálculo) no tick diário do mundo, só sobre os agregados diários.

**API pronta, sem chamador porque o sistema de origem ainda não existe:** falência 5★+ (`news.company_bankrupt`), resultado de eleição com porcentagem real e marco da primeira
eleição de cada cargo (`election_concluded`, `chamber_elected`), deposição (`government_change`), início e resultado de conflito (`conflict_started`, `conflict_result`).
Todas testadas diretamente; quando `06`/`19` forem implementados só precisam chamá-las.

## 2. Lacunas e interpretações
| # | Ponto | O que o design diz | Escolha técnica | Revisão |
|---|---|---|---|---|
| H1 | Falência de empresa | 12.5 manda noticiar falência de 5★+; o `02` só cita "falência" como serviço da Financeira e não define falência de empresa | Não existe mecânica de falência; `company_bankrupt` está pronta e testada (5★+ publica, abaixo disso não, uma vez por empresa) e **sem chamador**. Nenhuma falência foi inventada | GD decide quando/como empresa falece (outro documento) |
| H2 | "Ano 1, Mês 1" do arquivo (12.10) | exemplo de arquivo por ano/mês do servidor | O arquivo agrupa por ano/mês do **calendário do jogo** (o tempo do jogo é o real, decisão de 2026-09-30); "Ano N" relativo ao início do servidor é só apresentação e exigiria a data de início oficial | apresentação |
| H3 | Prioridade de notícias de lei | 12.13 não lista leis | `[PROV]` mesma prioridade das eleições (3); só desempata notícias no MESMO instante | valor |
| H4 | Gênero/artigo dos nomes de produto | exemplo "do aço" | O catálogo não registra gênero: os modelos usam "de {produto}" (serve a todos) | texto |
| H5 | Outras métricas econômicas (12.4) | "pode noticiar" estoque, produção, consumo, volume | Só a tendência de preço (a "notícia padrão") é implementada; as outras são opcionais, sem limiar no design | GD pode pedir |
| H6 | Intervalo mínimo (12.12) | existe, sem valor | `[PROV]` 3 dias por produto; limiar de tendência `[PROV]` 5 %; "grande" evento econômico `[PROV]` ≥ 20 % | valores |
| H7 | Tick atrasado vê o dia corrente inteiro | — | `market.stats` calcula o dia corrente ao vivo sem teto de instante; num tick processado com atraso, a tendência pode incluir vendas posteriores ao instante do tick. Com ticks processados em dia (o normal) não há efeito. Não alterei o `17` | `17`, se quiser teto por instante |
| H8 | Chamada de leis no motor | 12.14 lista aprovação, veto, derrubada e vigor | Sanção, rejeição, retirada e veto mantido **não** geram notícia (não estão na lista). Cada notícia de lei tem chave (proposta, evento, rodada): reabertura de votação por troca de Presidente pode noticiar a nova aprovação | interpretação |
| H9 | Referência navegável (12.1) | leva à página quando existe | Resolvedores por tipo de referência (`register_ref_resolver`); sem páginas ainda, o caminho é `null` e a referência (tipo + id) é entregue | UI (P1.16) |

## 3. Garantias testadas
Notícia imutável (individual e em lote; restrições no banco); mesma entrada → mesmo texto, variações todas usadas; campo faltando é erro; idempotência por chave (inclusive sob fundações
simultâneas e, em PG, publicações simultâneas); intervalo mínimo nas bordas; tendência abaixo/no/acima do limiar, "sem dados" nunca vira notícia; feed ordenado, filtros, cursor sem repetir nem perder
itens mesmo com chegada de notícias novas; notícias antigas continuam no arquivo; o feed custa 1 consulta por página e nunca toca tabelas brutas; leis não noticiáveis nunca publicam, noticiáveis publicam
cada fato uma vez.
