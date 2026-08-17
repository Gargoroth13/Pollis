import random
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from .models import RegistroDeTrabalho

# Constantes do "trabalho genérico" do MVP. Quando o sistema de profissões
# existir, cada emprego vai ter os seus próprios valores em vez destes fixos.
CUSTO_DE_ENERGIA_TRABALHO = 10
GANHO_MINIMO = 8
GANHO_MAXIMO = 25


@login_required
@require_POST
def trabalhar(request):
    perfil = request.user.perfil

    if not perfil.gastar_energia(CUSTO_DE_ENERGIA_TRABALHO):
        messages.error(
            request,
            f"Energia insuficiente. Você precisa de {CUSTO_DE_ENERGIA_TRABALHO} "
            f"e tem {perfil.energia_atual}.",
        )
        return redirect("painel")

    dinheiro_ganho = Decimal(random.randint(GANHO_MINIMO, GANHO_MAXIMO))
    perfil.dinheiro += dinheiro_ganho
    perfil.save(update_fields=["dinheiro"])

    RegistroDeTrabalho.objects.create(
        usuario=request.user,
        energia_gasta=CUSTO_DE_ENERGIA_TRABALHO,
        dinheiro_ganho=dinheiro_ganho,
    )

    messages.success(request, f"Você trabalhou e ganhou R$ {dinheiro_ganho}.")
    return redirect("painel")
