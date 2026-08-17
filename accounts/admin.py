from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Perfil, Usuario


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
        "energia_maxima",
        "saude_atual",
        "saude_maxima",
    )
    list_filter = ("bairro__cidade",)
    search_fields = ("usuario__username",)
    autocomplete_fields = ("bairro",)


admin.site.site_header = "Administração do Polis"
admin.site.site_title = "Polis Admin"
