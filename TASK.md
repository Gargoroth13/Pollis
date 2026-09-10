# TASK.md — Tarefa atual

## Objetivo
Adicionar custo de fundação de empresa, variando por tipo. Hoje
`criar_empresa` não cobra nada do fundador.

## Contexto mínimo
Fundar empresa deve virar um objetivo de médio/fim de jogo, não algo
trivial pra iniciante (decisão registrada em `design/02-empresas.md`,
seção "Correções de hoje"). Custo por tipo já definido:

| Tipo | Custo |
|---|---|
| Varejo | R$ 15.000 |
| Serviços (Transporte/Publicidade/Lazer) | R$ 25.000 |
| Matriz | R$ 40.000 |
| Construtora | R$ 60.000 |
| Industrial | R$ 80.000 |
| Serviços, especialização Financeira | R$ 100.000 |

## Escopo desta task
- `empresas/models.py`: tabela de custo por tipo (com caso especial pra
  Financeira) + função `custo_de_fundacao(tipo, especializacao_servico)`
- `empresas/views.py`, view `criar_empresa`: validar que o fundador tem
  saldo suficiente antes de criar; descontar do `perfil.dinheiro` ao
  criar
- Template de criação de empresa: mostrar o custo antes de confirmar,
  se for simples — senão, deixar só na mensagem de erro/sucesso

## O que já foi feito
Nada commitado ainda. Uma sessão anterior chegou a rascunhar o
dicionário de custo localmente, mas não foi testado nem commitado —
esta task começa do zero, a partir do commit `4f0f07b` (HEAD de lógica;
docs de workflow depois disso não mexem em `criar_empresa`).

## O que falta
- [ ] Adicionar `CUSTO_DE_FUNDACAO_POR_TIPO` e `custo_de_fundacao()` em `empresas/models.py`
- [ ] Validar saldo e descontar em `criar_empresa`
- [ ] Testar: fundar com saldo insuficiente bloqueia; fundar com saldo
      suficiente desconta o valor certo por tipo (incluindo o caso
      especial da Financeira)
- [ ] Commit e push

## Restrições
- Não mexer em cargo "Dono" automático, produção centralizada, nem
  especialização de funcionário
- Não mexer em diploma de Administração Empresarial — depende de Escola,
  que ainda não existe
- Não implementar caixa da empresa nesta task (Task 002 da fila)

## Critérios de conclusão
- Custo descontado corretamente por tipo, testado via Django test Client
- `git status` limpo depois do commit (só arquivos desta task)

## Fila
Próximas tasks, bloqueios e a ordem recomendada (incluindo a inserção
de tesouraria da empresa **antes** do cargo Dono) estão em `TASK_QUEUE.md`.
Não iniciar a próxima enquanto esta não estiver commitada.
