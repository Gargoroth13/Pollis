import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from geography.models import Bairro

# A cada quantos minutos o jogador recupera 1 ponto de energia (na taxa
# base — o efetivo muda com o QoL, ver _sincronizar_energia) ou 1 ponto
# de saúde (quando QoL >= 1).
MINUTOS_POR_PONTO_DE_ENERGIA = 3
MINUTOS_POR_PONTO_DE_SAUDE = 10

# A cada quantos minutos a nutrição cai 1 ponto sozinha (só sobe comendo).
MINUTOS_POR_PONTO_DE_NUTRICAO_PERDIDA = 15

# A cada quantos minutos o QoL anda 1 passo em direção à sua base.
MINUTOS_POR_PASSO_DE_QOL = 60
INCREMENTO_DE_QOL_POR_PASSO = Decimal("0.05")

# Quanto QoL cada clique de trabalhar/produzir/fabricar/estudar consome.
CUSTO_DE_QOL_POR_ACAO = Decimal("0.20")

# Patamares de saúde que entram/saem do estado de depressão. Usa dois
# valores diferentes (histerese) pra não ficar entrando e saindo toda
# hora bem em cima do limite.
SAUDE_PARA_ENTRAR_EM_DEPRESSAO = 20
SAUDE_PARA_SAIR_DA_DEPRESSAO = 30

DIAS_DE_INTERNACAO = 3


class Usuario(AbstractUser):
    """
    Usamos um User customizado desde o início (mesmo sem mudar nada ainda)
    porque trocar isso depois de o banco já ter dados reais é bem doloroso.
    Campos específicos do jogo (energia, dinheiro, bairro...) ficam no Perfil,
    não aqui — isso mantém autenticação separada de dados de gameplay.
    """

    pass


