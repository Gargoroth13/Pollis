import random

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import RegistroDeTrabalho
from skills.models import HabilidadeDoJogador

from .forms import CriarCargoForm, CriarEmpresaForm
from .models import ESTRELA_MAXIMA, Cargo, Empresa

Usuario = get_user_model()

CUSTO_DE_ENERGIA_TRABALHO = 10
XP_MINIMO = 5
XP_MAXIMO = 15


def listar(request):
    empresas = Empresa.objects.select_related("setor", "dono")
    return render(request, "empresas/lista.html", {"empresas": empresas})


@login_required
def criar_empresa(request):
    if request.method == "POST":
        form = CriarEmpresaForm(request.POST)
        if form.is_valid():
            empresa = form.save(commit=False)
            empresa.dono = request.user
            empresa.save()
            messages.success(request, f"{empresa.nome} foi fundada com 1 estrela.")
            return redirect("empresas_detalhe", empresa_id=empresa.id)
    else:
        form = CriarEmpresaForm()
    return render(request, "empresas/criar_empresa.html", {"form": form})


def detalhe(request, empresa_id):
    empresa = get_object_or_404(Empresa.objects.select_related("setor", "dono"), id=empresa_id)
    cargos = empresa.cargos.select_related("categoria_habilidade", "ocupante")
    eh_dono = request.user.is_authenticated and request.user.id == empresa.dono_id
    estrelas_visual = "★" * empresa.estrelas + "☆" * (ESTRELA_MAXIMA - empresa.estrelas)
    return render(
        request,
        "empresas/detalhe.html",
        {
            "empresa": empresa,
            "cargos": cargos,
            "eh_dono": eh_dono,
            "estrelas_visual": estrelas_visual,
            "form_cargo": CriarCargoForm() if eh_dono else None,
            "requisitos_para_upar": empresa.requisitos_para_upar(),
        },
    )


@login_required
@require_POST
def criar_cargo(request, empresa_id):
    empresa = get_object_or_404(Empresa, id=empresa_id, dono=request.user)

    if empresa.cargos.count() >= empresa.max_cargos_permitidos():
        messages.error(
            request,
            f"{empresa.nome} já está no limite de {empresa.max_cargos_permitidos()} "
            "cargos pro nível de estrela atual. Suba de nível pra abrir mais vagas.",
        )
        return redirect("empresas_detalhe", empresa_id=empresa.id)

    form = CriarCargoForm(request.POST)
    if form.is_valid():
        cargo = form.save(commit=False)
        cargo.empresa = empresa
        cargo.save()
        messages.success(request, f"Cargo '{cargo.titulo}' criado.")
    else:
        messages.error(request, "Não deu pra criar o cargo — confira os campos.")
    return redirect("empresas_detalhe", empresa_id=empresa.id)


@login_required
@require_POST
def contratar(request, empresa_id, cargo_id):
    empresa = get_object_or_404(Empresa, id=empresa_id, dono=request.user)
    cargo = get_object_or_404(Cargo, id=cargo_id, empresa=empresa)

    if not cargo.vago():
        messages.error(request, f"O cargo '{cargo.titulo}' já está ocupado.")
        return redirect("empresas_detalhe", empresa_id=empresa.id)

    username = request.POST.get("username", "").strip()
    candidato = Usuario.objects.filter(username=username).first()
    if candidato is None:
        messages.error(request, f"Não existe nenhum jogador com o username '{username}'.")
        return redirect("empresas_detalhe", empresa_id=empresa.id)

    if Cargo.objects.filter(ocupante=candidato).exists():
        messages.error(request, f"{candidato.username} já está empregado em outro cargo.")
        return redirect("empresas_detalhe", empresa_id=empresa.id)

    habilidade = HabilidadeDoJogador.objects.filter(
        usuario=candidato, categoria=cargo.categoria_habilidade
    ).first()
    nivel_do_candidato = habilidade.nivel if habilidade else 0
    if nivel_do_candidato < cargo.nivel_minimo:
        messages.error(
            request,
            f"{candidato.username} tem nível {nivel_do_candidato} em {cargo.categoria_habilidade.nome}, "
            f"mas o cargo exige nível {cargo.nivel_minimo}.",
        )
        return redirect("empresas_detalhe", empresa_id=empresa.id)

    cargo.ocupante = candidato
    cargo.save(update_fields=["ocupante"])
    messages.success(request, f"{candidato.username} foi contratado como {cargo.titulo}.")
    return redirect("empresas_detalhe", empresa_id=empresa.id)


@login_required
@require_POST
def demitir(request, empresa_id, cargo_id):
    empresa = get_object_or_404(Empresa, id=empresa_id, dono=request.user)
    cargo = get_object_or_404(Cargo, id=cargo_id, empresa=empresa)
    nome_antigo = cargo.ocupante.username if cargo.ocupante else None
    cargo.ocupante = None
    cargo.save(update_fields=["ocupante"])
    if nome_antigo:
        messages.success(request, f"{nome_antigo} foi demitido de {cargo.titulo}.")
    return redirect("empresas_detalhe", empresa_id=empresa.id)


@login_required
@require_POST
def upar_empresa(request, empresa_id):
    empresa = get_object_or_404(Empresa, id=empresa_id, dono=request.user)
    sucesso, mensagem = empresa.upar()
    if sucesso:
        messages.success(request, mensagem)
    else:
        messages.error(request, mensagem)
    return redirect("empresas_detalhe", empresa_id=empresa.id)


@login_required
@require_POST
def trabalhar_no_emprego(request):
    perfil = request.user.perfil
    cargo = Cargo.objects.select_related("empresa", "categoria_habilidade").filter(ocupante=request.user).first()

    if cargo is None:
        messages.error(request, "Você não está empregado em nenhum cargo formal.")
        return redirect("painel")

    if not perfil.gastar_energia(CUSTO_DE_ENERGIA_TRABALHO):
        messages.error(
            request,
            f"Energia insuficiente. Você precisa de {CUSTO_DE_ENERGIA_TRABALHO} e tem {perfil.energia_atual}.",
        )
        return redirect("painel")

    perfil.dinheiro += cargo.salario
    perfil.save(update_fields=["dinheiro"])

    xp_ganho = random.randint(XP_MINIMO, XP_MAXIMO)
    habilidade, _ = HabilidadeDoJogador.objects.get_or_create(
        usuario=request.user, categoria=cargo.categoria_habilidade
    )
    niveis_subidos = habilidade.ganhar_xp(xp_ganho)

    RegistroDeTrabalho.objects.create(
        usuario=request.user,
        categoria=cargo.categoria_habilidade,
        energia_gasta=CUSTO_DE_ENERGIA_TRABALHO,
        dinheiro_ganho=cargo.salario,
        xp_ganho=xp_ganho,
    )

    mensagem = (
        f"Você trabalhou como {cargo.titulo} na {cargo.empresa.nome} "
        f"e ganhou R$ {cargo.salario} + {xp_ganho} XP."
    )
    if niveis_subidos:
        mensagem += f" Subiu pro nível {habilidade.nivel} em {cargo.categoria_habilidade.nome}!"
    messages.success(request, mensagem)
    return redirect("painel")
