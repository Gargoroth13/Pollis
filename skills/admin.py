from django.contrib import admin

from .models import HabilidadeDoJogador


@admin.register(HabilidadeDoJogador)
class HabilidadeDoJogadorAdmin(admin.ModelAdmin):
    list_display = ("usuario", "skill", "nivel", "xp_atual")
    list_filter = ("skill",)
    search_fields = ("usuario__username",)
    autocomplete_fields = ("usuario",)
