import random
from decimal import Decimal

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from core.models import RegistroDeTrabalho
from empresas.models import Cargo
from geography.models import Bairro
from skills.models import CategoriaDeHabilidade, HabilidadeDoJogador, xp_necessario_para_nivel

from .forms import CadastroForm
from .models import Perfil

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
    registros_recentes = RegistroDeTrabalho.objects.filter(usuario=request.user).select_related("categoria")[:5]

    categorias = CategoriaDeHabilidade.objects.all()
    habilidades_existentes = {
        h.categoria_id: h for h in HabilidadeDoJogador.objects.filter(usuario=request.user)
    }
    habilidades = [
        {
            "categoria": categoria,
            "nivel": habilidades_existentes[categoria.id].nivel if categoria.id in habilidades_existentes else 0,
            "xp_atual": habilidades_existentes[categoria.id].xp_atual if categoria.id in habilidades_existentes else 0,
            "xp_necessario": (
                habilidades_existentes[categoria.id].xp_necessario()
                if categoria.id in habilidades_existentes
                else xp_necessario_para_nivel(0)
            ),
        }
        for categoria in categorias
    ]

    cargo_atual = Cargo.objects.select_related("empresa", "categoria_habilidade").filter(
        ocupante=request.user
    ).first()

    return render(
        request,
        "accounts/painel.html",
        {
            "perfil": perfil,
            "registros_recentes": registros_recentes,
            "categorias": categorias,
            "habilidades": habilidades,
            "cargo_atual": cargo_atual,
        },
    )
