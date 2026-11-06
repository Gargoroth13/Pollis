"""
Parâmetros dos Rankings. Origem de cada valor:
  DESIGN   número que o design/14 fixa (decisão consolidada §14.12): não é ajustável por conta própria.
  [PROV]   valor técnico de apresentação, SEM efeito de jogo: pode ser calibrado sem decisão de design.
"""
from core.timeline import SECONDS_PER_HOUR

PRODUCTION_WINDOW_DAYS = 14                  # DESIGN 14.3.3 / 14.12-1
TAXPAYER_WINDOW_DAYS = 30                    # DESIGN 14.3.7 / 14.12-2
STREAK_MAX_GAP_SECONDS = 72 * SECONDS_PER_HOUR   # DESIGN 14.3.11 / 14.12-6: o intervalo precisa ser INFERIOR a isto

PAGE_SIZE = 20                               # [PROV] linhas por ranking na página
MAX_PAGE_SIZE = 100                          # [PROV] teto de linhas pedidas a uma consulta
DAILY_TICK_PRIORITY = 90                     # [PROV] ordem da varredura diária entre os handlers do tick DAILY do mundo

# Snapshots de QoL (14.3.4; decisão do GD, 2026-11-03)
QOL_SNAPSHOT_INTERVAL_SECONDS = 3600         # GD: frequência inicial de 1 hora, parametrizada (múltiplo do ciclo de 10 min)
QOL_SNAPSHOT_RETAIN_COMPLETE = 24            # GD: reter as últimas 24 snapshots COMPLETAS
QOL_SWEEP_BATCH = 200                        # [PROV] jogadores por lote da varredura (cada jogador em transação própria)
QOL_TICK_PRIORITY = 95                       # [PROV] ordem do handler entre os do tick de 10 minutos do mundo

# Outbox de atividade (14.3.11; decisão do GD, 2026-11-04)
ACTIVITY_INLINE_PROCESSING = True            # [PROV] passada do jogador via on_commit: SÍNCRONA, no mesmo fluxo, logo após o commit (não é worker); a durabilidade não depende dela; padrão mantido até medir no Bot Test
ACTIVITY_OUTBOX_PLAYER_BATCH = 200           # [PROV] eventos por jogador numa passada
ACTIVITY_OUTBOX_MAX_PLAYERS = 500            # [PROV] jogadores por passada do worker (falhas contam; o escalonamento justo evita starvation)
ACTIVITY_OUTBOX_TICK_PRIORITY = 92           # [PROV] ordem do handler entre os do tick de 10 minutos do mundo
ACTIVITY_OUTBOX_OVERDUE_SECONDS = 3600     # [PROV] evento pendente há mais que isto vira achado de auditoria (tick de 10 min deveria tê-lo drenado)
