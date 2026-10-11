from django.apps import AppConfig


class TravelConfig(AppConfig):
    name = "travel"

    def ready(self):
        from players import hooks
        from . import services, tick_handlers  # noqa: F401  (registra o handler de chegada)

        hooks.register_player_created_hook("travel", services.on_player_created)   # localização inicial
        hooks.register_block_provider("travel", services.presence_block)           # bloqueio durante a viagem
        hooks.register_access_hook("travel", services.settle_arrivals)             # chegada exata (On Access)
