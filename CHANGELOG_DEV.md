# CHANGELOG_DEV.md

Registro breve de mudanças e decisões de desenvolvimento relevantes pro
futuro. Não é histórico completo — pra isso, ver o log do Git e `design/`.

## 2026-09-08 — Fundação do projeto até Fase 4b

- MVP inicial: cadastro, bairro sorteado por faixa de renda, energia com
  regeneração sob demanda, trabalho freelance
- Fase 1: skills viraram 3 stats fixos (Inteligência/Físico/Carisma) em
  vez de 8 categorias; empresa passou a se classificar por terreno
  (Matriz) ou tipo de indústria (Industrial) em vez de setor
- Fase 2: catálogo de produtos completo (67 produtos, 82 receitas),
  compra Industrial→Industrial, estrela mínima por receita, consumo
  operacional (EPI/Uniforme)
- Fase 3: inventário do jogador, QoL pessoal (distinta da QoL do
  bairro), Saúde com decaimento ligado a QoL, Nutrição, internação
  automática, produção via qualquer funcionário (não só dono)
- Fase 4a: preço de venda varia pela estrela do vendedor;
  especialização de funcionário por produto
- Fase 4b: app `financeira` completo — poupança com juros semanais,
  empréstimo, cartão de crédito com juros mensais, transferência entre
  jogadores, reserva obrigatória de 20%, rating de solvência público,
  falência
- Decisão: bolsa de valores e intervenção do governo na falência
  ficaram de fora — dependem de sociedade com múltiplos donos e sistema
  de governo, ainda não implementados

## 2026-09-08 — Reorganização de documentação e workflow

- `DESIGN.md` (monólito de 1300+ linhas) fragmentado em `design/` por
  tema, pra evitar reescrever um arquivo gigante a cada mudança pequena
- Workflow reorganizado: `CLAUDE.md` (permanente), `TASK.md` (task
  atual), `CHANGELOG_DEV.md` (este arquivo) — o histórico da conversa
  deixa de ser necessário pra continuar o projeto
- Notas de teste do usuário incorporadas em `design/`: skill deixa de
  ser escolha livre do jogador (é definida pela atividade); fundar
  empresa passa a ter custo + vai exigir diploma de Administração
  Empresarial (diploma fica bloqueado até Escola existir); cargo "Dono"
  automático ao fundar; produção centralizada pelo dono; especialização
  de funcionário mais lenta; geografia vai ganhar Lotes e distância da
  capital; sistema de moradia (albergue → compra/aluguel, com dívida de
  aluguel não pago indo pro "Banco Central" — conceito ainda em aberto)
