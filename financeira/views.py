from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.timezone import timedelta
from django.views.decorators.http import require_POST

from core.models import RegistroDeTrabalho
from empresas.models import EspecializacaoDeServico, Empresa
from skills.models import HabilidadeDoJogador, Skill

from .models import (
    DIAS_DE_BLOQUEIO_POS_FALENCIA, PERDA_POS_FALENCIA, TAXA_DE_TRANSFERENCIA,
    CartaoDeCredito, DadosFinanceiros, Emprestimo, Poupanca,
)

Usuario = get_user_model()

TAXA_DE_JUROS_DO_EMPRESTIMO = Decimal("0.05")


def _valor_do_post(request, campo="valor"):
    try:
        valor = Decimal(request.POST.get(campo, "0"))
    except InvalidOperation:
        return Decimal("0")
    return valor if valor > 0 else Decimal("0")


def calcular_limite_de_cartao(usuario):
    """Limite = skill Carisma × 20 + renda recente (soma dos últimos 10 ganhos de trabalho)."""
    habilidade_carisma = HabilidadeDoJogador.objects.filter(usuario=usuario, skill=Skill.CARISMA).first()
    nivel_carisma = habilidade_carisma.nivel if habilidade_carisma else 0

    renda_recente = RegistroDeTrabalho.objects.filter(usuario=usuario).order_by("-quando")[:10].aggregate(
        soma=models.Sum("dinheiro_ganho")
    )["soma"] or Decimal("0")

    limite = Decimal(nivel_carisma * 20) + renda_recente
    return limite.quantize(Decimal("0.01"))


def detalhe(request, empresa_id):
    empresa = get_object_or_404(
        Empresa.objects.select_related("dono"),
        id=empresa_id, especializacao_servico=EspecializacaoDeServico.FINANCEIRA,
    )
    dados, _ = DadosFinanceiros.objects.get_or_create(empresa=empresa)
    eh_dono = request.user.is_authenticated and request.user.id == empresa.dono_id

    poupanca = emprestimo = cartao = None
    if request.user.is_authenticated:
        poupanca = Poupanca.objects.filter(usuario=request.user, financeira=empresa).first()
        if poupanca:
            poupanca.sincronizar()
        emprestimo = Emprestimo.objects.filter(usuario=request.user, financeira=empresa, quitado=False).first()
        cartao = CartaoDeCredito.objects.filter(usuario=request.user, financeira=empresa).first()
        if cartao:
            cartao.sincronizar()

    return render(request, "financeira/detalhe.html", {
        "empresa": empresa,
        "dados": dados,
        "eh_dono": eh_dono,
        "poupanca": poupanca,
        "emprestimo": emprestimo,
        "cartao": cartao,
    })


@login_required
@require_POST
def depositar(request, empresa_id):
    empresa = get_object_or_404(Empresa, id=empresa_id, especializacao_servico=EspecializacaoDeServico.FINANCEIRA)
    dados, _ = DadosFinanceiros.objects.get_or_create(empresa=empresa)
    if dados.falida:
        messages.error(request, "Essa financeira está falida e não aceita depósitos.")
        return redirect("financeira_detalhe", empresa_id=empresa.id)

    valor = _valor_do_post(request)
    perfil = request.user.perfil
    if valor <= 0 or valor > perfil.dinheiro:
        messages.error(request, "Valor inválido ou saldo insuficiente.")
        return redirect("financeira_detalhe", empresa_id=empresa.id)

    perfil.dinheiro -= valor
    perfil.save(update_fields=["dinheiro"])

    poupanca, _ = Poupanca.objects.get_or_create(usuario=request.user, financeira=empresa)
    poupanca.sincronizar()
    poupanca.saldo += valor
    poupanca.save(update_fields=["saldo"])

    dados.caixa += valor
    dados.save(update_fields=["caixa"])

    messages.success(request, f"Depositou R$ {valor} na poupança de {empresa.nome}.")
    return redirect("financeira_detalhe", empresa_id=empresa.id)


