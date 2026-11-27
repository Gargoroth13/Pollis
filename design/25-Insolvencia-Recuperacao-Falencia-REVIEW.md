# 25 — Insolvência, Recuperação e Falência Empresarial

**Status: REVIEW.** Decisões estruturais e explicitamente aprovadas pelo Game Director em 2026-11-27 são **vinculantes**; os detalhes de execução listados no §25.8 ainda precisam de decisão. Não é autorização de implementação ou merge de código. Complementa 02, 24, 18, 10, 17, 14, 12 e 21.

## 25.1. Capacidade administrativa
Não há limite rígido de funcionários por estrela. A capacidade administrativa ideal C é 10/20/40/80/160 para 1–5 estrelas [PROV]. Para N funcionários, eficiência E = min(1, sqrt(C/N)); N=0 implica E=1. Curva e valores calibráveis no Bot Test. Retornos decrescentes afetam produtividade, nunca reduzem remuneração contratada. Preservar teto de qualidade, estoque, limites específicos de suporte e requisitos de receitas. Aplicar consequências equivalentes a Varejo e Construtora; especificar integração por atividade e contagem de funcionários antes de implementar, evitando multiplicação duplicada de fatores. Retornar Explained conforme 20.

## 25.2. Estados e relógio
- Regular: sem obrigações vencidas.
- Inadimplente: obrigação vencida não quitada; impedir novas contratações, melhorias, **troca efetiva de produção** (escolher de novo o mesmo produto continua sem efeito nem cobrança) e retiradas/distribuição de lucros desde o início.
- Insolvente: após 3 dias de inadimplência persistente, suspender produção e atividades que geram novas obrigações salariais; permitir venda legítima de estoque, recebimentos, aportes e quitação.
- Após 7 dias: fase de recuperação financeira, com oportunidade de aporte e pagamento.
- Após 30 dias de inadimplência persistente: decretar falência e iniciar liquidação. Prazos em tempo do jogo, calibráveis [PROV].
A referência temporal é a obrigação vencida mais antiga ainda não quitada; pagamento parcial não reinicia seu prazo. Auditar tentativas de rolagem de dívida e definir continuidade do episódio para impedir reinício artificial por substituição de obrigações. **Obrigação vencida** (GD, 2026-11-27): aquela cujo prazo de pagamento chegou e que não foi integralmente quitada. Salários devidos pelo Trabalho e não pagos por insuficiência de caixa são imediatamente vencidos. Para contratos e empréstimos vale o vencimento contratual. Obrigações futuras não caracterizam inadimplência.
Quitação integral das vencidas antes da decretação restaura operação regular. Não permitir recuperação fictícia por emissão de dinheiro.

## 25.3. Proteções financeiras
Na contratação, conferir capacidade de pagar pelo menos um dia de remuneração potencial da equipe inteira, incluindo o novo contratado; não exige congelamento de saldo. Especificar cálculo determinístico conforme limites diários e contratos, sob travas que evitem contratação concorrente usando o mesmo saldo. Salários pendentes são permitidos, sujeitos às restrições acima. Bloquear retiradas e transferências de benefício próprio (inclusive aportes a outras empresas) durante inadimplência; remuneração do dono subordinada às dívidas vencidas. Operações entre partes relacionadas auditáveis, incluindo venda de estoque por valor irrisório; definir proteção efetiva contra esvaziamento patrimonial antes da implementação. Situação financeira e salários atrasados públicos, sem divulgar informação privada desnecessária.
A **distribuição de lucros** (`02`, complemento de 2026-11-27) só é permitida a empresa regular e preserva sete dias de folha potencial [PROV]; usa o **mesmo cálculo determinístico de folha potencial** especificado para esta checagem (§25.8).

