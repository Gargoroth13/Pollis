# 02a — Estrelas das empresas: proposta de progressão

> **Status:** DRAFT — PROPOSTA (não implementar a progressão antes de aprovada)
>
> Origem: decisão do Game Director de 2026-10-19 (`02` §25.1): todas as empresas começam em 1★ `[PROV]`; a progressão é por
> **melhorias compradas com o caixa da empresa, com custo crescente por estrela**; antes de implementar, documentar custos,
> limites e desbloqueios afetados e identificar apenas as lacunas que realmente exigem decisão.
>
> Tudo que está marcado `[PROPOSTA]` é um valor inicial calibrável (`02` §22: "valores calibrados principalmente através dos
> testes com bots"). Nada aqui altera a estrutura do `02`. Itens em **"Decisão necessária"** não têm base em nenhum documento.

---

## 1. O que já está definido (base documental)

| Fato | Fonte |
|---|---|
| Estrelas = estrutura e potencial da empresa; não são desempenho | `02` §14 |
| Toda empresa nasce em 1★ `[PROV]`; sobe por melhorias pagas pelo caixa da empresa, com custo crescente por estrela | `02` §25.1 (GD 2026-10-19) |
| Faixa de estrelas dos produtos/receitas: 1★ a 5★ (restrição já existente no catálogo) | `22`, `catalog` |
| Estrela mínima por receita (1★ a 5★) | `22`; `implicacoes-tecnicas` 15 |
| Estoque máximo, nº de Engenheiros, nº de Advogados, teto de qualidade: **dependem da estrela** | `02` §6, §9, §11.1, §18 |
| Estrela determina o nível de imóvel comercial que a empresa pode ocupar | `10` §16 |
| Ranking "maior empresa já alcançada" = maior estrela já atingida (recorde permanece) | `14` §14.4.2 |
| Cobrança é feita da conta da empresa (o Dono não é dono do saldo); dinheiro não é criado | `24`, `02` §16 |

## 2. Proposta

### 2.1. Faixa e regra de subida
- Estrelas de **1 a 5** `[PROPOSTA]` (o catálogo já limita as receitas a 1★–5★; o Carro exige 5★).
- A empresa sobe **uma estrela por vez** (n → n+1), por uma ação **"Melhorar empresa"** do Action Registry (mesmo registro para
  bots e humanos), executável **somente pelo Dono** (coerente com `02` §25.3).
- Requisito único: **caixa da empresa ≥ custo** da próxima estrela. Sem requisito de skill, diploma ou tempo `[PROPOSTA]`.
- A melhoria é **imediata** ao pagamento `[PROPOSTA]`; sem fila ou tempo de obra.
- Recusa explicada (`20`): estrela máxima, caixa insuficiente (com valor do custo e do saldo).

### 2.2. Custo crescente `[PROPOSTA]`
O custo é proporcional ao **custo de fundação do tipo** (`02` §17), de modo que tipos mais caros de fundar também são mais caros
de melhorar, com multiplicadores crescentes:

| Subida | Multiplicador do custo de fundação | Varejo (15.000) | Serviços (25.000) | Matriz (40.000) | Construtora (60.000) | Industrial (80.000) | Financeira (100.000) |
|---|---|---|---|---|---|---|---|
| 1★ → 2★ | 0,5× | 7.500 | 12.500 | 20.000 | 30.000 | 40.000 | 50.000 |
| 2★ → 3★ | 1,0× | 15.000 | 25.000 | 40.000 | 60.000 | 80.000 | 100.000 |
| 3★ → 4★ | 2,0× | 30.000 | 50.000 | 80.000 | 120.000 | 160.000 | 200.000 |
| 4★ → 5★ | 4,0× | 60.000 | 100.000 | 160.000 | 240.000 | 320.000 | 400.000 |

Valores em reais. A tabela é parâmetro (uma linha por subida), exibida com `Explained` (`20`): custo, multiplicador, custo-base do
tipo, saldo da empresa.

### 2.3. Limites e desbloqueios afetados `[PROPOSTA]` (calibráveis)

| Parâmetro | 1★ | 2★ | 3★ | 4★ | 5★ | Onde é usado |
|---|---|---|---|---|---|---|
| Teto de qualidade (escala de qualidade do `02` §18) | 100 `[PROV]` | 200 | 300 | 400 | 500 | P1.04c (`params.QUALITY_CAP_PER_STAR`) |
| Engenheiros | 1 | 2 | 3 | 4 | 5 | `02` §9.1 (P1.04d) |
| Advogados | 1 | 2 | 3 | 4 | 5 | `02` §9.2 (P1.04d) |
| Estoque máximo (unidades) | 500 `[PROV]` | 1.000 | 1.500 | 2.000 | 2.500 | `02` §11.1, P1.04c (`params.STOCK_CAPACITY_PER_STAR`); P1.04e para a venda |
| Limite de funcionários | a definir | | | | | `02` §14 ("pode influenciar") |
| Receitas liberadas | receitas com `min_stars ≤ estrela` | | | | | `22`, P1.04c |
| Nível de imóvel comercial | a definir com `10` §16 | | | | | P1.07 |

Engenheiros/Advogados "= estrela" é um ponto de partida linear.

**Valores `[PROV]` aplicados em P1.04c (2026-10-20), para confirmação do GD** — o `02` e o `22` não fixam unidades, então a
implementação usou a forma mais simples (linear por estrela), parametrizada em `companies/params.py`, listada em
`provisional_table()` e auditável, sem decisão de design escondida:
- **Teto de qualidade** = 100 × estrela, na mesma escala dos níveis de skill (a qualidade de cada unidade é a skill relevante de
  quem trabalhou, `02` §8; o teto aplica `MIN(qualidade, teto)` na leitura, o estoque guarda a média sem corte).
- **Estoque máximo** = 500 unidades × estrela, somando todos os produtos da empresa.
- **Limite de funcionários**: continua **sem limite** (o `02` §14 só diz "pode influenciar"; lacuna 7 abaixo).

### 2.4. Rastreabilidade
- Cada melhoria grava um registro imutável (empresa, de/para, custo, instante, executor, chave idempotente, `Explained`),
  como o aporte de capital e a fundação.
- `audit_companies` confere: estrela = 1 + nº de melhorias; cada melhoria tem lançamento correspondente; soma dos custos igual
  ao total debitado.
- O recorde para `14` §14.4.2 é a maior estrela da empresa (estrelas não diminuem, §3 item 2).

## 3. Lacunas reais (precisam de decisão do GD antes de implementar)

1. **Destino e natureza do pagamento da melhoria.** A lista de naturezas do `24` é fechada e não tem "melhoria de empresa".
   Proposta: pagar à conta federal (`UNION`), como a fundação, com a natureza `COMPANY_FOUNDING` e categoria `company_upgrade`
   (sem mudar o `24`), **ou** criar uma natureza própria (mudança do `24`). Nenhuma outra conta recebe o dinheiro (sem NPC).
2. **Estrelas podem diminuir?** O `14` fala em "maior nível já alcançado", o que sugere que poderiam cair; o `02` não prevê
   perda. Proposta: **nunca diminuem** nesta fase.
3. **Custo: múltiplos do custo de fundação** (tabela 2.2) é aceitável como valor inicial `[PROV]`, ou o GD prefere outra base?
4. **Faixa máxima: 5★** (alinhada ao catálogo) é aceitável?
5. **Teto de qualidade por estrela** (depende da escala de qualidade do `02` §18/`22`).
6. **Estoque máximo por estrela** (unidades de estoque por tipo de empresa).
7. **Limite de funcionários por estrela** (o `02` §14 apenas diz "pode influenciar").
8. **Estrela mínima da Matriz** (`GAP_MATRIZ_STARS_UNDEFINED`, já registrada; hoje `catalog` usa 1★ `[PROV]` uniforme).

> Os itens 1–4 bloqueiam a **ação de melhoria**. Os itens 5–8 não bloqueiam a ação em si, mas bloqueiam os limites de P1.04c–e;
> pela regra "dependência muda a ordem, não o compromisso", seguem como valores `[PROV]` calibráveis assim que o GD confirmar
> a forma da tabela (linear por estrela, parametrizada em `companies/params.py`, auditável).

## 4. Impacto na execução

- **P1.04b (cargos/mural/salários)** não depende de estrelas.
- **P1.04c–e** consomem a estrela como parâmetro: com 1★ para todos, só receitas de `min_stars = 1` ficam disponíveis até a
  progressão existir. A progressão é a **fatia P1.04f** (ação "Melhorar empresa", registro imutável, auditoria), implementada
  assim que os itens 1–4 estiverem decididos.
