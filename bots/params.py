"""
Parâmetros da infraestrutura do Bot Test. O design (21 §21.2-§21.4) fixa a população-alvo (~1.000) e a criação padrão (1 Bot por minuto, configurável),
o relógio acelerado (1 dia de jogo = 10 minutos reais) e que o intervalo entre avaliações é VARIÁVEL; não dá os intervalos: `[PROV]` em tabela auditável.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

DEFAULT_TARGET_POPULATION = 1000                   # 21 §21.2 ("aproximadamente")
DEFAULT_CREATION_INTERVAL_REAL_SECONDS = 60        # 21 §21.2: 1 Bot por minuto (tempo REAL), configurável
DEFAULT_MAX_CREATION_BURST = 10                    # [PROV] teto de criações numa única passada (recuperação após pausa do servidor)
EVAL_AFTER_ACTION_SECONDS = (600, 1800)            # [PROV] intervalo de jogo até a próxima avaliação depois de agir (10–30 min de jogo)
EVAL_IDLE_SECONDS = (1800, 7200)                   # [PROV] sem ação possível ou ação recusada (30 min–2 h de jogo)
EVAL_FIRST_SECONDS = (0, 3600)                     # [PROV] primeira avaliação, espalhada para os Bots não acordarem em bloco (21 §21.4)
BASELINE_MODEL_VERSION = "uniform_masked_v0"       # política de INFRAESTRUTURA (sem aprendizado); o modelo híbrido RL é a P1.19


@dataclass(frozen=True)
class ParamRow:
    parameter: str
    value: str
    source: str
    status: str          # "DESIGN" | "PROV"
    note: str = ""


def parameter_table() -> List[ParamRow]:
    return [
        ParamRow("target_population", str(DEFAULT_TARGET_POPULATION), "21 §21.2", "DESIGN", "configurável por execução"),
        ParamRow("creation_interval_real_seconds", str(DEFAULT_CREATION_INTERVAL_REAL_SECONDS), "21 §21.2", "DESIGN", "configurável por execução"),
        ParamRow("max_creation_burst", str(DEFAULT_MAX_CREATION_BURST), "—", "PROV"),
        ParamRow("eval_after_action_seconds", str(EVAL_AFTER_ACTION_SECONDS), "21 §21.4 (intervalo variável, sem valores)", "PROV"),
        ParamRow("eval_idle_seconds", str(EVAL_IDLE_SECONDS), "21 §21.4", "PROV"),
        ParamRow("eval_first_seconds", str(EVAL_FIRST_SECONDS), "21 §21.4", "PROV"),
        ParamRow("baseline_model_version", BASELINE_MODEL_VERSION, "21 §21.59 (sem LLM; RL é a P1.19)", "DESIGN"),
    ]
