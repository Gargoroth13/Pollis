from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import ItemDoJogador, Perfil, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    pass


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = (
        "usuario",
        "bairro",
        "dinheiro",
        "energia_atual",
        "saude_atual",
        "nutricao_atual",
        "qol_atual",
        "em_depressao",
        "internado_ate",
    )
    list_filter = ("bairro__cidade", "em_depressao")
    search_fields = ("usuario__username",)
    autocomplete_fields = ("bairro",)


@admin.register(ItemDoJogador)
class ItemDoJogadorAdmin(admin.ModelAdmin):
    list_display = ("usuario", "produto", "quantidade")
    search_fields = ("usuario__username", "produto__nome")
    autocomplete_fields = ("usuario", "produto")


admin.site.site_header = "Administração do Polis"
admin.site.site_title = "Polis Admin"
