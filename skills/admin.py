from django.contrib import admin

from .models import PlayerSkill, Specialization


@admin.register(PlayerSkill)
class PlayerSkillAdmin(admin.ModelAdmin):
    list_display = ("player", "skill", "level")
    list_filter = ("skill",)


@admin.register(Specialization)
class SpecializationAdmin(admin.ModelAdmin):
    list_display = ("player", "key", "value", "historic_max", "last_used_day")
