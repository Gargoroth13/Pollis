from django.contrib import admin

from .models import CategoriaDeHabilidade, HabilidadeDoJogador


@admin.register(CategoriaDeHabilidade)
class CategoriaDeHabilidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "descricao")
    search_fields = ("nome",)


@admin.register(HabilidadeDoJogador)
class HabilidadeDoJogadorAdmin(admin.ModelAdmin):
    list_display = ("usuario", "categoria", "nivel", "xp_atual")
    list_filter = ("categoria",)
    search_fields = ("usuario__username",)
    autocomplete_fields = ("usuario",)