## 25.4. Responsabilidade e pagamentos
Responsabilidade limitada: patrimônio pessoal não é automaticamente confiscado para pagar dívidas da empresa. Aportes voluntários permitidos. Recursos recebidos pela empresa inadimplente são destinados automaticamente às obrigações vencidas na ordem: salários, impostos, obrigações contratuais, empréstimos; dentro de cada categoria, mais antigas primeiro. Definir desempate, classificação sem dupla contagem, retenções e interação com reservas existentes no 24 antes da implementação. **Ordem por estado (GD, 2026-11-27):** em operação regular, as obrigações exigíveis são pagas em ordem cronológica (`24` §24.9); durante inadimplência, insolvência e liquidação aplicam-se as prioridades por categoria acima, e dentro de cada categoria as mais antigas primeiro.
Preservar atomicidade, idempotência, conservação monetária e trilha auditável.

## 25.5. Falência e liquidação
Na decretação, desligar funcionários, encerrar operações e encaminhar contratos ativos ao processo de encerramento contratual. Liquidar estoques e imóveis da empresa; distribuir recursos conforme prioridade acima; devolver eventual saldo remanescente ao proprietário. Não destruir bens, apagar lançamentos ou criar moeda. Após liquidação, registrar perdas dos credores e encerrar contabilmente obrigações remanescentes de modo auditável; empresa arquivada, sem operar. Histórico público permanente. Integrar ao Histórico do Mundo conforme 12, preservando os critérios de notícia daquele documento.

## 25.6. Cooldown e transferência
Proibir fundação de novas empresas pelo proprietário durante insolvência e liquidação. Após conclusão da falência, cooldown de 30 dias de jogo [PROV], independente da duração da liquidação. Cada empresa falida acrescenta 30 dias de cooldown [PROV]; esta decisão substitui a regra anterior de não acumular. O saldo de cooldown não diminui enquanto houver liquidação pendente de empresa atribuída ao proprietário; nova falência acrescenta 30 dias ao saldo restante, uma única vez por empresa. Outras empresas saudáveis já existentes podem operar; trabalhar e estudar continuam permitidos. Não impor perda artificial de skills ou QoL.
Proibir transferência voluntária de propriedade de empresa inadimplente (inclui insolvência e liquidação). Histórico público de proprietários; transferências anteriores à inadimplência auditáveis para identificar evasão de responsabilidade e cooldown. Se o episódio de inadimplência que culmina em falência começar dentro de 30 dias de jogo [PROV] após uma transferência, o proprietário anterior também recebe o cooldown daquela falência, mesmo que a decretação ocorra depois da janela. A responsabilidade anterior limita-se ao cooldown, sem confisco pessoal. Exigir transparência patrimonial, dívidas e histórico financeiro antes da transferência. Aplicar quando a transferência empresarial existir; não inventar sistema de transferência neste PR.

## 25.7. Decisões F1–F10 — aprovadas pelo GD em 2026-11-27
- F1/F2: liquidação em até 30 dias de jogo [PROV], por leilões públicos. Preços mínimos de 100%, 75% e 50% do valor de referência nos dias 1–10, 11–20 e 21–30, respectivamente [PROV]. Referência de mercado quando disponível; senão preço-base do catálogo ou avaliação parametrizada do imóvel. O proprietário não escolhe compradores, preços nem pode cancelar a liquidação. Encerrar antecipadamente se todos os ativos forem liquidados e as contas encerradas.
- F3: ao fim do prazo, terrenos e imóveis não vendidos passam ao Município; matérias-primas, produtos e equipamentos ao estoque da União, sem compensação à empresa falida. Podem ser leiloados posteriormente pelo poder público. Dinheiro destinado aos credores. Não criar moeda nem destruir bens.
- F4: antigo proprietário e suas outras empresas não podem comprar diretamente ativos nos leilões da própria empresa falida.
- F5/F6: cooldown acumulável por empresa e janela de responsabilidade do proprietário anterior conforme §25.6.
- F7: reservas legítimas anteriores à inadimplência são respeitadas enquanto a obrigação correspondente estiver válida.
- F8: impedir novas reservas discricionárias durante inadimplência.
- F9: saldo disponível, novas receitas livres e reservas liberadas entram automaticamente na fila de pagamento da §25.4. Contratos anteriores seguem suas regras de execução e encerramento; evitar dupla contagem de imposto retido e obrigação salarial. Operações atômicas, idempotentes e auditáveis pelo Ledger.
- F10: após a liquidação, encerrar dívidas remanescentes contabilmente, registrar perdas dos credores e preservar histórico público da falência. Não apagar lançamentos.

