from django.conf import settings
from django.db import models

# Nível máximo que uma skill pode atingir.
NIVEL_MAXIMO = 1000

# A cada faixa de 100 pontos, a eficiência de ganho cai — skill continua
# infinita, mas fica cada vez mais cara de continuar subindo. Ver seção
# 1.4 do DESIGN.md.
TAMANHO_DA_FAIXA_DE_DIMINISHING_RETURNS = 100
PENALIDADE_POR_FAIXA = 0.2


def xp_necessario_para_nivel(nivel):
    """
    Quanto de XP falta pra sair do `nivel` atual e chegar no próximo.
    Cresce conforme o nível sobe — cada ponto de skill fica um pouco
    mais caro que o anterior.
    """
    return 100 * (nivel + 1)


def multiplicador_de_eficiencia(nivel):
    """
    Diminishing returns: a cada 100 pontos de nível, o XP que realmente
    conta cai um pouco. Nível 0-99 = 100%, 100-199 = ~83%, 200-299 =
    ~71%, e assim por diante. Nunca chega a zero, só fica cada vez mais
    lento virar especialista de verdade.
    """
    faixa = nivel // TAMANHO_DA_FAIXA_DE_DIMINISHING_RETURNS
    return 1 / (1 + faixa * PENALIDADE_POR_FAIXA)


class Skill(models.TextChoices):
    """
    As únicas 3 skills do jogo. Diferente da versão anterior (8
    categorias tipo Indústria/Comércio/Tecnologia), essas não têm mais
    nenhuma relação com o tipo de empresa — classificação de empresa
    agora é `terreno` (Matriz) ou `tipo_industria` (Industrial), ver
    o app `empresas`.
    """

    INTELIGENCIA = "inteligencia", "Inteligência"
    FISICO = "fisico", "Físico"
    CARISMA = "carisma", "Carisma"


class HabilidadeDoJogador(models.Model):
    """
    O progresso de UM jogador em UMA das 3 skills. Só existe um registro
    depois que o jogador ganha XP naquela skill pela primeira vez —
    antes disso, é tratado como nível 0 sem precisar de linha no banco.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="habilidades"
    )
    skill = models.CharField(max_length=20, choices=Skill.choices)
    nivel = models.PositiveSmallIntegerField(default=0)
    xp_atual = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Habilidade do jogador"
        verbose_name_plural = "Habilidades dos jogadores"
        unique_together = ("usuario", "skill")
        ordering = ["skill"]

    def __str__(self):
        return f"{self.usuario.username} - {self.get_skill_display()}: nível {self.nivel}"

    def xp_necessario(self):
        return xp_necessario_para_nivel(self.nivel)

    def ganhar_xp(self, quantidade_bruta):
        """
        Aplica o multiplicador de diminishing returns sobre o XP bruto
        recebido, adiciona, e sobe de nível quantas vezes for necessário.
        Retorna quantos níveis subiu.

        Nota: essa função ainda NÃO aplica o multiplicador de QoL ×
        qualidade da escola da seção 1.2 do DESIGN.md — isso depende do
        sistema de QoL pessoal e de Escolas, que ainda não existem
        (fica pras próximas fases). Por enquanto só o diminishing
        returns já está valendo.
        """
        if self.nivel >= NIVEL_MAXIMO:
            return 0

        xp_efetivo = round(quantidade_bruta * multiplicador_de_eficiencia(self.nivel))
        xp_efetivo = max(xp_efetivo, 1)  # nunca deixa o ganho zerar de vez

        niveis_subidos = 0
        self.xp_atual += xp_efetivo
        while self.nivel < NIVEL_MAXIMO and self.xp_atual >= self.xp_necessario():
            self.xp_atual -= self.xp_necessario()
            self.nivel += 1
            niveis_subidos += 1

        self.save(update_fields=["nivel", "xp_atual"])
        return niveis_subidos
