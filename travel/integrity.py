"""
Integridade de localização e viagem: relatório estruturado, como geography.integrity. Cobre as invariantes que o banco
sozinho não garante (consistência entre localização, viagens e o processamento de tempo do jogador).
"""
from __future__ import annotations

from geography.integrity import IntegrityReport
from players.models import Player

from .models import Journey, PlayerLocation


def check_integrity() -> IntegrityReport:
    r = IntegrityReport()
    players = list(Player.objects.all())
    locations = {l.player_id: l for l in PlayerLocation.objects.select_related("lot")}
    r.stats = {"players": len(players), "locations": len(locations), "active_journeys": Journey.objects.filter(completed=False).count()}
    for p in players:
        loc = locations.get(p.id)
        if loc is None:
            r.add("PLAYER_WITHOUT_LOCATION", f"jogador {p.id}")
            continue
        active = Journey.objects.filter(player=p, completed=False).first()
        if active is not None:
            if active.origin_id != loc.lot_id:
                r.add("ACTIVE_JOURNEY_ORIGIN_NOT_LOCATION", f"jogador {p.id}")
            if active.arrives_at <= p.processed_until:
                r.add("JOURNEY_NOT_SETTLED", f"jogador {p.id}: chegou em {active.arrives_at} e o jogador já foi processado até {p.processed_until}")
        else:
            last = Journey.objects.filter(player=p, completed=True).order_by("arrives_at", "id").last()
            if last is not None and last.destination_id != loc.lot_id:
                r.add("LOCATION_NOT_LAST_DESTINATION", f"jogador {p.id}")
    return r
