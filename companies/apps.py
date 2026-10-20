from django.apps import AppConfig


class CompaniesConfig(AppConfig):
    name = "companies"

    def ready(self):
        from . import payroll, registration

        registration.register()          # Fundar, aportar, cargos e mural no Action Registry (design/02; 21 §20)
        payroll.register()               # salário do Trabalho (hook + atividade) e folha diária do Dono (tick do mundo)
