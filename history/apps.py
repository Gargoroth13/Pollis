from django.apps import AppConfig


class HistoryConfig(AppConfig):
    name = "history"

    def ready(self):
        from . import economy

        economy.register()      # notícias de tendência de preço no tick diário do mundo (design/12 §12.4)
