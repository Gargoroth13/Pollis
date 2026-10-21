from django.apps import AppConfig


class CompaniesConfig(AppConfig):
    name = "companies"

    def ready(self):
        from . import construction, payroll, production, registration, support

        registration.register()          # Fundar, aportar, cargos e mural no Action Registry (design/02; 21 §20)
        production.register()            # produção no Trabalho: bloqueios, hook, sem curva global [PROV]
        support.register()               # Engenheiro/Advogado: efeito diário e risco de Burnout (02 §9)
        construction.register()          # Construtora: a obra anda com o Trabalhar (02 §12)
        payroll.register()               # salário do Trabalho (hook + atividade) e folha diária do Dono (tick do mundo)
