from django.contrib import admin

from .models import Cargo, Empresa


class CargoInline(admin.TabularInline):
    model = Cargo
    extra = 0
    autocomplete_fields = ("ocupante",)


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nome", "setor", "dono", "estrelas", "funcionarios_ocupados")
    list_filter = ("setor", "estrelas")
    search_fields = ("nome", "dono__username")
    autocomplete_fields = ("dono",)
    inlines = [CargoInline]

    @admin.display(description="Funcionários")
    def funcionarios_ocupados(self, obj):
        return obj.funcionarios_ocupados()


@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "empresa", "categoria_habilidade", "nivel_minimo", "salario", "ocupante")
    list_filter = ("empresa", "categoria_habilidade")
    search_fields = ("titulo", "empresa__nome", "ocupante__username")
    autocomplete_fields = ("empresa", "ocupante")
