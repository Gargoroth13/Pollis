from django.contrib import admin

from .models import CartaoDeCredito, DadosFinanceiros, Emprestimo, Poupanca


@admin.register(DadosFinanceiros)
class DadosFinanceirosAdmin(admin.ModelAdmin):
    list_display = ("empresa", "caixa", "obrigacoes_totais", "indice_de_reserva", "rating", "falida")
    list_filter = ("falida",)
    search_fields = ("empresa__nome",)
    autocomplete_fields = ("empresa",)


@admin.register(Poupanca)
class PoupancaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "financeira", "saldo", "bloqueado_ate")
    search_fields = ("usuario__username", "financeira__nome")
    autocomplete_fields = ("usuario", "financeira")


@admin.register(Emprestimo)
class EmprestimoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "financeira", "valor_original", "saldo_devedor", "taxa_juros", "quitado")
    list_filter = ("quitado",)
    search_fields = ("usuario__username", "financeira__nome")
    autocomplete_fields = ("usuario", "financeira")


@admin.register(CartaoDeCredito)
class CartaoDeCreditoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "financeira", "limite", "saldo_devedor")
    search_fields = ("usuario__username", "financeira__nome")
    autocomplete_fields = ("usuario", "financeira")
