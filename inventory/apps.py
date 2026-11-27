from django.apps import AppConfig


class InventoryConfig(AppConfig):
    name = "inventory"

    def ready(self):
        from players import hooks

        from . import auto, registration

        registration.register()          # Consumir, Correio e Auto-consumo no Action Registry (design/05, 04 §16; 21 §20)
        hooks.register_access_hook("inventory.auto_consumption", auto.on_access)      # 04 §16: no processamento lazy
