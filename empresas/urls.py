from django.urls import path

from . import views

urlpatterns = [
    path("empresas/", views.listar, name="empresas_lista"),
    path("empresas/nova/", views.criar_empresa, name="empresas_criar"),
    path("empresas/<int:empresa_id>/", views.detalhe, name="empresas_detalhe"),
    path("empresas/<int:empresa_id>/cargos/novo/", views.criar_cargo, name="cargos_criar"),
    path("empresas/<int:empresa_id>/cargos/<int:cargo_id>/contratar/", views.contratar, name="cargo_contratar"),
    path("empresas/<int:empresa_id>/cargos/<int:cargo_id>/demitir/", views.demitir, name="cargo_demitir"),
    path("empresas/<int:empresa_id>/upar/", views.upar_empresa, name="empresas_upar"),
    path("trabalhar-emprego/", views.trabalhar_no_emprego, name="trabalhar_emprego"),
]