## 25.8. Pendências de execução
- Especificar lotes de leilão, avaliação, fechamento no prazo, transferência de custódia pública e tratamento de ativos onerados, respeitando F1–F4.
- Definição operacional da fase de recuperação e dos episódios de inadimplência, evitando rolagem estratégica; vencimento das diversas obrigações.
- Integração das prioridades com retenções, reservas, impostos, contratos e obrigações existentes no ledger; tratamento de perdas e de credores.
- Contagem de funcionários, cálculo da folha potencial, aplicação da eficiência nas atividades e parâmetros por tipo de empresa.
- Detalhar proteção contra venda simulada, esvaziamento patrimonial e compradores indiretos; aplicar a janela objetiva F6 sem inventar punições adicionais.
- Especificar idempotência do cooldown acumulado e regras de liquidação de contratos e bens sujeitos a ônus.

### Impactos no Ledger verificados (2026-11-27) — nada foi alterado no código nem nas regras monetárias
1. **Obrigação vencida × `Obligation`:** compatível. O `24` §24.9 já define obrigação pendente como dívida **vencida** não paga; salário do Trabalho sem caixa já nasce pendente na hora. Obrigações futuras (contrato, empréstimo) não existem no Ledger enquanto não vencem: o sistema de origem só cria a obrigação ao vencer, com `competence_day` = dia do vencimento (e não o da criação), pois o relógio de inadimplência (25.2) parte da vencida mais antiga.
2. **Categorias de prioridade:** `Obligation` tem `nature` mas não categoria. É preciso o mapeamento `nature` → categoria (salários: `WAGE`, `OWNER_SALARY`, `MILITARY_PAY`, `POLITICAL_SALARY`; impostos; contratuais; empréstimos: `LOAN_*`) e decidir onde ficam as naturezas hoje sem categoria. O imposto retido da remuneração viaja dentro da obrigação salarial (`tax_rate`, `tax_paid`): não duplicar como obrigação tributária (F9).
3. **Ordem dependente do estado:** `settle_obligations(debtor)` hoje só conhece "competência, depois id" (R4). Para ordem por categoria em inadimplência o chamador (Empresas) precisa informar o modo, ou o Ledger consultar o estado por um provedor registrado; o Ledger não deve conhecer o estado financeiro da empresa.
4. **Incompatibilidade a reconciliar:** o `24` §24.9 diz que aluguel/parcelas de contrato **não** criam obrigação (têm consequência própria, `18` §18.6, `10` §11), mas o 25.4 coloca "obrigações contratuais" e empréstimos na fila de pagamento. Falta decidir se o vencido de contrato/empréstimo passa a gerar `Obligation` (altera o 24) ou se a fila do 25 consulta uma segunda fonte. **Não decidido aqui.**
5. **Regra de fila do PR #37 (A-04):** em operação regular é exatamente "cronológica por competência" e é compatível. Em inadimplência ela precisará deixar de contar obrigações mais antigas de categoria inferior (um salário novo passa à frente de dívida contratual mais antiga).
6. **Naturezas:** a lista do `24` §24.8 é fechada; categorias novas ou naturezas de perdas de credores (F10) exigem emenda explícita.

Não decidir silenciosamente esses itens. Apresentar propostas ao GD antes de implementar as partes afetadas.

## 25.9. Critérios de aceitação
Testar limites temporais, pagamento parcial e integral, contratação concorrente, acumulação de salários, retiradas disfarçadas, recuperação, prioridade e conservação de dinheiro e bens, falência idempotente, prazo e conclusão da liquidação, cooldown e transferência. Testar integração com produção, estoque, imóveis, mercado, contratos, rankings, histórico, ticks e Action Registry compartilhado por humanos e bots. Medir concentração de emprego, produtividade, dívidas, recuperação e falências no Bot Test. Não criar NPCs econômicos, atalhos para bots ou reputação artificial.
