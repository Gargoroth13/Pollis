from django.apps import AppConfig


class SchoolsConfig(AppConfig):
    name = "schools"

    def ready(self):
        from . import quality, registration, services

        services.register()          # matrícula inicial no bairro (hook de criação do jogador)
        quality.register()           # ciclo diário de qualidade: retrato dos materiais, decaimento, qualidade do dia
        registration.register()      # trocar de escola no Action Registry
