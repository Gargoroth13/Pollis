import random
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import RegistroDeTrabalho
from empresas.models import Cargo
from geography.models import Bairro
from skills.models import HabilidadeDoJogador, Skill, xp_necessario_para_nivel

from .forms import CadastroForm
from .models import ItemDoJogador, Perfil

# Chance de nascer em cada faixa de renda. Ajuste esses números pra mudar
# a distribuição social da cidade — não precisa mexer em nenhum outro lugar.
DISTRIBUICAO_DE_RENDA = {
    Bairro.FaixaRenda.BAIXA: 50,
    Bairro.FaixaRenda.MEDIA: 40,
    Bairro.FaixaRenda.ALTA: 10,
}

# Faixa de dinheiro inicial (min, max) de acordo com a faixa de renda sorteada.
DINHEIRO_INICIAL_POR_FAIXA = {
    Bairro.FaixaRenda.BAIXA: (200, 800),
    Bairro.FaixaRenda.MEDIA: (800, 3000),
    Bairro.FaixaRenda.ALTA: (3000, 15000),
}


def _sortear_bairro_de_nascimento():
    faixas = list(DISTRIBUICAO_DE_RENDA.keys())
    pesos = list(DISTRIBUICAO_DE_RENDA.values())
    faixa_sorteada = random.choices(faixas, weights=pesos, k=1)[0]

    candidatos = list(Bairro.objects.filter(faixa_renda=faixa_sorteada))
    if not candidatos:
        # Rede de segurança: se ainda não existir nenhum bairro cadastrado
        # nessa faixa específica, cai pra qualquer bairro existente.
        candidatos = list(Bairro.objects.all())

    if not candidatos:
        return None, None

    bairro = random.choice(candidatos)
    return bairro, faixa_sorteada


def cadastro(request):
    if request.user.is_authenticated:
        return redirect("painel")

    if request.method == "POST":
        form = CadastroForm(request.POST)
        if form.is_valid():
            bairro, faixa = _sortear_bairro_de_nascimento()
            if bairro is None:
                form.add_error(
                    None,
                    "Ainda não existe nenhum bairro cadastrado na cidade. "
                    "Rode o comando de seed antes de criar contas.",
                )
            else:
                usuario = form.save()

                minimo, maximo = DINHEIRO_INICIAL_POR_FAIXA[faixa]
                dinheiro_inicial = Decimal(random.randint(minimo, maximo))

                Perfil.objects.create(
                    usuario=usuario,
                    bairro=bairro,
                    dinheiro=dinheiro_inicial,
                )

                login(request, usuario)
                return redirect("painel")
    else:
        form = CadastroForm()

    return render(request, "accounts/cadastro.html", {"form": form})


def home(request):
    if request.user.is_authenticated:
        return redirect("painel")
    return redirect("login")


@login_required
def painel(request):
    perfil = request.user.perfil
    perfil.sincronizar()
    registros_recentes = RegistroDeTrabalho.objects.filter(usuario=request.user)[:5]

    habilidades_existentes = {
        h.skill: h for h in HabilidadeDoJogador.objects.filter(usuario=request.user)
    }
    habilidades = [
        {
            "skill": valor,
            "nome": rotulo,
            "nivel": habilidades_existentes[valor].nivel if valor in habilidades_existentes else 0,
            "xp_atual": habilidades_existentes[valor].xp_atual if valor in habilidades_existentes else 0,
            "xp_necessario": (
                habilidades_existentes[valor].xp_necessario()
                if valor in habilidades_existentes
                else xp_necessario_para_nivel(0)
            ),
        }
        for valor, rotulo in Skill.choices
    ]

    cargo_atual = Cargo.objects.select_related("empresa").filter(ocupante=request.user).first()

    return render(
        request,
        "accounts/painel.html",
        {
            "perfil": perfil,
            "registros_recentes": registros_recentes,
            "habilidades": habilidades,
            "cargo_atual": cargo_atual,
        },
    )


@login_required
def inventario(request):
    perfil = request.user.perfil
    perfil.sincronizar()
    itens = ItemDoJogador.objects.filter(usuario=request.user, quantidade__gt=0).select_related("produto")
    return render(request, "accounts/inventario.html", {"perfil": perfil, "itens": itens})


@login_required
@require_POST
def consumir(request, item_id):
    item = get_object_or_404(ItemDoJogador, id=item_id, usuario=request.user)
    if not item.produto.eh_comivel():
        messages.error(request, f"{item.produto.nome} não é um item que dá pra consumir.")
        return redirect("inventario")
    if item.quantidade <= 0:
        messages.error(request, "Você não tem mais desse item.")
        return redirect("inventario")

    perfil = request.user.perfil
    perfil.sincronizar()
    perfil.comer(item.produto.nutricao, item.produto.efeito_qol)
    perfil.save(update_fields=["nutricao_atual", "qol_atual"])

    item.quantidade -= 1
    item.save(update_fields=["quantidade"])

    messages.success(
        request,
        f"Consumiu 1x {item.produto.nome}. Nutrição +{item.produto.nutricao}, QoL {item.produto.efeito_qol:+}.",
    )
    return redirect("inventario")
