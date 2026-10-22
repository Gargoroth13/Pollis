from django.apps import AppConfig


class MarketConfig(AppConfig):
    name = "market"

    def ready(self):
        from . import rollup

        rollup.register()               # fecha o dia no tick diário do mundo (17 §17.10, §17.19)
