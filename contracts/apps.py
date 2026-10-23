from django.apps import AppConfig


class ContractsConfig(AppConfig):
    name = "contracts"

    def ready(self):
        from . import registration, services

        services.register()          # handlers dos tipos e execução diária no tick do mundo
        registration.register()      # ações no Action Registry
