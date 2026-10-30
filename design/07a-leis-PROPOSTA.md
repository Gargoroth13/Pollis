# 07a — Leis: lacunas técnicas e interpretações da P1.10a (PROPOSTA)

**Status:** PROPOSTA — documento de apoio ao `07 — Leis` (FINAL — BOT TEST). Nada aqui altera o fluxo legislativo definido no `07`; cada linha é uma
lacuna **técnica** onde o design é silencioso ou ambíguo, a escolha feita para não bloquear o desenvolvimento e o que o GD pode revisar. Nenhuma é
bloqueante. Valores numéricos sem fonte estão em `legislation/params.py::parameter_table()` (`DESIGN` ou `PROV`).

## 1. O que a P1.10a entrega (app `legislation`, migração `0001`)
Propostas (criar, editar com versões, retirar), discussão de 3 dias, janela semanal da segunda-feira 00:00, votação da Câmara com composição congelada
e voto nominal alterável, maioria absoluta das cadeiras ocupadas, sanção (3 dias; inação = sanção automática), veto com justificativa, derrubada por
2/3, vigor no próximo `weekly tick`, conflito por escopo (grupos acoplados), cooldown de reapresentação, revogação por proposta, mudança de Presidente e
interregno (07 §07.18-§07.19), sugestões de Governador/Prefeito, preview (efeitos diretos × estimativas × validações), consultas públicas, histórico
imutável, auditoria (`audit_legislation`) e nove ações no Action Registry (mesmo caminho para bots e jogadores).

**Fora desta etapa (dependências):** quem ocupa Presidente/Deputado/Governador/Prefeito e a composição da Câmara (`06`, P1.11: entram por provedor,
como `budget.authority`; sem provedor ninguém propõe e os prazos ficam suspensos); o **catálogo concreto de leis** e seus limites (`11`, REVIEW, P1.12: o motor
só conhece leis REGISTRADAS por `catalog.register_law`; sem lei registrada nada é proposto); efeitos das leis nos demais sistemas (cada consumidor lê
`laws.value(chave, parâmetro)`; esta etapa não liga nenhum); pisos constitucionais com valores (L5).

## 2. Lacunas e interpretações

| # | Ponto | O que o design diz | Escolha técnica | Revisão |
|---|---|---|---|---|
| L1 | "3 dias de calendário" de discussão | 07.5 e 07.6: a proposta enviada na **sexta** entra na votação da segunda; enviada depois do limite espera | Dias **civis do calendário do jogo, contando o dia da criação**: a discussão termina às 00:00 do 4º dia (sexta, qualquer hora → segunda 00:00; sábado → terça, espera a janela seguinte). Com 72 h exatas o exemplo da sexta seria impossível. Votação e sanção usam 72 h exatas (começam à meia-noite, terminam à meia-noite) | confirmar |
| L2 | Cooldown de reapresentação (07.11) | "valores exatos são parâmetros técnicos" | `[PROV]` 7 dias (igual) e 3 dias (com alteração real de algum X, comparado à proposta rejeitada). Só **rejeição** gera cooldown; veto mantido não (o design só cita a rejeitada) | valor `[PROV]` |
| L3 | Instante da composição e do Presidente | 07.7: composição congelada ao iniciar a votação | Os prazos usam o instante LÓGICO (o prazo registrado), a composição/Presidente vêm do provedor no processamento (tick de 10 minutos). Ação do jogador depois do prazo é recusada mesmo que o motor ainda não tenha processado (o prazo é a verdade) | técnica |
| L4 | Janela da votação de derrubada (07.15) | "segue a mesma janela legislativa de 3 dias" | Abre na **primeira segunda-feira depois do veto**, dura 3 dias; derrubado → entra em vigor no `weekly tick` seguinte ao fim; composição congelada na abertura da derrubada | confirmar |
| L5 | Pisos constitucionais (07.23) | "definidos pelo sistema inicial" (moradia, educação), sem valores | Gancho `register_constitutional_floor(lei, parâmetro, piso)`; **nenhum piso registrado**; proposta abaixo do piso → `BELOW_CONSTITUTIONAL_FLOOR` | GD define valores |
| L6 | Catálogo de leis | `11` em REVIEW | O motor não traz leis; sistemas/P1.12 registram `LawSpec` (parâmetros X com mínimo/máximo/padrão, grupo acoplado, validadores) | P1.12 |
| L7 | Sanção sem Presidente (vago) | 07.12 dá 3 dias ao Presidente | O prazo só passa a correr quando houver Presidente; sem ele não há sanção automática | técnica |
| L8 | Deputado que perde a cadeira durante a votação | composição congelada (07.7) | Não pode mais votar (`NOT_A_DEPUTY`); o voto já registrado continua valendo; quem assumiu depois não vota nesta votação | técnica |
| L9 | Autor que deixou o cargo | 07.20: a proposta continua; histórico preserva o autor | Continua podendo editar/retirar na discussão (o design não retira o direito) | revisar se indesejável |
| L10 | Reabertura da votação (mudança de Presidente ou interregno) | 07.18-07.19: "nova votação de 3 dias" / "três dias completos quando a nova Câmara estiver constituída" | Abre **imediatamente** (não espera a segunda-feira), 72 h exatas; a votação anterior fica anulada no histórico, nada é aproveitado | técnica |
| L11 | Proposta sem mudança real | 07.21 | Valor igual ao vigente → `NO_CHANGE`; a proposta traz o conjunto COMPLETO de parâmetros X da lei; revogação devolve ao padrão do catálogo | técnica |
| L12 | Validações de coerência (07.24) | exibidas no preview | Rodam na criação e na edição (e aparecem no preview); não são reexecutadas na entrada em vigor (o grupo acoplado impede outra proposta no meio) | técnica |
| L13 | Energia das ações políticas | `04`/`06` | Custo `()` (sem custo) até o `06` definir | `06` |
| L14 | Sugestões de Governador/Prefeito (07.3) | só enviam sugestões ao Presidente | Entidade `Suggestion`; o Presidente formaliza (vira o autor, todas as regras de proposta valem) ou descarta | técnica |

## 3. Processo (resumo do motor)
Cada proposta ativa guarda o próximo instante de ação (`deadline_at`); `process.advance(at)` aplica, em ordem de instante, tudo que venceu:
`DISCUSSION → (segunda 00:00) VOTING → (fim) SANCTION | REJECTED`; `SANCTION → sanção/veto | sanção automática → AWAITING_FORCE`;
`VETOED → (segunda) OVERRIDE_VOTING → AWAITING_FORCE | VETO_SUSTAINED`; `AWAITING_FORCE → (weekly tick) ENACTED` (cria/atualiza `Law`, grava `LawChange`).
Registrado como handler do tick `TEN_MINUTES` do mundo; idempotente.

## 4. Limites conhecidos da prova
- A restrição única parcial por escopo e as travas das propostas são as defesas; os testes de corrida (sanção × veto, sanção × sanção automática, escopo) são PG-only
  (`CROSS_ROW`). A remoção da trava da proposta em `voting._lock` **é** detectada (3 de 3 execuções em PG); a ausência de uma trava continua só parcialmente detectável por temporização.
- Sem os provedores reais de cargo (P1.11) o processo é testado com um provedor falso; o cenário do Bot Test precisa dos ocupantes (K1).
