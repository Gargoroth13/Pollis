from django.apps import AppConfig


class InventoryConfig(AppConfig):
    name = "inventory"

    def ready(self):
        from . import registration

        registration.register()          # Consumir e Correio no Action Registry (design/05; 21 §20)
