from django.apps import AppConfig


class PlayersConfig(AppConfig):
    name = "players"

    def ready(self):
        from . import tick_handlers  # noqa: F401  (registra os handlers do escopo "player")
