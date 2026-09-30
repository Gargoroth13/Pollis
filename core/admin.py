from django.contrib import admin

from .models import WorldClock


@admin.register(WorldClock)
class WorldClockAdmin(admin.ModelAdmin):
    list_display = ("real_seconds_per_game_day", "anchor_game", "world_processed_until")
    # Alterar a velocidade aqui quebraria a continuidade do tempo: use
    # `manage.py world_clock set-speed`, que re-ancora corretamente.
    readonly_fields = [f.name for f in WorldClock._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
