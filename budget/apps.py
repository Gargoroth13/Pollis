from django.apps import AppConfig


class BudgetConfig(AppConfig):
    name = "budget"

    def ready(self):
        from . import registration

        registration.register()      # ações no Action Registry
