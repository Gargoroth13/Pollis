from django.contrib import admin

from .models import Player, QolEffect


class QolEffectInline(admin.TabularInline):
    model = QolEffect
    extra = 0


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("user", "energy", "health", "nutrition", "burnout", "burnout_active", "health_critical")
    inlines = [QolEffectInline]
