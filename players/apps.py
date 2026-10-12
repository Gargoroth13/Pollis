from django.apps import AppConfig


class PlayersConfig(AppConfig):
    name = "players"

    def ready(self):
        from . import tick_handlers  # noqa: F401  (registra os handlers do escopo "player")
        from . import registry
        registry.register_player_actions()  # Trabalhar, Estudar e Lazer no Action Registry (21 §20)
