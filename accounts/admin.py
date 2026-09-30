from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    pass


admin.site.site_header = "Administração do Polis"
admin.site.site_title = "Polis Admin"
