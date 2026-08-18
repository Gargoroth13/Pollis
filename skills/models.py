from django.conf import settings
from django.db import models

# Nível máximo que uma habilidade pode atingir.
NIVEL_MAXIMO = 100


def xp_necessario_para_nivel(nivel):
    """
    Quanto de XP falta pra sair do `nivel` atual e chegar no próximo.
    Cresce conforme o nível sobe, então cada ponto de habilidade fica
    um pouco mais caro que o anterior — isso é o que faz treinar do
    zero ser rápido e virar especialista ser um investimento de verdade.
    """
    return 100 * (nivel + 1)


class CategoriaDeHabilidade(models.Model):
    """
    Um "setor" amplo (Indústria, Tecnologia, Jurídico...). Profissões e
    cargos de empresa vão futuramente exigir um nível mínimo numa ou
    mais dessas categorias. Fica num model separado (em vez de uma
    lista fixa no código) justamente pra dar pra criar setores novos
    sem precisar mexer em nenhuma view.
    """

    nome = models.CharField(max_length=50, unique=True)
    descricao = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Categoria de habilidade"
        verbose_name_plural = "Categorias de habilidade"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class HabilidadeDoJogador(models.Model):
    """
    O progresso de UM jogador em UMA categoria. Só existe um registro
    depois que o jogador pratica aquela categoria pela primeira vez —
    antes disso, ele é tratado como nível 0 sem precisar de linha no banco.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="habilidades"
    )
    categoria = models.ForeignKey(
        CategoriaDeHabilidade, on_delete=models.CASCADE, related_name="jogadores"
    )
    nivel = models.PositiveSmallIntegerField(default=0)
    xp_atual = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Habilidade do jogador"
        verbose_name_plural = "Habilidades dos jogadores"
        unique_together = ("usuario", "categoria")
        ordering = ["categoria__nome"]

    def __str__(self):
        return f"{self.usuario.username} - {self.categoria.nome}: nível {self.nivel}"

    def xp_necessario(self):
        return xp_necessario_para_nivel(self.nivel)

    def ganhar_xp(self, quantidade):
        """
        Adiciona XP e sobe de nível quantas vezes for necessário (o `while`
        cobre o caso raro de ganhar XP suficiente pra subir mais de um
        nível de uma vez só). Retorna quantos níveis subiu, pra a view
        poder mostrar uma mensagem comemorando.
        """
        if self.nivel >= NIVEL_MAXIMO:
            return 0

        niveis_subidos = 0
        self.xp_atual += quantidade
        while self.nivel < NIVEL_MAXIMO and self.xp_atual >= self.xp_necessario():
            self.xp_atual -= self.xp_necessario()
            self.nivel += 1
            niveis_subidos += 1

        self.save(update_fields=["nivel", "xp_atual"])
        return niveis_subidos
