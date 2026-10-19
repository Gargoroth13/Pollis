from django.apps import AppConfig


class CompaniesConfig(AppConfig):
    name = "companies"

    def ready(self):
        from . import registration

        registration.register()          # Fundar empresa e aporte de capital no Action Registry (design/02; 21 §20)
