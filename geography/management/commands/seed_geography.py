from django.core.management.base import BaseCommand

from geography.models import Bairro, Cidade, Estado


class Command(BaseCommand):
    help = "Popula o banco com um estado, uma cidade e bairros iniciais (idempotente)."

    def handle(self, *args, **options):
        estado, _ = Estado.objects.get_or_create(nome="Estado Central", sigla="EC")
        cidade, _ = Cidade.objects.get_or_create(nome="Nova Polis", estado=estado)

        # (nome, x, y, faixa, qualidade_vida_inicial, e_prefeitura)
        bairros = [
            ("Praça da Prefeitura", 0, 0, Bairro.FaixaRenda.MEDIA, 60, True),
            ("Vila Operária", -1, 0, Bairro.FaixaRenda.BAIXA, 35, False),
            ("Beira-Rio", -1, 1, Bairro.FaixaRenda.BAIXA, 30, False),
            ("Conjunto Esperança", 0, -1, Bairro.FaixaRenda.BAIXA, 40, False),
            ("Jardim das Acácias", 1, 0, Bairro.FaixaRenda.MEDIA, 55, False),
            ("Vila Nova", 0, 1, Bairro.FaixaRenda.MEDIA, 58, False),
            ("Setor Comercial", 1, -1, Bairro.FaixaRenda.MEDIA, 62, False),
            ("Colina Alta", 2, 0, Bairro.FaixaRenda.ALTA, 85, False),
        ]

        criados = 0
        for nome, x, y, faixa, qol, e_prefeitura in bairros:
            _, foi_criado = Bairro.objects.get_or_create(
                cidade=cidade,
                grid_x=x,
                grid_y=y,
                defaults={
                    "nome": nome,
                    "faixa_renda": faixa,
                    "qualidade_vida": qol,
                    "e_bairro_da_prefeitura": e_prefeitura,
                },
            )
            criados += int(foi_criado)

        self.stdout.write(self.style.SUCCESS(
            f"Pronto: {estado.nome} / {cidade.nome} com {len(bairros)} bairros ({criados} criados agora)."
        ))
