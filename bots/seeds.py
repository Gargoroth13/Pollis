"""Contexto aleatório reproduzível (21 §21.49): toda decisão se associa a Bot + versão do jogo + versão do modelo + seed + estado."""
from __future__ import annotations

import hashlib
import random


def derive_seed(*parts) -> int:
    """Inteiro de 63 bits derivado de forma estável (SHA-256) das partes; independe do PYTHONHASHSEED e da plataforma."""
    text = "\x1f".join(str(p) for p in parts)
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big") >> 1


def rng_for(seed: int) -> random.Random:
    return random.Random(seed)
