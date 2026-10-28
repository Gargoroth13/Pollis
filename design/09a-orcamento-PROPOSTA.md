# 09a — Orçamento Público: o que a P1.09a implementa e as lacunas encontradas (proposta)

> **Status:** PROPOSTA — o `09` está FINAL — BOT TEST e define a estrutura; este documento registra o que a primeira etapa (núcleo) implementa, as **lacunas**
> encontradas e a **menor solução técnica** usada em cada uma (CLAUDE.md §13). Valores ausentes estão `[PROV]` em `budget/params.py`
> (`provisional_table()`). Nenhuma mecânica nova foi criada; nada aqui altera o `09`, o `11` ou o `24`.

## 1. Etapas da P1.09

| Etapa | Conteúdo | Estado |
|---|---|---|
| **P1.09a** | Núcleo: contas e visão fiscal públicas, classificação de receita/despesa, teto de déficit (`24` §24.16), repasses União→Estado→Município, plano orçamentário municipal com pisos, decisões registradas e públicas, auditoria, ações no Action Registry | implementada (este PR) |
| **P1.09b** | Projetos/obras públicas e contratos com Construtoras; handler governamental do motor de `18` (P1.08c); dotação por área consumida por quem gasta | pendente (depende de P1.08c; `budget.plans.area_headroom` já existe como ponto de consulta) |
| **P1.09c** | Dívida pública (títulos, juros, resgate), níveis de bloqueio fiscal | pendente (`public_debt: None` na visão fiscal; `None ≠ 0`) |
| **P1.09d** | Subsídios, campanhas | pendente |

## 2. O que a P1.09a entrega (app `budget`)

- **Visão fiscal pública** (`fiscal.fiscal_view`, `09` §33): saldo, comprometido (reservas, `09` §10), disponível, obrigações pendentes, receitas e despesas do período de 30 dias e dos últimos 30 dias, por natureza e por categoria, teto de déficit. **Log financeiro público** (`fiscal.ledger_log`, `09` §34) com saldos antes/depois. Tudo é leitura do registro monetário; nada é guardado em tabela paralela.
- **Classificação** (`24` §24.16): entrou na conta = receita, saiu = despesa, exceto o que o `24` manda não contar (dotações do cenário, emissão de títulos, retenção; transferências a níveis inferiores, principal da dívida). Estorno cancela a classificação do original. As naturezas excluídas aparecem listadas em `excluded_*`.
- **Teto de déficit** (`fiscal.deficit_check`): janela de 360 dias (ou desde a abertura da conta, se menor), referência anualizada, mínimo de 30 dias de histórico para bloquear, `C_360` = pagamentos de HOJE até hoje+359; aritmética racional exata; devolve `Explained` e dados estruturados (`headroom`, `restricted_by`). Ainda **não é chamado por ninguém**: quem cria compromisso discricionário (P1.09b/c) o consulta.
- **Repasses** (`transfers`, ação `budget_transfer`): Presidente → Estado, Governador → Município do **seu** Estado (`09` §2-§4; sem pular nível nem voltar). Natureza `GOV_TRANSFER`, categoria `transfer`; dinheiro existente que troca de caixa. Sem fórmula de equalização (`09` §28, §30): o valor é decisão política, registrada em `GovernmentDecision` (só se acrescenta), pública, com a decomposição dos fundos.
- **Plano orçamentário municipal** (`plans`, ações `set_budget_plan`/`confirm_budget_plan`): o Prefeito distribui entre Educação, Saúde, Infraestrutura, Administração e Programas Sociais por período de 30 dias; a confirmação confere **pisos** (Educação, Saúde, Infraestrutura; `11` §11.2.1) sobre a **base de receitas dos últimos 30 dias**, a soma dos pisos ≤ 100% e o total ≤ disponível; devolve `Explained`; plano confirmado não muda. `area_headroom` = dotação restante da área (`None` = sem plano confirmado, nunca 0).
- **Auditoria** (`audit_budget`, `manage.py audit_budget [--json]`): 4 invariantes (repasse × decisão × lançamento; todo `GOV_TRANSFER` entre governos tem decisão e respeita a hierarquia; consistência do plano; pisos e disponível registrados).

## 3. Lacunas K1–K5 (decisão técnica provisória; nada vira regra permanente sem o GD)

| # | Lacuna | Solução técnica usada | Estado |
|---|---|---|---|
| **K1** | **Quem ocupa os cargos** (Presidente/Governador/Prefeito). O `09` diz quem age, mas os cargos pertencem a `06` (REVIEW) e à P1.11, que não existem. | Gancho técnico `authority.register_office_provider`: a P1.11 (e o cenário do Bot Test, `21`/`09` §37: bots já começam no cargo) registram o ocupante. **Sem provedor, ninguém age** (`NO_OFFICE_HOLDER`), nunca "qualquer um". Dois provedores que discordam falham (`OFFICE_CONFLICT`): o design não define precedência. | técnica; **bloqueia ligar o Bot Test**, não o desenvolvimento |
| **K2** | De onde contam os períodos de 30 dias (`09` §8 só diz "30 dias"). | Da **época do jogo** (`budget.periods`). | `[PROV]` |
| **K3** | O que o governo pode repassar: o `09` §11 manda priorizar obrigações já assumidas; o `24` §24.9 deixa a decisão à P1.09. | Só repassa o que sobra depois do **comprometido** e das **obrigações pendentes** (`TRANSFERS_RESPECT_PENDING_OBLIGATIONS`). | `[PROV]` |
| **K4** | O que é "linha do plano": o `09` não define se a dotação por área limita o gasto nem como se confirma. Pisos por lei: padrão 10% de `11` até existir o motor de leis (P1.12). | Linhas = dotações por área; soma ≤ disponível na confirmação; piso exigido = ⌈pct × receitas de 30 dias⌉ (arredondado para cima); a diferença é **reserva** (manter reserva é decisão política, `09` §32). Faixas do `11` registradas (5–30%/1–30%/1–30%). | `[PROV]` |
| **K5** | Horizonte do compromisso novo e **idade da conta**: a janela do teto conta desde a abertura da conta; abertura preguiçosa deslocaria a janela. | `C_360` = [hoje, hoje+359]; `ensure_accounts()` abre as contas de TODOS os governos na formação do mundo. A Federação não tem pisos (`09`/`11`); militar é só federal (`09` 45.8) e fica fora do plano municipal. | técnica |

Não implementado e **sem pedir decisão agora** (são das etapas seguintes): dívida pública, bloqueio fiscal por níveis, subsídios, campanhas, tributos (`24`/`11`), contratos governamentais.

## 4. Parâmetros

Ver `budget.params.provisional_table()`: ciclo de 30 dias (`GD`), âncora da época (`PROV`), janela 360/mín. 30 (`GD`), teto 10% (`PROV`, padrão do `11`), pisos 10/10/10 (`PROV`, padrão do `11`), repasse respeita pendências (`PROV`), naturezas fora de receita/despesa (`GD`, `24` §24.16).

## 5. Limites conhecidos da prova

- Concorrência: repasses simultâneos e confirmação repetida são provados em PG e SQLite; a ordem confirmação × edição do plano depende da trava da conta do Município e só é garantida em PostgreSQL (`CROSS_ROW`); remover a trava dos **repasses** não é detectado pelos testes, porque o registro monetário (saldo sob trava) e a unicidade das chaves são a primeira defesa — a trava do app serializa a foto de fundos gravada na decisão, não o saldo.
- Com ocupantes de cargo **falsos nos testes** (provedor de teste). A integração com os cargos reais é da P1.11.
