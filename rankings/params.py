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
