from django.contrib import admin

from .models import ActivityStreak, RankingHistorico


@admin.register(RankingHistorico)
class RankingHistoricoAdmin(admin.ModelAdmin):
    list_display = ("category", "entity_type", "entity_id", "value", "recorded_at", "updated_at")
    readonly_fields = [f.name for f in RankingHistorico._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ActivityStreak)
class ActivityStreakAdmin(admin.ModelAdmin):
    list_display = ("player", "best_length", "best_start", "best_end", "current_start", "last_action_at")
    readonly_fields = [f.name for f in ActivityStreak._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
