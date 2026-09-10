# CLAUDE.md — Polis

## O que é
Jogo de simulação política/econômica text-based multiplayer, em Django.
Jogadores fundam empresas, trabalham, sobem de skill, participam da
economia e (em fases futuras) da política. Design completo em `design/`.

## Stack e arquitetura
- Django + SQLite (dev) / Postgres (produção)
- Apps: `accounts` (Usuario, Perfil, ItemDoJogador), `geography`
  (Estado/Cidade/Bairro — será expandido com Lotes), `skills` (3 skills
  fixas: Inteligência/Físico/Carisma), `empresas` (Empresa, Cargo,
  Produto/Receita/Estoque, EspecializacaoDoFuncionario), `financeira`
  (Poupança, Empréstimo, CartãoDeCrédito), `core` (trabalho freelance)
- Setup local: venv → `pip install -r requirements.txt` → `python manage.py
  migrate` → `seed_geography` → `seed_produtos`

## Convenções
- Nomenclatura do código em português (models, campos, mensagens)
- Recursos que mudam com o tempo (energia, saúde, nutrição, QoL, juros)
  usam o padrão "sincronizar() sob demanda": guarda timestamp da última
  sincronização, calcula quantos ciclos passaram, aplica de uma vez.
  Nunca usar cron/worker externo.
- Preço/efeito de produto pode variar pela estrela de quem vende
  (`preco_com_qualidade` em `empresas/models.py`)

## Regras de desenvolvimento
- Tasks pequenas, independentes, verificáveis — nunca agrupar features de
  uma fase inteira numa task só
- Não implementar sistema que a task não pediu, mesmo que pareça
  relacionado
- Se uma task esbarrar numa dependência que não existe, registrar o
  bloqueio em `TASK.md` e parar — não expandir escopo sozinho
- `design/` é a fonte de verdade do design — ler só o arquivo relevante
  pra cada task, não o diretório inteiro
- Um agente implementa a task em Current (`TASK.md` + `TASK_QUEUE.md`).
  Não trabalhar em paralelo na mesma task. Revisar o trabalho de outro
  agente é permitido; sobrescrever não.

## Testes
- Toda mudança de comportamento precisa de teste real via Django test
  Client antes de considerar a task concluída — "parece certo" não é
  suficiente
- Preferir TestCase persistente em `*/tests.py` do app. Não commitar
  `smoke_test.py` (nem outro script solto) na raiz

## Git
- Puxar o repositório (clone ou pull) antes de editar
- **Sempre checar `TASK.md` e `TASK_QUEUE.md` primeiro** — pode haver
  outra sessão/agente trabalhando no mesmo repositório
- Um commit por task concluída — nunca misturar tasks diferentes
- Revisar `git status --short` e o diff antes de commitar
- Push só depois de testado
- Nunca commitar segredo (token/senha), nunca force-push

## Onde encontrar o quê
- Task atual, escopo e critério de conclusão → `TASK.md`
- Fila ordenada de tasks (próximas / futuras / bloqueadas) → `TASK_QUEUE.md`
- Histórico de decisões técnicas relevantes → `CHANGELOG_DEV.md`
- Regras e números do design do jogo → `design/`
