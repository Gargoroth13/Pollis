from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("cadastro/", views.cadastro, name="cadastro"),
    path("painel/", views.painel, name="painel"),
    path("inventario/", views.inventario, name="inventario"),
    path("inventario/<int:item_id>/consumir/", views.consumir, name="consumir"),
]
