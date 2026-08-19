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
- Empresas: qualquer jogador funda uma, define cargos customizados
  (título livre, categoria de skill exigida, nível mínimo, salário) e
  contrata outros jogadores que atendam o requisito de nível
- Sistema de estrelas (1 a 5): cada nível define quantos cargos a
  empresa pode ter; upar de nível exige um número mínimo de funcionários
  contratados **e** um investimento em dinheiro do dono
- Empregado formal ganha um botão de trabalho que paga o salário fixo do
  cargo (em vez do valor aleatório do trabalho freelance)
- Cadeia produtiva por tipo de empresa: **Matriz** produz matéria-prima
  do zero, **Industrial** compra da Matriz e fabrica manufaturados
  seguindo receitas, **Varejo** compra da Industrial e revende pros
  jogadores no Mercado público. Catálogo inicial: Madeira/Algodão/Minério
  de Ferro → Papel/Tecido/Caneta
- Painel administrativo do Django pronto (`/admin/`) pra editar qualquer
  dado do jogo sem escrever tela nenhuma

## Estrutura do projeto

```
polis/            configurações do projeto (settings.py, urls.py)
accounts/         Usuario customizado, Perfil (energia/saúde/dinheiro), cadastro/login/painel
geography/        Estado, Cidade, Bairro + comando de seed
skills/            categorias de habilidade + progresso de nível por jogador
empresas/          Empresa (tipo + estrelas), Cargo, Produto/Receita/Estoque, Mercado
core/              ações de jogo (trabalho freelance genérico)
templates/         template base compartilhado
```

## Simplificações atuais (documentadas de propósito)

- Só o **dono** produz/fabrica na empresa (gasta a própria energia) —
  ainda não delega isso pros funcionários contratados
- Preço de compra/venda é sempre o `preco_base` do produto — não tem
  precificação dinâmica por empresa ainda
- Comprar no Mercado não gera item nenhum no "inventário" do jogador
  (ainda não existe inventário de jogador) — é só o lado econômico da
  cadeia funcionando
- `tipo` da empresa hoje é só Matriz/Industrial/Varejo — a lista existe
  como `TextChoices` em `empresas/models.py`, então adicionar um tipo
  novo (Serviços, Construção etc) é só acrescentar uma linha ali e
  ajustar as regras que dependerem dele

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

# 5. Popular os bairros, categorias de habilidade e catálogo de produtos
python manage.py seed_geography
python manage.py seed_skills
python manage.py seed_produtos

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

1. Leis paramétricas + câmara + cadeia de aprovação com prazos
2. Eleições (prefeito/governador/presidente)
3. Mercado imobiliário + contratos de construção via leilão (por
   ranking de estrelas — a base já está pronta no app `empresas`)
4. Judiciário (STF, fiscais, júri popular)
5. Mercado de ações (elegibilidade por estrelas, também já preparada)
