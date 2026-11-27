from django.apps import AppConfig


class RankingsConfig(AppConfig):
    name = "rankings"

    def ready(self):
        from . import wiring
        wiring.connect()    # observer de ações (Maior tempo ativo) + varredura diária do recorde de patrimônio
