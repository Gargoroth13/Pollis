from django.apps import AppConfig


class CompaniesConfig(AppConfig):
    name = "companies"

    def ready(self):
        from . import payroll, production, registration

        registration.register()          # Fundar, aportar, cargos e mural no Action Registry (design/02; 21 §20)
        production.register()            # produção no Trabalho: bloqueios, hook, curva [PROV] de skill
        payroll.register()               # salário do Trabalho (hook + atividade) e folha diária do Dono (tick do mundo)
