# Polis

Simulação política, econômica e social multiplayer (jogadores reais + bots de teste),
em Django.

> **O código anterior ao Bot Test foi removido** (ver `CHANGELOG_DEV.md`, 2026-09-30) e
> está preservado no histórico do Git. O jogo está sendo reconstruído a partir de `design/`.

## Onde está cada coisa

| Arquivo | Função |
|---|---|
| `design/` | Regras do jogo (fonte de verdade de mecânicas) |
| `CLAUDE.md` | Regras permanentes de desenvolvimento |
| `TASK.md` | Tarefa atual |
| `TASK_QUEUE.md` | Fila priorizada |
| `CHANGELOG_DEV.md` | Decisões e conflitos registrados |

## Rodando localmente

Python 3.11+.

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # defina SECRET_KEY (obrigatória se DEBUG=False)
python manage.py migrate
python manage.py test
python manage.py runserver
```

Sem `DATABASE_URL`, usa SQLite. Em produção, PostgreSQL via `DATABASE_URL`.

## Tempo do mundo

O relógio de jogo é do app `core`. Padrão: 1 dia de jogo = 600 s reais.

```bash
python manage.py world_clock show
python manage.py world_clock set-speed 600     # segundos reais por dia de jogo
python manage.py advance_world                 # processa ticks pendentes do mundo
python manage.py advance_world --loop --interval 5
```
