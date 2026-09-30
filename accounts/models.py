from django.contrib.auth.models import AbstractUser


class Usuario(AbstractUser):
    """
    Usuário de autenticação. Existe como modelo customizado desde o início
    porque trocar AUTH_USER_MODEL depois que há dados reais é muito doloroso.

    Apenas autenticação. O estado de jogo do jogador (energia, dinheiro,
    skills...) NÃO fica aqui: será modelado separadamente (P0.04).
    """
