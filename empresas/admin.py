from django.contrib import admin

from .models import Cargo, EstoqueDaEmpresa, Empresa, Produto, Receita


class CargoInline(admin.TabularInline):
    model = Cargo
    extra = 0
    autocomplete_fields = ("ocupante",)


class EstoqueInline(admin.TabularInline):
    model = EstoqueDaEmpresa
    extra = 0
    autocomplete_fields = ("produto",)


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = (
        "nome", "tipo", "terreno", "tipo_industria", "especializacao_servico",
        "dono", "estrelas", "funcionarios_ocupados",
    )
    list_filter = ("tipo", "terreno", "tipo_industria", "especializacao_servico", "estrelas")
    search_fields = ("nome", "dono__username")
    autocomplete_fields = ("dono",)
    inlines = [CargoInline, EstoqueInline]

    @admin.display(description="Funcionários")
    def funcionarios_ocupados(self, obj):
        return obj.funcionarios_ocupados()


@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "empresa", "skill_relevante", "nivel_minimo", "salario", "ocupante")
    list_filter = ("empresa", "skill_relevante")
    search_fields = ("titulo", "empresa__nome", "ocupante__username")
    autocomplete_fields = ("empresa", "ocupante")


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ("nome", "eh_materia_prima", "terreno_produtor", "tipo_industria_produtor", "preco_base")
    list_filter = ("eh_materia_prima", "terreno_produtor", "tipo_industria_produtor")
    search_fields = ("nome",)


@admin.register(Receita)
class ReceitaAdmin(admin.ModelAdmin):
    list_display = ("produto_final", "ingrediente", "quantidade_necessaria", "quantidade_produzida", "estrela_minima")
    list_filter = ("produto_final", "estrela_minima")


@admin.register(EstoqueDaEmpresa)
class EstoqueDaEmpresaAdmin(admin.ModelAdmin):
    list_display = ("empresa", "produto", "quantidade")
    list_filter = ("empresa__tipo", "produto")
    search_fields = ("empresa__nome", "produto__nome")
    autocomplete_fields = ("empresa", "produto")