@login_required
@require_POST
def sacar(request, empresa_id):
    empresa = get_object_or_404(Empresa, id=empresa_id, especializacao_servico=EspecializacaoDeServico.FINANCEIRA)
    poupanca = get_object_or_404(Poupanca, usuario=request.user, financeira=empresa)
    poupanca.sincronizar()

    if poupanca.esta_bloqueada():
        messages.error(request, f"Saldo bloqueado até {poupanca.bloqueado_ate:%d/%m %H:%M} (a financeira faliu).")
        return redirect("financeira_detalhe", empresa_id=empresa.id)

    valor = _valor_do_post(request)
    if valor <= 0 or valor > poupanca.saldo:
        messages.error(request, "Valor inválido.")
        return redirect("financeira_detalhe", empresa_id=empresa.id)

    dados = empresa.dados_financeiros
    if not dados.pode_sacar_do_caixa(valor):
        messages.error(
            request,
            f"{empresa.nome} não tem caixa suficiente pra esse saque sem violar a reserva obrigatória de 20%.",
        )
        return redirect("financeira_detalhe", empresa_id=empresa.id)

    poupanca.saldo -= valor
    poupanca.save(update_fields=["saldo"])
    dados.caixa -= valor
    dados.save(update_fields=["caixa"])

    perfil = request.user.perfil
    perfil.dinheiro += valor
    perfil.save(update_fields=["dinheiro"])

    messages.success(request, f"Sacou R$ {valor} da poupança.")
    return redirect("financeira_detalhe", empresa_id=empresa.id)


@login_required
@require_POST
def pedir_emprestimo(request, empresa_id):
    empresa = get_object_or_404(Empresa, id=empresa_id, especializacao_servico=EspecializacaoDeServico.FINANCEIRA)
    dados, _ = DadosFinanceiros.objects.get_or_create(empresa=empresa)
    if dados.falida:
        messages.error(request, "Essa financeira está falida.")
        return redirect("financeira_detalhe", empresa_id=empresa.id)

    if Emprestimo.objects.filter(usuario=request.user, financeira=empresa, quitado=False).exists():
        messages.error(request, "Você já tem um empréstimo em aberto com essa financeira.")
        return redirect("financeira_detalhe", empresa_id=empresa.id)

    valor = _valor_do_post(request)
    if valor <= 0:
        messages.error(request, "Valor inválido.")
        return redirect("financeira_detalhe", empresa_id=empresa.id)

    if not dados.pode_sacar_do_caixa(valor):
        messages.error(
            request,
            f"{empresa.nome} não tem caixa suficiente pra esse empréstimo sem violar a reserva obrigatória de 20%.",
        )
        return redirect("financeira_detalhe", empresa_id=empresa.id)

    saldo_devedor = (valor * (1 + TAXA_DE_JUROS_DO_EMPRESTIMO)).quantize(Decimal("0.01"))
    Emprestimo.objects.create(
        usuario=request.user, financeira=empresa, valor_original=valor,
        saldo_devedor=saldo_devedor, taxa_juros=TAXA_DE_JUROS_DO_EMPRESTIMO,
    )
    dados.caixa -= valor
    dados.save(update_fields=["caixa"])

    perfil = request.user.perfil
    perfil.dinheiro += valor
    perfil.save(update_fields=["dinheiro"])

    messages.success(
        request,
        f"Empréstimo de R$ {valor} aprovado (juros de {TAXA_DE_JUROS_DO_EMPRESTIMO * 100}%, total a pagar: R$ {saldo_devedor}).",
    )
    return redirect("financeira_detalhe", empresa_id=empresa.id)


@login_required
@require_POST
def pagar_emprestimo(request, empresa_id):
    empresa = get_object_or_404(Empresa, id=empresa_id, especializacao_servico=EspecializacaoDeServico.FINANCEIRA)
    emprestimo = get_object_or_404(Emprestimo, usuario=request.user, financeira=empresa, quitado=False)

    valor = _valor_do_post(request)
    perfil = request.user.perfil
    if valor <= 0 or valor > perfil.dinheiro:
        messages.error(request, "Valor inválido ou saldo insuficiente.")
        return redirect("financeira_detalhe", empresa_id=empresa.id)

    valor = min(valor, emprestimo.saldo_devedor)
    perfil.dinheiro -= valor
    perfil.save(update_fields=["dinheiro"])

    emprestimo.saldo_devedor -= valor
    if emprestimo.saldo_devedor <= 0:
        emprestimo.saldo_devedor = Decimal("0")
        emprestimo.quitado = True
    emprestimo.save(update_fields=["saldo_devedor", "quitado"])

    dados = empresa.dados_financeiros
    dados.caixa += valor
    dados.save(update_fields=["caixa"])

    mensagem = f"Pagou R$ {valor} do empréstimo."
    mensagem += " Quitado!" if emprestimo.quitado else f" Resta R$ {emprestimo.saldo_devedor}."
    messages.success(request, mensagem)
    return redirect("financeira_detalhe", empresa_id=empresa.id)


