# Polis

MVP de um jogo de simulação política/econômica text-based. Esta primeira
versão implementa só os sistemas mais fundamentais — o resto (empresas,
bolsa de valores, imóveis, leis, eleições, judiciário) entra em cima
dessa base, nas próximas sessões.

## O que já funciona

- Cadastro de jogador, com sorteio do bairro de nascimento ponderado por
  faixa de renda (50% baixa / 40% média / 10% alta, configurável)
- Dinheiro inicial varia de acordo com a faixa sorteada
- Energia e saúde que regeneram sozinhas com o tempo, calculadas sob
  demanda (sem nenhum processo rodando o tempo todo)
- Sistema de habilidades: 8 categorias (Indústria, Comércio, Tecnologia,
  Saúde, Educação, Jurídico, Serviços, Agropecuária), cada uma com nível
  e XP próprios, custo de XP crescente por nível
- Ação de "trabalhar": jogador escolhe a categoria, gasta energia, gera
  dinheiro e XP naquela categoria (sobe de nível automaticamente), fica
  no histórico
- Painel administrativo do Django pronto (`/admin/`) pra editar qualquer
  dado do jogo sem escrever tela nenhuma

## Estrutura do projeto

```
polis/            configurações do projeto (settings.py, urls.py)
accounts/         Usuario customizado, Perfil (energia/saúde/dinheiro), cadastro/login/painel
geography/        Estado, Cidade, Bairro + comando de seed
skills/            categorias de habilidade + progresso de nível por jogador
core/              ações de jogo (por enquanto: trabalhar)
templates/         template base compartilhado
```

## Rodando localmente

Pré-requisito: Python 3.11+.

```bash
# 1. Criar e ativar o ambiente virtual
python3 -m venv citycore-env
source citycore-env/bin/activate      # No Windows: citycore-env\Scripts\activate

# 2. Instalar as dependências
pip install -r requirements.txt

# 3. Configurar variáveis de ambiente
cp .env.example .env
# abra o .env e gere uma SECRET_KEY com:
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 4. Criar o banco (sqlite local, zero configuração)
python manage.py migrate

# 5. Popular os bairros e as categorias de habilidade iniciais
python manage.py seed_geography
python manage.py seed_skills

# 6. Criar um usuário admin, pra acessar /admin/
python manage.py createsuperuser

# 7. Rodar o servidor
python manage.py runserver
```

Acesse `http://127.0.0.1:8000/cadastro/` pra criar um jogador, ou
`http://127.0.0.1:8000/admin/` pra mexer nos dados direto.

## Como continuar o desenvolvimento entre conversas

Esse projeto foi feito num ambiente de chat, que não guarda os arquivos
de uma conversa pra outra. O fluxo recomendado:

1. Depois de cada sessão, baixe os arquivos e suba num repositório
   **GitHub gratuito** (`git init`, `git add .`, `git commit`, `git push`)
2. Na próxima conversa, me mande o link do repositório (ou re-suba os
   arquivos relevantes) pra eu continuar exatamente de onde paramos
3. Isso também já deixa tudo pronto pra conectar direto num serviço de
   deploy (Railway ou Render conseguem fazer deploy automático a partir
   de um repositório GitHub)

## Deploy (Railway ou Render)

Ambos funcionam de forma parecida:

1. Suba o projeto num repositório GitHub
2. Crie um novo projeto no Railway/Render e conecte o repositório
3. Adicione um banco Postgres (ambos oferecem isso com um clique) — o
   host gera a `DATABASE_URL` automaticamente
4. Configure as variáveis de ambiente do `.env.example` no painel do
   host (`SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS` com o domínio que
   o host te der, e a `DATABASE_URL` gerada)
5. Comando de start: `gunicorn polis.wsgi`
6. Depois do primeiro deploy, rode `python manage.py migrate` e
   `python manage.py seed_geography` no terminal do host

## Próximos sistemas (na ordem que faz mais sentido construir)

1. Empresas (criação, cargos customizados, contratação, ranking de estrelas)
2. Leis paramétricas + câmara + cadeia de aprovação com prazos
3. Eleições (prefeito/governador/presidente)
4. Mercado imobiliário + contratos de construção via leilão
5. Judiciário (STF, fiscais, júri popular)
6. Mercado de ações