class Perfil(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name="perfil")
    bairro = models.ForeignKey(Bairro, on_delete=models.PROTECT, related_name="moradores")

    dinheiro = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    energia_atual = models.PositiveSmallIntegerField(default=100)
    energia_maxima = models.PositiveSmallIntegerField(default=100)

    saude_atual = models.PositiveSmallIntegerField(default=100)
    saude_maxima = models.PositiveSmallIntegerField(default=100)

    nutricao_atual = models.PositiveSmallIntegerField(default=100)
    nutricao_maxima = models.PositiveSmallIntegerField(default=100)

    # QoL pessoal (DESIGN.md seção 5.2) — diferente da QoL do bairro
    # (Bairro.qualidade_vida). `qol_base` hoje é sempre 1.00 pra todo
    # mundo porque ainda não existe posse de imóvel/carro/roupa
    # (a seção 5.2 diz que esses bens deveriam definir a base) — quando
    # esse sistema existir, é só passar a calcular `qol_base` a partir
    # dele em vez do valor fixo.
    qol_atual = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.00"))
    qol_base = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.00"))

    em_depressao = models.BooleanField(default=False)
    internado_ate = models.DateTimeField(null=True, blank=True)

    # Cada recurso tem seu próprio "relógio". Isso evita ter que fazer
    # malabarismo pra combinar taxas diferentes num timestamp só.
    ultima_sync_energia = models.DateTimeField(default=timezone.now)
    ultima_sync_saude = models.DateTimeField(default=timezone.now)
    ultima_sync_nutricao = models.DateTimeField(default=timezone.now)
    ultima_sync_qol = models.DateTimeField(default=timezone.now)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfis"

    def __str__(self):
        return f"Perfil de {self.usuario.username}"

    # ---------- utilitários genéricos ----------

    def _regenerar(self, campo_atual, campo_maximo, campo_timestamp, minutos_por_ponto):
        """
        Regeneração "sob demanda" genérica: calcula quantos pontos
        inteiros já deveriam ter regenerado desde o último timestamp
        salvo, aplica o ganho, e avança o timestamp só pelo tempo já
        convertido em pontos (o restante da fração de minuto continua
        contando pra próxima vez). `minutos_por_ponto` pode ser float.
        """
        atual = getattr(self, campo_atual)
        maximo = getattr(self, campo_maximo)
        ultimo_timestamp = getattr(self, campo_timestamp)

        if atual >= maximo:
            setattr(self, campo_timestamp, timezone.now())
            return

        minutos_passados = (timezone.now() - ultimo_timestamp).total_seconds() / 60
        pontos_ganhos = int(minutos_passados // minutos_por_ponto)

        if pontos_ganhos <= 0:
            return

        novo_valor = min(maximo, atual + pontos_ganhos)
        setattr(self, campo_atual, novo_valor)
        setattr(self, campo_timestamp, ultimo_timestamp + timedelta(minutes=pontos_ganhos * minutos_por_ponto))

    # ---------- QoL ----------

    def qol_base_efetiva(self):
        """
        O "alvo" que o QoL atual persegue. Cai pela metade em depressão;
        e fica travado num teto de 60% da base se a nutrição zerou —
        ambos usando a mesma lógica de "persegue um alvo mais baixo"
        em vez de precisar de código separado pra cada caso.
        """
        base = self.qol_base / 2 if self.em_depressao else self.qol_base
        if self.nutricao_atual <= 0:
            base = min(base, self.qol_base * Decimal("0.6"))
        return base

    def _sincronizar_qol(self):
        agora = timezone.now()
        minutos_passados = (agora - self.ultima_sync_qol).total_seconds() / 60
        passos = int(minutos_passados // MINUTOS_POR_PASSO_DE_QOL)
        if passos <= 0:
            return

        alvo = self.qol_base_efetiva()
        incremento = INCREMENTO_DE_QOL_POR_PASSO * passos
        if self.qol_atual < alvo:
            self.qol_atual = min(alvo, self.qol_atual + incremento)
        elif self.qol_atual > alvo:
            self.qol_atual = max(alvo, self.qol_atual - incremento)

        self.ultima_sync_qol = self.ultima_sync_qol + timedelta(minutes=passos * MINUTOS_POR_PASSO_DE_QOL)

    def gastar_qol(self, quantidade=CUSTO_DE_QOL_POR_ACAO):
        """Chamado por ações de trabalho/estudo — dreno instantâneo, não é regeneração."""
        self.qol_atual = max(Decimal("0"), self.qol_atual - Decimal(str(quantidade)))

    def multiplicador_de_eficacia(self):
        """QoL vira multiplicador de ganho de skill/produção (DESIGN.md seção 1.2, versão simplificada sem escola ainda)."""
        return float(self.qol_atual)

    # ---------- energia ----------

    def _sincronizar_energia(self):
        # QoL alto regenera energia mais rápido; QoL baixo, mais devagar
        # (fórmula já fechada no DESIGN.md seção 5.2).
        qol_para_calculo = max(self.qol_atual, Decimal("0.1"))  # evita divisão por zero/taxa absurda
        minutos_por_ponto_efetivo = MINUTOS_POR_PONTO_DE_ENERGIA / float(qol_para_calculo)
        self._regenerar("energia_atual", "energia_maxima", "ultima_sync_energia", minutos_por_ponto_efetivo)

    # ---------- saúde ----------

    def _sincronizar_saude(self):
        agora = timezone.now()
        minutos_passados = (agora - self.ultima_sync_saude).total_seconds() / 60
        ticks = int(minutos_passados // MINUTOS_POR_PONTO_DE_SAUDE)
        if ticks > 0:
            for _ in range(ticks):
                if self.qol_atual >= 1:
                    if self.saude_atual < self.saude_maxima:
                        self.saude_atual += 1
                else:
                    # Quanto mais baixo o QoL (abaixo de 1), maior a chance de piorar.
                    chance_de_piorar = min(Decimal("0.5"), (Decimal("1") - self.qol_atual) * Decimal("0.5"))
                    if self.saude_atual > 0 and random.random() < float(chance_de_piorar):
                        self.saude_atual -= 1

            self.ultima_sync_saude = self.ultima_sync_saude + timedelta(minutes=ticks * MINUTOS_POR_PONTO_DE_SAUDE)

        # Histerese de depressão.
        if not self.em_depressao and self.saude_atual <= SAUDE_PARA_ENTRAR_EM_DEPRESSAO:
            self.em_depressao = True
        elif self.em_depressao and self.saude_atual > SAUDE_PARA_SAIR_DA_DEPRESSAO:
            self.em_depressao = False

        # Internação automática ao zerar a saúde.
        if self.saude_atual <= 0 and not self.esta_internado():
            self.internado_ate = timezone.now() + timedelta(days=DIAS_DE_INTERNACAO)

    def esta_internado(self):
        return bool(self.internado_ate and timezone.now() < self.internado_ate)

    # ---------- nutrição ----------

    def _sincronizar_nutricao(self):
        agora = timezone.now()
        minutos_passados = (agora - self.ultima_sync_nutricao).total_seconds() / 60
        pontos_perdidos = int(minutos_passados // MINUTOS_POR_PONTO_DE_NUTRICAO_PERDIDA)
        if pontos_perdidos <= 0:
            return
        self.nutricao_atual = max(0, self.nutricao_atual - pontos_perdidos)
        self.ultima_sync_nutricao = self.ultima_sync_nutricao + timedelta(
            minutes=pontos_perdidos * MINUTOS_POR_PONTO_DE_NUTRICAO_PERDIDA
        )

    def comer(self, nutricao_ganha, efeito_qol):
        """
        Aplica o efeito de consumir um item de alimento (chamado pela
        view de inventário). Nutrição nunca passa do máximo; QoL nunca
        passa da própria base (bônus de lazer que ultrapassa a base
        fica pra quando esse sistema existir).
        """
        self.nutricao_atual = min(self.nutricao_maxima, self.nutricao_atual + nutricao_ganha)
        novo_qol = self.qol_atual + Decimal(str(efeito_qol))
        self.qol_atual = max(Decimal("0"), min(self.qol_base, novo_qol))

    # ---------- ponto de entrada único ----------

    def sincronizar(self):
        """
        Atualiza todas as barras com base no tempo decorrido, e salva se
        algo mudou. A ordem importa: saúde e nutrição primeiro (porque
        QoL persegue um alvo que depende delas), QoL depois, energia por
        último (porque a taxa dela depende do QoL já atualizado).
        """
        antes = (
            self.energia_atual, self.saude_atual, self.nutricao_atual,
            self.qol_atual, self.em_depressao, self.internado_ate,
        )

        self._sincronizar_saude()
        self._sincronizar_nutricao()
        self._sincronizar_qol()
        self._sincronizar_energia()

        depois = (
            self.energia_atual, self.saude_atual, self.nutricao_atual,
            self.qol_atual, self.em_depressao, self.internado_ate,
        )
        if antes != depois:
            self.save(update_fields=[
                "energia_atual", "ultima_sync_energia",
                "saude_atual", "ultima_sync_saude",
                "nutricao_atual", "ultima_sync_nutricao",
                "qol_atual", "ultima_sync_qol",
                "em_depressao", "internado_ate",
            ])

    def gastar_energia(self, quantidade):
        """
        Tenta gastar energia. Retorna True se conseguiu, False se não tinha
        energia suficiente. Sempre sincroniza antes de checar o saldo.
        """
        self.sincronizar()
        if self.energia_atual < quantidade:
            return False
        self.energia_atual -= quantidade
        self.gastar_qol()
        self.save(update_fields=["energia_atual", "qol_atual"])
        return True


class ItemDoJogador(models.Model):
    """
    Inventário do jogador. Comprar no Mercado (Varejo) passa a alimentar
    isso, em vez de só transferir dinheiro — é o que falta pra "comer"
    um item de comida fazer sentido de verdade.
    """

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="itens")
    produto = models.ForeignKey("empresas.Produto", on_delete=models.PROTECT, related_name="em_inventario_de")
    quantidade = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Item do jogador"
        verbose_name_plural = "Itens dos jogadores"
        unique_together = ("usuario", "produto")
        ordering = ["produto__nome"]

    def __str__(self):
        return f"{self.usuario.username}: {self.quantidade}x {self.produto.nome}"