@login_required
@require_POST
def pedir_cartao(request, empresa_id):
    empresa = get_object_or_404(Empresa, id=empresa_id, especializacao_servico=EspecializacaoDeServico.FINANCEIRA)
    dados, _ = DadosFinanceiros.objects.get_or_create(empresa=empresa)
    if dados.falida:
        messages.error(request, "Essa financeira está falida.")
        return redirect("financeira_detalhe", empresa_id=empresa.id)

    if CartaoDeCredito.objects.filter(usuario=request.user, financeira=empresa).exists():
        messages.error(request, "Você já tem um cartão dessa financeira.")
        return redirect("financeira_detalhe", empresa_id=empresa.id)

    limite = calcular_limite_de_cartao(request.user)
    CartaoDeCredito.objects.create(usuario=request.user, financeira=empresa, limite=limite)
    messages.success(request, f"Cartão aprovado com limite de R$ {limite}.")
    return redirect("financeira_detalhe", empresa_id=empresa.id)


@login_required
@require_POST
def sacar_cartao(request, empresa_id):
    empresa = get_object_or_404(Empresa, id=empresa_id, especializacao_servico=EspecializacaoDeServico.FINANCEIRA)
    cartao = get_object_or_404(CartaoDeCredito, usuario=request.user, financeira=empresa)
    cartao.sincronizar()

    dados = empresa.dados_financeiros
    if dados.falida:
        messages.error(request, "Essa financeira está falida.")
        return redirect("financeira_detalhe", empresa_id=empresa.id)

    valor = _valor_do_post(request)
    limite_disponivel = cartao.limite_disponivel()
    if valor <= 0 or valor > limite_disponivel:
        messages.error(request, f"Valor inválido. Limite disponível: R$ {limite_disponivel}.")
        return redirect("financeira_detalhe", empresa_id=empresa.id)

    if not dados.pode_sacar_do_caixa(valor):
        messages.error(
            request,
            f"{empresa.nome} não tem caixa suficiente pra esse saque sem violar a reserva obrigatória de 20%.",
        )
        return redirect("financeira_detalhe", empresa_id=empresa.id)

    cartao.saldo_devedor += valor
    cartao.save(update_fields=["saldo_devedor"])
    dados.caixa -= valor
    dados.save(update_fields=["caixa"])

    perfil = request.user.perfil
    perfil.dinheiro += valor
    perfil.save(update_fields=["dinheiro"])

    messages.success(request, f"Sacou R$ {valor} no cartão. Saldo devedor agora: R$ {cartao.saldo_devedor}.")
    return redirect("financeira_detalhe", empresa_id=empresa.id)


@login_required
@require_POST
def pagar_cartao(request, empresa_id):
    empresa = get_object_or_404(Empresa, id=empresa_id, especializacao_servico=EspecializacaoDeServico.FINANCEIRA)
    cartao = get_object_or_404(CartaoDeCredito, usuario=request.user, financeira=empresa)
    cartao.sincronizar()

    if request.POST.get("modo") == "minimo":
        valor = cartao.pagamento_minimo()
    else:
        valor = _valor_do_post(request)

    perfil = request.user.perfil
    if valor <= 0 or valor > perfil.dinheiro:
        messages.error(request, "Valor inválido ou saldo insuficiente.")
        return redirect("financeira_detalhe", empresa_id=empresa.id)

    valor = min(valor, cartao.saldo_devedor)
    perfil.dinheiro -= valor
    perfil.save(update_fields=["dinheiro"])

    cartao.saldo_devedor -= valor
    cartao.save(update_fields=["saldo_devedor"])

    dados = empresa.dados_financeiros
    dados.caixa += valor
    dados.save(update_fields=["caixa"])

    messages.success(request, f"Pagou R$ {valor} do cartão. Saldo devedor agora: R$ {cartao.saldo_devedor}.")
    return redirect("financeira_detalhe", empresa_id=empresa.id)


