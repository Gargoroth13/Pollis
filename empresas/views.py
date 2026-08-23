import random

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import ItemDoJogador
from core.models import RegistroDeTrabalho
from skills.models import HabilidadeDoJogador

from .forms import CriarCargoForm, CriarEmpresaForm
from .models import ESTRELA_MAXIMA, Cargo, Empresa, EstoqueDaEmpresa, Produto, TipoDeEmpresa

Usuario = get_user_model()

CUSTO_DE_ENERGIA_TRABALHO = 25  # DESIGN.md seção 5.1
XP_MINIMO = 5
XP_MAXIMO = 15
PRODUCAO_MINIMA = 5
PRODUCAO_MAXIMA = 15

# Define quem pode comprar de quem na cadeia produtiva: uma empresa do
# tipo chave pode comprar de qualquer uma das regras da sua lista. Cada
# regra diz de qual "tipo_vendedor" pode comprar, e se o produto tem
# que ser matéria-prima (True) ou manufaturado (False).
#
# Industrial agora tem DUAS regras: compra matéria-prima de Matriz (pra
# fabricar o básico) E compra manufaturado de outra Industrial (pra
# receitas que usam produto de outro tipo de indústria como ingrediente,
# ex: Carro precisa de Aço/Plástico feitos por uma Industrial de
# Produção e Bateria feita por uma Industrial Tecnológica).
REGRAS_DE_COMPRA = {
    TipoDeEmpresa.INDUSTRIAL: [
        {"tipo_vendedor": TipoDeEmpresa.MATRIZ, "materia_prima": True},
        {"tipo_vendedor": TipoDeEmpresa.INDUSTRIAL, "materia_prima": False},
    ],
    TipoDeEmpresa.VAREJO: [
        {"tipo_vendedor": TipoDeEmpresa.INDUSTRIAL, "materia_prima": False},
    ],
    TipoDeEmpresa.CONSTRUTORA: [
        {"tipo_vendedor": TipoDeEmpresa.INDUSTRIAL, "materia_prima": False},
    ],
}

# Produtos manufaturados consumidos automaticamente a cada produzir/fabricar,
# se a empresa tiver em estoque (não bloqueia a ação se não tiver — só avisa).
CONSUMO_OPERACIONAL_POR_ACAO = ["EPIs", "Uniforme"]


def _criar_estoque_inicial(empresa):
    """
    Ao fundar a empresa, já cria (com quantidade zero) as linhas de
    estoque dos produtos que ela tem permissão de produzir/fabricar —
    assim eles já aparecem na página da empresa prontos pra começar a
    produzir, sem precisar de nenhum passo manual extra.
    """
    if empresa.tipo == TipoDeEmpresa.MATRIZ:
        produtos = Produto.objects.filter(terreno_produtor=empresa.terreno, eh_materia_prima=True)
    elif empresa.tipo == TipoDeEmpresa.INDUSTRIAL:
        produtos = Produto.objects.filter(tipo_industria_produtor=empresa.tipo_industria, eh_materia_prima=False)
    else:
        produtos = Produto.objects.none()

    for produto in produtos:
        EstoqueDaEmpresa.objects.get_or_create(empresa=empresa, produto=produto)


def _pode_operar_empresa(usuario, empresa):
    """
    Produzir/fabricar deixa de ser ação exclusiva do dono (DESIGN.md
    seção 2.9) — qualquer funcionário contratado (Cargo com esse
    usuário como ocupante) também pode, além do próprio dono.
    """
    if empresa.dono_id == usuario.id:
        return True
    return Cargo.objects.filter(empresa=empresa, ocupante=usuario).exists()


def _consumir_operacional(empresa):
    """
    Consome 1 unidade de cada produto de CONSUMO_OPERACIONAL_POR_ACAO
    (EPIs, Uniforme) do próprio estoque da empresa, se ela tiver. Não
    bloqueia a ação (produzir/fabricar) se faltar — só avisa, porque
    bloquear travaria toda empresa recém-fundada que ainda não comprou
    nada disso. Retorna uma string de aviso (ou "" se não faltou nada).
    """
    faltando = []
    for nome_produto in CONSUMO_OPERACIONAL_POR_ACAO:
        estoque = EstoqueDaEmpresa.objects.filter(empresa=empresa, produto__nome=nome_produto).first()
        if estoque and estoque.quantidade > 0:
            estoque.quantidade -= 1
            estoque.save(update_fields=["quantidade"])
        else:
            faltando.append(nome_produto)

    if faltando:
        return f"⚠️ Sem {' e '.join(faltando)} em estoque (consumo operacional não pago)."
    return ""


