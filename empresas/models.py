from decimal import Decimal

from django.conf import settings
from django.db import models

from skills.models import CategoriaDeHabilidade

ESTRELA_MAXIMA = 5

# Define, pra cada nível de estrela atual: quantos cargos a empresa pode ter
# no total, e o que é exigido pra subir pro próximo nível (número mínimo de
# funcionários OCUPADOS no momento — representa o "tamanho" real da empresa —
# e o investimento em dinheiro que o dono precisa pagar). O último nível não
# tem "próximo", então os campos de upgrade ficam None.
NIVEIS_DE_EMPRESA = {
    1: {"max_cargos": 3, "funcionarios_para_upar": 3, "custo_para_upar": Decimal("5000")},
    2: {"max_cargos": 6, "funcionarios_para_upar": 6, "custo_para_upar": Decimal("20000")},
    3: {"max_cargos": 12, "funcionarios_para_upar": 10, "custo_para_upar": Decimal("75000")},
    4: {"max_cargos": 25, "funcionarios_para_upar": 20, "custo_para_upar": Decimal("250000")},
    5: {"max_cargos": 50, "funcionarios_para_upar": None, "custo_para_upar": None},
}


class TipoDeEmpresa(models.TextChoices):
    MATRIZ = "matriz", "Matriz (extração/produção primária)"
    INDUSTRIAL = "industrial", "Industrial (manufatura)"
    VAREJO = "varejo", "Varejo (venda ao consumidor)"


class Empresa(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    tipo = models.CharField(max_length=12, choices=TipoDeEmpresa.choices, default=TipoDeEmpresa.VAREJO)
    setor = models.ForeignKey(CategoriaDeHabilidade, on_delete=models.PROTECT, related_name="empresas")
    dono = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="empresas_possuidas"
    )
    estrelas = models.PositiveSmallIntegerField(default=1)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        ordering = ["-estrelas", "nome"]

    def __str__(self):
        return f"{self.nome} ({'★' * self.estrelas})"

    def config_nivel_atual(self):
        return NIVEIS_DE_EMPRESA[self.estrelas]

    def max_cargos_permitidos(self):
        return self.config_nivel_atual()["max_cargos"]

    def funcionarios_ocupados(self):
        return self.cargos.filter(ocupante__isnull=False).count()

    def pode_upar(self):
        return self.estrelas < ESTRELA_MAXIMA

    def requisitos_para_upar(self):
        """Retorna os requisitos pro próximo nível, ou None se já é o nível máximo."""
        if not self.pode_upar():
            return None
        return NIVEIS_DE_EMPRESA[self.estrelas]

    def upar(self):
        """
        Tenta subir a empresa pro próximo nível de estrela. Retorna uma
        tupla (sucesso, mensagem) — nunca lança exceção, pra view só
        precisar checar o booleano e mostrar a mensagem.
        """
        if not self.pode_upar():
            return False, f"{self.nome} já está no nível máximo ({ESTRELA_MAXIMA} estrelas)."

        requisitos = self.requisitos_para_upar()
        funcionarios_atuais = self.funcionarios_ocupados()
        if funcionarios_atuais < requisitos["funcionarios_para_upar"]:
            return False, (
                f"Precisa de pelo menos {requisitos['funcionarios_para_upar']} funcionários "
                f"contratados (tem {funcionarios_atuais}) pra subir de nível."
            )

        perfil_dono = self.dono.perfil
        custo = requisitos["custo_para_upar"]
        if perfil_dono.dinheiro < custo:
            return False, f"Custa R$ {custo} pra upar, e o dono só tem R$ {perfil_dono.dinheiro}."

        perfil_dono.dinheiro -= custo
        perfil_dono.save(update_fields=["dinheiro"])
        self.estrelas += 1
        self.save(update_fields=["estrelas"])
        return True, f"{self.nome} subiu para {self.estrelas} estrelas!"


class Cargo(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="cargos")
    titulo = models.CharField(max_length=80)
    categoria_habilidade = models.ForeignKey(
        CategoriaDeHabilidade, on_delete=models.PROTECT, related_name="cargos"
    )
    nivel_minimo = models.PositiveSmallIntegerField(default=0)
    salario = models.DecimalField(max_digits=10, decimal_places=2)
    ocupante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cargo_atual",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cargo"
        verbose_name_plural = "Cargos"
        ordering = ["empresa", "titulo"]

    def __str__(self):
        status = self.ocupante.username if self.ocupante else "vago"
        return f"{self.titulo} @ {self.empresa.nome} ({status})"

    def vago(self):
        return self.ocupante_id is None


class Produto(models.Model):
    """
    Catálogo de produtos da cadeia produtiva. Matéria-prima é o que uma
    Matriz produz do zero; manufaturado é o que uma Industrial fabrica
    a partir de matéria-prima, seguindo uma Receita.

    O `setor` define quem tem permissão de mexer nesse produto: só
    empresas cujo próprio setor bate com o do produto podem produzi-lo
    (Matriz) ou fabricá-lo (Industrial). Varejo não tem essa restrição
    — pode revender qualquer manufaturado que conseguir comprar.
    """

    nome = models.CharField(max_length=60, unique=True)
    eh_materia_prima = models.BooleanField()
    setor = models.ForeignKey(CategoriaDeHabilidade, on_delete=models.PROTECT, related_name="produtos")
    preco_base = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        ordering = ["setor", "nome"]

    def __str__(self):
        tipo = "matéria-prima" if self.eh_materia_prima else "manufaturado"
        return f"{self.nome} ({tipo})"


class Receita(models.Model):
    """
    Um ingrediente necessário pra fabricar um produto manufaturado. Um
    mesmo produto_final pode ter várias Receitas (vários ingredientes
    diferentes exigidos ao mesmo tempo).
    """

    produto_final = models.ForeignKey(
        Produto, on_delete=models.CASCADE, related_name="receitas",
        limit_choices_to={"eh_materia_prima": False},
    )
    materia_prima = models.ForeignKey(
        Produto, on_delete=models.PROTECT, related_name="usada_em_receitas",
        limit_choices_to={"eh_materia_prima": True},
    )
    quantidade_necessaria = models.PositiveIntegerField(default=1)
    quantidade_produzida = models.PositiveIntegerField(
        default=1, help_text="Quanto de produto_final cada execução da receita rende."
    )

    class Meta:
        verbose_name = "Receita"
        verbose_name_plural = "Receitas"
        unique_together = ("produto_final", "materia_prima")

    def __str__(self):
        return f"{self.quantidade_necessaria}x {self.materia_prima.nome} → {self.quantidade_produzida}x {self.produto_final.nome}"


class EstoqueDaEmpresa(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="estoque")
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="em_estoque_de")
    quantidade = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Estoque"
        verbose_name_plural = "Estoques"
        unique_together = ("empresa", "produto")
        ordering = ["empresa", "produto"]

    def __str__(self):
        return f"{self.empresa.nome}: {self.quantidade}x {self.produto.nome}"