@login_required
@require_POST
def transferir(request, empresa_id):
    empresa = get_object_or_404(Empresa, id=empresa_id, especializacao_servico=EspecializacaoDeServico.FINANCEIRA)

    username_destino = request.POST.get("username", "").strip()
    destinatario = Usuario.objects.filter(username=username_destino).first()
    if destinatario is None:
        messages.error(request, f"Não existe jogador com o username '{username_destino}'.")
        return redirect("financeira_detalhe", empresa_id=empresa.id)
    if destinatario.id == request.user.id:
        messages.error(request, "Não dá pra transferir pra você mesmo.")
        return redirect("financeira_detalhe", empresa_id=empresa.id)

    valor = _valor_do_post(request)
    taxa = (valor * TAXA_DE_TRANSFERENCIA).quantize(Decimal("0.01"))
    total_debitado = valor + taxa

    perfil = request.user.perfil
    if valor <= 0 or total_debitado > perfil.dinheiro:
        messages.error(request, f"Valor inválido ou saldo insuficiente (precisa de R$ {total_debitado} com a taxa).")
        return redirect("financeira_detalhe", empresa_id=empresa.id)

    perfil.dinheiro -= total_debitado
    perfil.save(update_fields=["dinheiro"])

    perfil_destino = destinatario.perfil
    perfil_destino.dinheiro += valor
    perfil_destino.save(update_fields=["dinheiro"])

    perfil_financeira = empresa.dono.perfil
    perfil_financeira.dinheiro += taxa
    perfil_financeira.save(update_fields=["dinheiro"])

    messages.success(
        request, f"Transferiu R$ {valor} pra {destinatario.username} (taxa de R$ {taxa} pra {empresa.nome})."
    )
    return redirect("financeira_detalhe", empresa_id=empresa.id)


@login_required
@require_POST
def capitalizar(request, empresa_id):
    empresa = get_object_or_404(
        Empresa, id=empresa_id, dono=request.user, especializacao_servico=EspecializacaoDeServico.FINANCEIRA
    )
    dados, _ = DadosFinanceiros.objects.get_or_create(empresa=empresa)

    valor = _valor_do_post(request)
    perfil = request.user.perfil
    if valor <= 0 or valor > perfil.dinheiro:
        messages.error(request, "Valor inválido ou saldo insuficiente.")
        return redirect("financeira_detalhe", empresa_id=empresa.id)

    perfil.dinheiro -= valor
    perfil.save(update_fields=["dinheiro"])
    dados.caixa += valor
    dados.save(update_fields=["caixa"])

    messages.success(request, f"Capitalizou {empresa.nome} com R$ {valor}.")
    return redirect("financeira_detalhe", empresa_id=empresa.id)


@login_required
@require_POST
def declarar_falencia(request, empresa_id):
    empresa = get_object_or_404(
        Empresa, id=empresa_id, dono=request.user, especializacao_servico=EspecializacaoDeServico.FINANCEIRA
    )
    dados, _ = DadosFinanceiros.objects.get_or_create(empresa=empresa)
    if dados.falida:
        messages.error(request, "Essa financeira já está falida.")
        return redirect("financeira_detalhe", empresa_id=empresa.id)

    bloqueio_ate = timezone.now() + timedelta(days=DIAS_DE_BLOQUEIO_POS_FALENCIA)
    for poupanca in Poupanca.objects.filter(financeira=empresa, saldo__gt=0):
        poupanca.saldo = (poupanca.saldo * (1 - PERDA_POS_FALENCIA)).quantize(Decimal("0.01"))
        poupanca.bloqueado_ate = bloqueio_ate
        poupanca.save(update_fields=["saldo", "bloqueado_ate"])

    dados.caixa = Decimal("0")
    dados.falida = True
    dados.save(update_fields=["caixa", "falida"])

    messages.success(
        request,
        f"{empresa.nome} declarou falência. Depositantes recebem 70% do saldo, liberado em {DIAS_DE_BLOQUEIO_POS_FALENCIA} dias.",
    )
    return redirect("financeira_detalhe", empresa_id=empresa.id)
