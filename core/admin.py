from django.contrib import admin

from .models import RegistroDeTrabalho


@admin.register(RegistroDeTrabalho)
class RegistroDeTrabalhoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "energia_gasta", "dinheiro_ganho", "quando")
    list_filter = ("quando",)
    search_fields = ("usuario__username",)
