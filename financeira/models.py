from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

# Percentual mínimo do total devido aos clientes que a Financeira precisa
# manter em caixa. Abaixo disso, ela já está em risco de insolvência.
RESERVA_OBRIGATORIA = Decimal("0.20")

JUROS_SEMANAIS_DA_POUPANCA = Decimal("0.01")  # 1% ao ser capitalizado (cada 7 dias)
DIAS_POR_CAPITALIZACAO_POUPANCA = 7

JUROS_MENSAIS_DO_CARTAO = Decimal("0.10")  # 10% ao mês, DESIGN.md seção 2.8
DIAS_POR_CAPITALIZACAO_CARTAO = 30

TAXA_DE_TRANSFERENCIA = Decimal("0.02")  # 2%, cobrada só pela Financeira intermediária

DIAS_DE_BLOQUEIO_POS_FALENCIA = 30
PERDA_POS_FALENCIA = Decimal("0.30")  # 30%, DESIGN.md seção 2.8


class DadosFinanceiros(models.Model):
    """
    Extensão de uma Empresa (Serviços, especialização Financeira) com o
    que só faz sentido pra uma instituição financeira: caixa segregado
    do dinheiro pessoal do dono (é isso que torna a reserva obrigatória
    uma restrição de verdade, não só decorativa) e o estado de falência.
    """

    empresa = models.OneToOneField(
        "empresas.Empresa", on_delete=models.CASCADE, related_name="dados_financeiros"
    )
    caixa = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    falida = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Dados financeiros"
        verbose_name_plural = "Dados financeiros"

    def __str__(self):
        return f"Dados financeiros de {self.empresa.nome}"

    def obrigacoes_totais(self):
        total = self.empresa.poupancas.aggregate(soma=models.Sum("saldo"))["soma"]
        return total or Decimal("0")

    def indice_de_reserva(self):
        """1.00 = caixa cobre 100% do que é devido aos clientes. Sem cliente nenhum, sempre 1.00."""
        obrigacoes = self.obrigacoes_totais()
        if obrigacoes == 0:
            return Decimal("1.00")
        return (self.caixa / obrigacoes).quantize(Decimal("0.01"))

    def rating(self):
        indice = self.indice_de_reserva()
        if indice >= 1:
            return "A"
        if indice >= Decimal("0.6"):
            return "B"
        if indice >= Decimal("0.4"):
            return "C"
        if indice >= RESERVA_OBRIGATORIA:
            return "D"
        return "F"

    def pode_sacar_do_caixa(self, valor):
        """
        Reserva obrigatória de verdade: não deixa o caixa cair abaixo de
        20% das obrigações totais depois da saída. Usado antes de
        qualquer saque, empréstimo novo ou saque de cartão.
        """
        obrigacoes = self.obrigacoes_totais()
        caixa_minimo_exigido = obrigacoes * RESERVA_OBRIGATORIA
        return (self.caixa - valor) >= caixa_minimo_exigido


class Poupanca(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="poupancas")
    financeira = models.ForeignKey(
        "empresas.Empresa", on_delete=models.CASCADE, related_name="poupancas"
    )
    saldo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    ultima_capitalizacao = models.DateTimeField(default=timezone.now)
    bloqueado_ate = models.DateTimeField(null=True, blank=True, help_text="Setado quando a Financeira quebra.")

    class Meta:
        verbose_name = "Poupança"
        verbose_name_plural = "Poupanças"
        unique_together = ("usuario", "financeira")

    def __str__(self):
        return f"Poupança de {self.usuario.username} na {self.financeira.nome}: R$ {self.saldo}"

    def esta_bloqueada(self):
        return bool(self.bloqueado_ate and timezone.now() < self.bloqueado_ate)

    def sincronizar(self):
        """Juros semanais capitalizados sob demanda — mesmo padrão de energia/QoL do resto do projeto."""
        agora = timezone.now()
        dias_passados = (agora - self.ultima_capitalizacao).total_seconds() / 86400
        capitalizacoes = int(dias_passados // DIAS_POR_CAPITALIZACAO_POUPANCA)
        if capitalizacoes <= 0 or self.saldo <= 0:
            return
        self.saldo = (self.saldo * (1 + JUROS_SEMANAIS_DA_POUPANCA) ** capitalizacoes).quantize(Decimal("0.01"))
        self.ultima_capitalizacao += timedelta(days=capitalizacoes * DIAS_POR_CAPITALIZACAO_POUPANCA)
        self.save(update_fields=["saldo", "ultima_capitalizacao"])


class Emprestimo(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="emprestimos")
    financeira = models.ForeignKey(
        "empresas.Empresa", on_delete=models.CASCADE, related_name="emprestimos"
    )
    valor_original = models.DecimalField(max_digits=12, decimal_places=2)
    saldo_devedor = models.DecimalField(max_digits=12, decimal_places=2)
    taxa_juros = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("0.05"))
    criado_em = models.DateTimeField(auto_now_add=True)
    quitado = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Empréstimo"
        verbose_name_plural = "Empréstimos"

    def __str__(self):
        status = "quitado" if self.quitado else f"devendo R$ {self.saldo_devedor}"
        return f"Empréstimo de {self.usuario.username} na {self.financeira.nome} ({status})"


class CartaoDeCredito(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cartoes")
    financeira = models.ForeignKey(
        "empresas.Empresa", on_delete=models.CASCADE, related_name="cartoes"
    )
    limite = models.DecimalField(max_digits=12, decimal_places=2)
    saldo_devedor = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    ultima_capitalizacao = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Cartão de crédito"
        verbose_name_plural = "Cartões de crédito"
        unique_together = ("usuario", "financeira")

    def __str__(self):
        return f"Cartão de {self.usuario.username} na {self.financeira.nome}: devendo R$ {self.saldo_devedor}"

    def limite_disponivel(self):
        return max(Decimal("0"), self.limite - self.saldo_devedor)

    def pagamento_minimo(self):
        if self.saldo_devedor <= 0:
            return Decimal("0")
        minimo = (self.saldo_devedor * Decimal("0.10")).quantize(Decimal("0.01"))
        return max(minimo, min(self.saldo_devedor, Decimal("10.00")))

    def sincronizar(self):
        """Juros compostos mensais sobre o saldo devedor — capitalizado sob demanda."""
        agora = timezone.now()
        dias_passados = (agora - self.ultima_capitalizacao).total_seconds() / 86400
        capitalizacoes = int(dias_passados // DIAS_POR_CAPITALIZACAO_CARTAO)
        if capitalizacoes <= 0 or self.saldo_devedor <= 0:
            return
        self.saldo_devedor = (
            self.saldo_devedor * (1 + JUROS_MENSAIS_DO_CARTAO) ** capitalizacoes
        ).quantize(Decimal("0.01"))
        self.ultima_capitalizacao += timedelta(days=capitalizacoes * DIAS_POR_CAPITALIZACAO_CARTAO)
        self.save(update_fields=["saldo_devedor", "ultima_capitalizacao"])
