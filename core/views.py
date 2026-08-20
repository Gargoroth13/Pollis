import random
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from skills.models import HabilidadeDoJogador, Skill

from .models import RegistroDeTrabalho

# Constantes do "trabalho genérico" do MVP. Quando o sistema de profissões
# existir, cada emprego vai ter os seus próprios valores em vez destes fixos.
CUSTO_DE_ENERGIA_TRABALHO = 10
GANHO_MINIMO = 8
GANHO_MAXIMO = 25
XP_MINIMO = 5
XP_MAXIMO = 15


@login_required
@require_POST
def trabalhar(request):
    perfil = request.user.perfil
    skill = request.POST.get("skill")
    if skill not in Skill.values:
        messages.error(request, "Escolha uma skill válida pra trabalhar.")
        return redirect("painel")

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

    xp_ganho = random.randint(XP_MINIMO, XP_MAXIMO)
    habilidade, _ = HabilidadeDoJogador.objects.get_or_create(usuario=request.user, skill=skill)
    niveis_subidos = habilidade.ganhar_xp(xp_ganho)

    RegistroDeTrabalho.objects.create(
        usuario=request.user,
        skill=skill,
        energia_gasta=CUSTO_DE_ENERGIA_TRABALHO,
        dinheiro_ganho=dinheiro_ganho,
        xp_ganho=xp_ganho,
    )

    nome_da_skill = habilidade.get_skill_display()
    mensagem = f"Você trabalhou em {nome_da_skill} e ganhou R$ {dinheiro_ganho} + {xp_ganho} XP."
    if niveis_subidos:
        mensagem += f" Subiu pro nível {habilidade.nivel} em {nome_da_skill}!"
    messages.success(request, mensagem)
    return redirect("painel")
