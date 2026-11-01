from django.contrib import admin

from .models import NewsItem


@admin.register(NewsItem)
class NewsItemAdmin(admin.ModelAdmin):
    """Dev/Admin vê o dado bruto que originou a notícia (12.11); ninguém edita nem apaga (12.10)."""
    list_display = ("id", "at", "category", "priority", "headline", "ref_kind", "ref_id")
    list_filter = ("category",)
    search_fields = ("headline", "body", "dedupe_key")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