def listar(request):
    empresas = Empresa.objects.select_related("dono")
    return render(request, "empresas/lista.html", {"empresas": empresas})


@login_required
def criar_empresa(request):
    if request.method == "POST":
        form = CriarEmpresaForm(request.POST)
        if form.is_valid():
            empresa = form.save(commit=False)
            empresa.dono = request.user
            empresa.save()
            _criar_estoque_inicial(empresa)
            messages.success(request, f"{empresa.nome} foi fundada com 1 estrela.")
            return redirect("empresas_detalhe", empresa_id=empresa.id)
    else:
        form = CriarEmpresaForm()
    return render(request, "empresas/criar_empresa.html", {"form": form})


def detalhe(request, empresa_id):
    empresa = get_object_or_404(Empresa.objects.select_related("dono"), id=empresa_id)
    cargos = empresa.cargos.select_related("ocupante")
    eh_dono = request.user.is_authenticated and request.user.id == empresa.dono_id
    estrelas_visual = "★" * empresa.estrelas + "☆" * (ESTRELA_MAXIMA - empresa.estrelas)
    estoque = empresa.estoque.select_related("produto").order_by("produto__nome")

    produtos_para_produzir = None
    produtos_para_fabricar = None
    vendedores_disponiveis = None

    if eh_dono:
        if empresa.tipo == TipoDeEmpresa.MATRIZ:
            produtos_para_produzir = Produto.objects.filter(terreno_produtor=empresa.terreno, eh_materia_prima=True)
        elif empresa.tipo == TipoDeEmpresa.INDUSTRIAL:
            produtos_para_fabricar = Produto.objects.filter(
                tipo_industria_produtor=empresa.tipo_industria, eh_materia_prima=False
            )

        for regra in REGRAS_DE_COMPRA.get(empresa.tipo, []):
            ofertas_da_regra = EstoqueDaEmpresa.objects.filter(
                empresa__tipo=regra["tipo_vendedor"],
                produto__eh_materia_prima=regra["materia_prima"],
                quantidade__gt=0,
            ).exclude(empresa=empresa).select_related("empresa", "produto")
            vendedores_disponiveis = (
                ofertas_da_regra if vendedores_disponiveis is None else vendedores_disponiveis | ofertas_da_regra
            )

    return render(
        request,
        "empresas/detalhe.html",
        {
            "empresa": empresa,
            "cargos": cargos,
            "eh_dono": eh_dono,
            "estrelas_visual": estrelas_visual,
            "classificacao": empresa.classificacao_legivel(),
            "form_cargo": CriarCargoForm() if eh_dono else None,
            "requisitos_para_upar": empresa.requisitos_para_upar(),
            "estoque": estoque,
            "produtos_para_produzir": produtos_para_produzir,
            "produtos_para_fabricar": produtos_para_fabricar,
            "vendedores_disponiveis": vendedores_disponiveis,
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
        usuario=candidato, skill=cargo.skill_relevante
    ).first()
    nivel_do_candidato = habilidade.nivel if habilidade else 0
    if nivel_do_candidato < cargo.nivel_minimo:
        messages.error(
            request,
            f"{candidato.username} tem nível {nivel_do_candidato} em {cargo.get_skill_relevante_display()}, "
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
    perfil.sincronizar()
    cargo = Cargo.objects.select_related("empresa").filter(ocupante=request.user).first()

    if cargo is None:
        messages.error(request, "Você não está empregado em nenhum cargo formal.")
        return redirect("painel")

    if perfil.esta_internado():
        messages.error(request, f"Você está internado até {perfil.internado_ate:%d/%m %H:%M} e não pode trabalhar.")
        return redirect("painel")

    if not perfil.gastar_energia(CUSTO_DE_ENERGIA_TRABALHO):
        messages.error(
            request,
            f"Energia insuficiente. Você precisa de {CUSTO_DE_ENERGIA_TRABALHO} e tem {perfil.energia_atual}.",
        )
        return redirect("painel")

    perfil.dinheiro += cargo.salario
    perfil.save(update_fields=["dinheiro"])

    xp_ganho = round(random.randint(XP_MINIMO, XP_MAXIMO) * perfil.multiplicador_de_eficacia())
    xp_ganho = max(xp_ganho, 1)
    habilidade, _ = HabilidadeDoJogador.objects.get_or_create(
        usuario=request.user, skill=cargo.skill_relevante
    )
    niveis_subidos = habilidade.ganhar_xp(xp_ganho)

    RegistroDeTrabalho.objects.create(
        usuario=request.user,
        skill=cargo.skill_relevante,
        energia_gasta=CUSTO_DE_ENERGIA_TRABALHO,
        dinheiro_ganho=cargo.salario,
        xp_ganho=xp_ganho,
    )

    mensagem = (
        f"Você trabalhou como {cargo.titulo} na {cargo.empresa.nome} "
        f"e ganhou R$ {cargo.salario} + {xp_ganho} XP."
    )
    if niveis_subidos:
        mensagem += f" Subiu pro nível {habilidade.nivel} em {cargo.get_skill_relevante_display()}!"
    messages.success(request, mensagem)
    return redirect("painel")


@login_required
@require_POST
def produzir(request, empresa_id):
    empresa = get_object_or_404(Empresa, id=empresa_id, tipo=TipoDeEmpresa.MATRIZ)
    if not _pode_operar_empresa(request.user, empresa):
        messages.error(request, "Você precisa ser dono ou funcionário dessa empresa pra produzir.")
        return redirect("empresas_detalhe", empresa_id=empresa.id)

    produto = get_object_or_404(
        Produto, id=request.POST.get("produto_id"), terreno_produtor=empresa.terreno, eh_materia_prima=True
    )

    perfil = request.user.perfil
    perfil.sincronizar()
    if perfil.esta_internado():
        messages.error(request, f"Você está internado até {perfil.internado_ate:%d/%m %H:%M} e não pode trabalhar.")
        return redirect("empresas_detalhe", empresa_id=empresa.id)

    if not perfil.gastar_energia(CUSTO_DE_ENERGIA_TRABALHO):
        messages.error(
            request,
            f"Energia insuficiente pra produzir. Você precisa de {CUSTO_DE_ENERGIA_TRABALHO} "
            f"e tem {perfil.energia_atual}.",
        )
        return redirect("empresas_detalhe", empresa_id=empresa.id)

    quantidade_base = random.randint(PRODUCAO_MINIMA, PRODUCAO_MAXIMA)
    quantidade = max(1, round(quantidade_base * perfil.multiplicador_de_eficacia()))
    estoque, _ = EstoqueDaEmpresa.objects.get_or_create(empresa=empresa, produto=produto)
    estoque.quantidade += quantidade
    estoque.save(update_fields=["quantidade"])

    aviso_consumo = _consumir_operacional(empresa)

    mensagem = f"{empresa.nome} produziu {quantidade}x {produto.nome}."
    if aviso_consumo:
        mensagem += f" {aviso_consumo}"
    messages.success(request, mensagem)
    return redirect("empresas_detalhe", empresa_id=empresa.id)


@login_required
@require_POST
def fabricar(request, empresa_id):
    empresa = get_object_or_404(Empresa, id=empresa_id, tipo=TipoDeEmpresa.INDUSTRIAL)
    if not _pode_operar_empresa(request.user, empresa):
        messages.error(request, "Você precisa ser dono ou funcionário dessa empresa pra fabricar.")
        return redirect("empresas_detalhe", empresa_id=empresa.id)

    produto_final = get_object_or_404(
        Produto, id=request.POST.get("produto_id"),
        tipo_industria_produtor=empresa.tipo_industria, eh_materia_prima=False,
    )

    receitas = list(produto_final.receitas.select_related("ingrediente"))
    if not receitas:
        messages.error(request, f"{produto_final.nome} ainda não tem receita cadastrada.")
        return redirect("empresas_detalhe", empresa_id=empresa.id)

    estrela_exigida = max(receita.estrela_minima for receita in receitas)
    if empresa.estrelas < estrela_exigida:
        messages.error(
            request,
            f"{produto_final.nome} exige uma Industrial de {estrela_exigida}★ ou mais "
            f"(a {empresa.nome} tem {empresa.estrelas}★).",
        )
        return redirect("empresas_detalhe", empresa_id=empresa.id)

    # Confere se tem TODOS os ingredientes em quantidade suficiente antes de
    # consumir qualquer um — senão poderia gastar metade da receita e falhar
    # no meio, perdendo insumo à toa.
    estoques_dos_ingredientes = {}
    for receita in receitas:
        estoque_ing = EstoqueDaEmpresa.objects.filter(empresa=empresa, produto=receita.ingrediente).first()
        disponivel = estoque_ing.quantidade if estoque_ing else 0
        if disponivel < receita.quantidade_necessaria:
            messages.error(
                request,
                f"Falta {receita.ingrediente.nome}: precisa de {receita.quantidade_necessaria}, "
                f"tem {disponivel}.",
            )
            return redirect("empresas_detalhe", empresa_id=empresa.id)
        estoques_dos_ingredientes[receita] = estoque_ing

    perfil = request.user.perfil
    perfil.sincronizar()
    if perfil.esta_internado():
        messages.error(request, f"Você está internado até {perfil.internado_ate:%d/%m %H:%M} e não pode trabalhar.")
        return redirect("empresas_detalhe", empresa_id=empresa.id)

    if not perfil.gastar_energia(CUSTO_DE_ENERGIA_TRABALHO):
        messages.error(
            request,
            f"Energia insuficiente pra fabricar. Você precisa de {CUSTO_DE_ENERGIA_TRABALHO} "
            f"e tem {perfil.energia_atual}.",
        )
        return redirect("empresas_detalhe", empresa_id=empresa.id)

    for receita, estoque_ing in estoques_dos_ingredientes.items():
        estoque_ing.quantidade -= receita.quantidade_necessaria
        estoque_ing.save(update_fields=["quantidade"])

    quantidade_base = receitas[0].quantidade_produzida
    quantidade_produzida = max(1, round(quantidade_base * perfil.multiplicador_de_eficacia()))
    estoque_final, _ = EstoqueDaEmpresa.objects.get_or_create(empresa=empresa, produto=produto_final)
    estoque_final.quantidade += quantidade_produzida
    estoque_final.save(update_fields=["quantidade"])

    aviso_consumo = _consumir_operacional(empresa)

    mensagem = f"{empresa.nome} fabricou {quantidade_produzida}x {produto_final.nome}."
    if aviso_consumo:
        mensagem += f" {aviso_consumo}"
    messages.success(request, mensagem)
    return redirect("empresas_detalhe", empresa_id=empresa.id)


@login_required
@require_POST
def comprar_de_empresa(request, empresa_id):
    empresa_compradora = get_object_or_404(Empresa, id=empresa_id, dono=request.user)
    regras = REGRAS_DE_COMPRA.get(empresa_compradora.tipo, [])
    if not regras:
        messages.error(
            request, f"Empresas do tipo {empresa_compradora.get_tipo_display()} não compram de outras empresas."
        )
        return redirect("empresas_detalhe", empresa_id=empresa_compradora.id)

    empresa_vendedora = get_object_or_404(Empresa, id=request.POST.get("empresa_vendedora_id"))
    produto = get_object_or_404(Produto, id=request.POST.get("produto_id"))

    if empresa_vendedora.id == empresa_compradora.id:
        messages.error(request, "Uma empresa não pode comprar dela mesma.")
        return redirect("empresas_detalhe", empresa_id=empresa_compradora.id)

    # A compra só é válida se bater com ALGUMA das regras da empresa compradora
    # (tipo do vendedor certo + matéria-prima/manufaturado certo).
    compra_permitida = any(
        empresa_vendedora.tipo == regra["tipo_vendedor"] and produto.eh_materia_prima == regra["materia_prima"]
        for regra in regras
    )
    if not compra_permitida:
        messages.error(
            request,
            f"{empresa_compradora.get_tipo_display()} não pode comprar {produto.nome} de "
            f"{empresa_vendedora.get_tipo_display()}.",
        )
        return redirect("empresas_detalhe", empresa_id=empresa_compradora.id)

    try:
        quantidade = int(request.POST.get("quantidade", 0))
    except ValueError:
        quantidade = 0
    if quantidade <= 0:
        messages.error(request, "Quantidade inválida.")
        return redirect("empresas_detalhe", empresa_id=empresa_compradora.id)

    estoque_vendedor = EstoqueDaEmpresa.objects.filter(empresa=empresa_vendedora, produto=produto).first()
    disponivel = estoque_vendedor.quantidade if estoque_vendedor else 0
    if disponivel < quantidade:
        messages.error(request, f"{empresa_vendedora.nome} só tem {disponivel}x {produto.nome} disponível.")
        return redirect("empresas_detalhe", empresa_id=empresa_compradora.id)

    preco_total = produto.preco_base * quantidade
    perfil_comprador = request.user.perfil
    if perfil_comprador.dinheiro < preco_total:
        messages.error(request, f"Custa R$ {preco_total} e você só tem R$ {perfil_comprador.dinheiro}.")
        return redirect("empresas_detalhe", empresa_id=empresa_compradora.id)

    estoque_vendedor.quantidade -= quantidade
    estoque_vendedor.save(update_fields=["quantidade"])

    estoque_comprador, _ = EstoqueDaEmpresa.objects.get_or_create(empresa=empresa_compradora, produto=produto)
    estoque_comprador.quantidade += quantidade
    estoque_comprador.save(update_fields=["quantidade"])

    perfil_comprador.dinheiro -= preco_total
    perfil_comprador.save(update_fields=["dinheiro"])

    perfil_vendedor = empresa_vendedora.dono.perfil
    perfil_vendedor.dinheiro += preco_total
    perfil_vendedor.save(update_fields=["dinheiro"])

    messages.success(
        request, f"{empresa_compradora.nome} comprou {quantidade}x {produto.nome} de {empresa_vendedora.nome} por R$ {preco_total}."
    )
    return redirect("empresas_detalhe", empresa_id=empresa_compradora.id)


def mercado(request):
    itens = EstoqueDaEmpresa.objects.filter(
        empresa__tipo=TipoDeEmpresa.VAREJO, quantidade__gt=0
    ).select_related("empresa", "produto")
    return render(request, "empresas/mercado.html", {"itens": itens})


@login_required
@require_POST
def comprar_do_mercado(request, estoque_id):
    estoque = get_object_or_404(
        EstoqueDaEmpresa.objects.select_related("empresa", "produto"),
        id=estoque_id,
        empresa__tipo=TipoDeEmpresa.VAREJO,
    )
    try:
        quantidade = int(request.POST.get("quantidade", 1))
    except ValueError:
        quantidade = 0
    if quantidade <= 0 or quantidade > estoque.quantidade:
        messages.error(request, "Quantidade inválida ou indisponível.")
        return redirect("empresas_mercado")

    preco_total = estoque.produto.preco_base * quantidade
    perfil = request.user.perfil
    if perfil.dinheiro < preco_total:
        messages.error(request, f"Custa R$ {preco_total}, você só tem R$ {perfil.dinheiro}.")
        return redirect("empresas_mercado")

    estoque.quantidade -= quantidade
    estoque.save(update_fields=["quantidade"])

    perfil.dinheiro -= preco_total
    perfil.save(update_fields=["dinheiro"])

    perfil_vendedor = estoque.empresa.dono.perfil
    perfil_vendedor.dinheiro += preco_total
    perfil_vendedor.save(update_fields=["dinheiro"])

    item, _ = ItemDoJogador.objects.get_or_create(usuario=request.user, produto=estoque.produto)
    item.quantidade += quantidade
    item.save(update_fields=["quantidade"])

    messages.success(request, f"Comprou {quantidade}x {estoque.produto.nome} por R$ {preco_total}. Foi pro seu inventário.")
    return redirect("empresas_mercado")
