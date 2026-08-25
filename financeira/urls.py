from django.urls import path

from . import views

urlpatterns = [
    path("financeira/<int:empresa_id>/", views.detalhe, name="financeira_detalhe"),
    path("financeira/<int:empresa_id>/depositar/", views.depositar, name="financeira_depositar"),
    path("financeira/<int:empresa_id>/sacar/", views.sacar, name="financeira_sacar"),
    path("financeira/<int:empresa_id>/emprestimo/pedir/", views.pedir_emprestimo, name="financeira_pedir_emprestimo"),
    path("financeira/<int:empresa_id>/emprestimo/pagar/", views.pagar_emprestimo, name="financeira_pagar_emprestimo"),
    path("financeira/<int:empresa_id>/cartao/pedir/", views.pedir_cartao, name="financeira_pedir_cartao"),
    path("financeira/<int:empresa_id>/cartao/sacar/", views.sacar_cartao, name="financeira_sacar_cartao"),
    path("financeira/<int:empresa_id>/cartao/pagar/", views.pagar_cartao, name="financeira_pagar_cartao"),
    path("financeira/<int:empresa_id>/transferir/", views.transferir, name="financeira_transferir"),
    path("financeira/<int:empresa_id>/capitalizar/", views.capitalizar, name="financeira_capitalizar"),
    path("financeira/<int:empresa_id>/falencia/", views.declarar_falencia, name="financeira_declarar_falencia"),
]
