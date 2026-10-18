from django.apps import AppConfig


class LedgerConfig(AppConfig):
    name = "ledger"

    def ready(self):
        from players import hooks
        from . import integration

        hooks.register_player_created_hook("ledger", integration.on_player_created)   # conta do jogador + dotação do cenário
        integration.register_travel_payment()                                          # viagem cobra pelo registro (design/24 §24.18)
