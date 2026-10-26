from django.apps import AppConfig


class PropertiesConfig(AppConfig):
    name = "properties"

    def ready(self):
        from . import registration, services

        services.register()          # obra com lote (validação, vínculo, conclusão) e encerramento dos leilões no tick do mundo
        registration.register()      # ações no Action Registry
