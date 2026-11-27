# 25 — Insolvência, Recuperação e Falência Empresarial

**Status: REVIEW — BOT TEST.** Decisões estruturais aprovadas pelo Game Director em 2026-11-27; detalhes de execução listados ao final ainda precisam de decisão. Não é autorização de implementação ou merge de código. Complementa 02, 24, 18, 10, 17, 14, 12 e 21.

## 25.1. Capacidade administrativa
Não há limite rígido de funcionários por estrela. A capacidade administrativa ideal C é 10/20/40/80/160 para 1–5 estrelas [PROV]. Para N funcionários, eficiência E = min(1, sqrt(C/N)); N=0 implica E=1. Curva e valores calibráveis no Bot Test. Retornos decrescentes afetam produtividade, nunca reduzem remuneração contratada. Preservar teto de qualidade, estoque, limites específicos de suporte e requisitos de receitas. Aplicar consequências equivalentes a Varejo e Construtora; especificar integração por atividade e contagem de funcionários antes de implementar, evitando multiplicação duplicada de fatores. Retornar Explained conforme 20.

## 25.2. Estados e relógio
- Regular: sem obrigações vencidas.
- Inadimplente: obrigação vencida não quitada; impedir novas contratações, melhorias e retiradas/distribuição de lucros desde o início.
- Insolvente: após 3 dias de inadimplência persistente, suspender produção e atividades que geram novas obrigações salariais; permitir venda legítima de estoque, recebimentos, aportes e quitação.
- Após 7 dias: fase de recuperação financeira, com oportunidade de aporte e pagamento.
- Após 30 dias de inadimplência persistente: decretar falência e iniciar liquidação. Prazos em tempo do jogo, calibráveis [PROV].
A referência temporal é a obrigação vencida mais antiga ainda não quitada; pagamento parcial não reinicia seu prazo. Auditar tentativas de rolagem de dívida e definir continuidade do episódio para impedir reinício artificial por substituição de obrigações. Quitação integral das vencidas antes da decretação restaura operação regular. Não permitir recuperação fictícia por emissão de dinheiro.

## 25.3. Proteções financeiras
Na contratação, conferir capacidade de pagar pelo menos um dia de remuneração potencial da equipe inteira, incluindo o novo contratado; não exige congelamento de saldo. Especificar cálculo determinístico conforme limites diários e contratos, sob travas que evitem contratação concorrente usando o mesmo saldo. Salários pendentes são permitidos, sujeitos às restrições acima. Bloquear retiradas e transferências de benefício próprio (inclusive aportes a outras empresas) durante inadimplência; remuneração do dono subordinada às dívidas vencidas. Operações entre partes relacionadas auditáveis, incluindo venda de estoque por valor irrisório; definir proteção efetiva contra esvaziamento patrimonial antes da implementação. Situação financeira e salários atrasados públicos, sem divulgar informação privada desnecessária.

## 25.4. Responsabilidade e pagamentos
Responsabilidade limitada: patrimônio pessoal não é automaticamente confiscado para pagar dívidas da empresa. Aportes voluntários permitidos. Recursos recebidos pela empresa inadimplente são destinados automaticamente às obrigações vencidas na ordem: salários, impostos, obrigações contratuais, empréstimos; dentro de cada categoria, mais antigas primeiro. Definir desempate, classificação sem dupla contagem, retenções e interação com reservas existentes no 24 antes da implementação. Preservar atomicidade, idempotência, conservação monetária e trilha auditável.

## 25.5. Falência e liquidação
Na decretação, desligar funcionários, encerrar operações e encaminhar contratos ativos ao processo de encerramento contratual. Liquidar estoques e imóveis da empresa; distribuir recursos conforme prioridade acima; devolver eventual saldo remanescente ao proprietário. Não destruir bens, apagar lançamentos ou criar moeda. Após liquidação, registrar perdas dos credores e encerrar contabilmente obrigações remanescentes de modo auditável; empresa arquivada, sem operar. Histórico público permanente. Integrar ao Histórico do Mundo conforme 12, preservando os critérios de notícia daquele documento.

## 25.6. Cooldown e transferência
Proibir fundação de novas empresas pelo proprietário durante insolvência e liquidação. Após conclusão da falência, cooldown de 30 dias de jogo [PROV], independente da duração da liquidação. Sem escalada por reincidência inicialmente. Outras empresas saudáveis já existentes podem operar; trabalhar e estudar continuam permitidos. Não impor perda artificial de skills ou QoL.
Proibir transferência voluntária de propriedade de empresa inadimplente (inclui insolvência e liquidação). Histórico público de proprietários; transferências anteriores à inadimplência auditáveis para identificar evasão de responsabilidade e cooldown. Aplicar quando a transferência empresarial existir; não inventar sistema de transferência neste PR.

## 25.7. Pendências de design/execução
- Prazo máximo de liquidação, mecanismo de venda, preço e destino de ativos não vendidos; não manter jogador bloqueado indefinidamente.
- Definição operacional da fase de recuperação e dos episódios de inadimplência, evitando rolagem estratégica; vencimento das diversas obrigações.
- Integração das prioridades com retenções, reservas, impostos, contratos e obrigações existentes no ledger; tratamento de perdas e de credores.
- Contagem de funcionários, cálculo da folha potencial, aplicação da eficiência nas atividades e parâmetros por tipo de empresa.
- Proteção contra venda simulada, esvaziamento patrimonial e transferência prévia fraudulenta; eventual responsabilidade/cooldown de proprietários anteriores exige aprovação explícita.
- Destino do cooldown quando houver falências sobrepostas e regras de liquidação de contratos e bens sujeitos a ônus.
Não decidir silenciosamente esses itens. Apresentar propostas ao GD antes de implementar as partes afetadas.

## 25.8. Critérios de aceitação
Testar limites temporais, pagamento parcial e integral, contratação concorrente, acumulação de salários, retiradas disfarçadas, recuperação, prioridade e conservação de dinheiro e bens, falência idempotente, prazo e conclusão da liquidação, cooldown e transferência. Testar integração com produção, estoque, imóveis, mercado, contratos, rankings, histórico, ticks e Action Registry compartilhado por humanos e bots. Medir concentração de emprego, produtividade, dívidas, recuperação e falências no Bot Test. Não criar NPCs econômicos, atalhos para bots ou reputação artificial.
