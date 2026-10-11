"""
Integridade do catálogo GRAVADO: valida o que está no banco (mesma validação das definições) e confere se ele corresponde às
definições transcritas do 22. Devolve relatório estruturado com códigos estáveis; separa ERRO de PENDÊNCIA de design.
"""
from __future__ import annotations

from typing import Sequence

from .definitions import PRODUCTS, ProductDef
from .loader import load_from_db
from .validation import CatalogReport, validate


def check_integrity(definitions: Sequence[ProductDef] = PRODUCTS) -> CatalogReport:
    db = load_from_db()
    if not db:
        r = CatalogReport()
        r.error("EMPTY_CATALOG", "catalog", "nenhum produto carregado (rode `sync_catalog`)")
        return r
    r = validate(list(db.values()))
    wanted = {d.key: d for d in definitions}
    for key in sorted(wanted.keys() - db.keys()):
        r.error("CATALOG_NOT_SYNCED", key, "definido no 22 mas ausente do banco")
    for key in sorted(db.keys() - wanted.keys()):
        r.error("PRODUCT_NOT_IN_DEFINITIONS", key, "existe no banco e não nas definições")
    for key in sorted(db.keys() & wanted.keys()):
        if db[key] != wanted[key]:
            r.error("PRODUCT_DIFFERS_FROM_DEFINITIONS", key, "banco difere das definições; rode `sync_catalog`")
    r.stats["errors"], r.stats["pending"] = len(r.errors), len(r.pending)
    return r
