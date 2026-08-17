from django.contrib import admin

from .models import Bairro, Cidade, Estado


@admin.register(Estado)
class EstadoAdmin(admin.ModelAdmin):
    list_display = ("nome", "sigla")
    search_fields = ("nome", "sigla")


@admin.register(Cidade)
class CidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "estado")
    list_filter = ("estado",)
    search_fields = ("nome",)


@admin.register(Bairro)
class BairroAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "cidade",
        "grid_x",
        "grid_y",
        "faixa_renda",
        "qualidade_vida",
        "e_bairro_da_prefeitura",
    )
    list_filter = ("cidade", "faixa_renda")
    search_fields = ("nome",)
