from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from geography.models import Bairro

# A cada quantos minutos o jogador recupera 1 ponto de energia/saúde.
# Ajustar esse número é a forma mais simples de deixar o jogo mais rápido ou mais lento.
MINUTOS_POR_PONTO_DE_ENERGIA = 3
MINUTOS_POR_PONTO_DE_SAUDE = 10


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

    # Cada recurso tem seu próprio "relógio" de regeneração. Isso evita ter
    # que fazer malabarismo pra combinar duas taxas diferentes num timestamp só.
    ultima_sync_energia = models.DateTimeField(default=timezone.now)
    ultima_sync_saude = models.DateTimeField(default=timezone.now)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfis"

    def __str__(self):
        return f"Perfil de {self.usuario.username}"

    def _regenerar(self, campo_atual, campo_maximo, campo_timestamp, minutos_por_ponto):
        """
        Lógica genérica de regeneração "sob demanda": calcula quantos pontos
        inteiros já deveriam ter regenerado desde o último timestamp salvo,
        aplica o ganho, e avança o timestamp só pelo tempo já convertido em
        pontos (o restante da fração de minuto continua contando pra próxima vez).

        Isso é chamado sempre que o valor é lido ou gasto — nenhum processo
        precisa ficar rodando "ao vivo" pra cada jogador.
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

    def sincronizar(self):
        """Atualiza energia e saúde com base no tempo decorrido, e salva se algo mudou."""
        antes = (self.energia_atual, self.saude_atual)

        self._regenerar("energia_atual", "energia_maxima", "ultima_sync_energia", MINUTOS_POR_PONTO_DE_ENERGIA)
        self._regenerar("saude_atual", "saude_maxima", "ultima_sync_saude", MINUTOS_POR_PONTO_DE_SAUDE)

        depois = (self.energia_atual, self.saude_atual)
        if antes != depois:
            self.save(update_fields=[
                "energia_atual", "ultima_sync_energia",
                "saude_atual", "ultima_sync_saude",
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
        self.save(update_fields=["energia_atual"])
        return True
