# Polis

MVP de um jogo de simulação política/econômica text-based. O design
completo do jogo (todas as regras, números e pendências) está em
`DESIGN.md` — este README documenta só o que já existe em código.

## O que já funciona

- Cadastro de jogador, com sorteio do bairro de nascimento ponderado por
  faixa de renda (50% baixa / 40% média / 10% alta, configurável)
- Dinheiro inicial varia de acordo com a faixa sorteada
- Energia e saúde que regeneram sozinhas com o tempo, calculadas sob
  demanda (sem nenhum processo rodando o tempo todo)
- **3 skills fixas do jogador**: Inteligência, Físico, Carisma — com
  diminishing returns (eficiência de ganho cai a cada 100 pontos de nível)
- Ação de "trabalhar": jogador escolhe qual skill treinar, gasta
  energia, gera dinheiro e XP (sobe de nível automaticamente), fica no
  histórico
- Empresas: qualquer jogador funda uma, escolhendo um **tipo** (Matriz,
  Industrial, Varejo, Construtora, Serviços) e, de acordo com o tipo,
  uma classificação própria:
  - Matriz → **terreno** (Agropecuária/Extrativismo/Mineração)
  - Industrial → **tipo de indústria** (Produção/Alimentícia/Bens de
    consumo/Tecnológica)
  - Serviços → **especialização** (Transporte/Publicidade/Lazer/Financeira)
  - Varejo/Construtora não têm sub-classificação
- Cargos customizados dentro da empresa: título livre, uma das 3 skills
  como requisito, nível mínimo, salário — contrata outros jogadores que
  atendam o requisito
- Sistema de estrelas (1 a 5): cada nível define quantos cargos a
  empresa pode ter; upar de nível exige um número mínimo de funcionários
  contratados **e** um investimento em dinheiro do dono
- Empregado formal ganha um botão de trabalho que paga o salário fixo do
  cargo (em vez do valor aleatório do trabalho freelance)
- Cadeia produtiva: **Matriz** produz matéria-prima do zero (de acordo
  com o terreno), **Industrial** compra da Matriz (ou de outra
  Industrial, pra receitas que usam manufaturado como ingrediente) e
  fabrica seguindo receitas com estrela mínima, **Varejo** compra da
  Industrial e revende pros jogadores no Mercado público, **Construtora**
  compra da Industrial. Catálogo completo: **67 produtos** (29
  matérias-primas + 38 manufaturados) e **82 linhas de receita**,
  incluindo o Carro (exige Industrial 5★ e ingredientes de 3 tipos de
  indústria diferentes)
- Consumo operacional: Matriz e Industrial consomem 1 EPI + 1 Uniforme
  do próprio estoque a cada produzir/fabricar (se tiver — não bloqueia
  se faltar, só avisa)
- **Produzir/fabricar não é mais só do dono** — qualquer funcionário
  contratado (com Cargo na empresa) também pode
- **QoL pessoal**: barra própria do jogador (diferente da QoL do
  bairro), começa em 1.00, drena 0.20 a cada trabalho/produção, se
  recupera sozinha em direção à base com o tempo. Vira multiplicador de
  quanto XP/produção você ganha por ação, e também controla a
  velocidade de regeneração de energia
- **Saúde com decaimento probabilístico**: QoL abaixo de 1 dá chance de
  a saúde cair sozinha; saúde ≤20 entra em depressão (corta a QoL base
  pela metade); saúde chega a 0 → internação automática de 3 dias,
  bloqueando ações de trabalho
- **Nutrição**: nova barra, cai sozinha com o tempo, só sobe consumindo
  itens de comida do inventário; nutrição zerada trava a QoL num teto
  de 60% da base
- **Inventário do jogador**: comprar no Mercado agora entrega o item de
  verdade (não só transfere dinheiro); itens de comida (Pão, Chocolate,
  Macarrão, Hambúrguer, Suco, Sorvete, Carne de Sol, Refrigerante) têm
  efeito real de nutrição/QoL ao consumir
- **Qualidade afeta preço**: a estrela de quem vende encarece o produto
  (`preço = preço_base × (1 + (estrela-1) × 0.15)`) — testado em compra
  real entre empresas, não só na fórmula isolada
- **Especialização de funcionário**: produzir/fabricar o mesmo produto
  repetidamente cria um registro de especialista naquele item
  específico, com bônus de até +50% de produção no nível máximo (100)
- **Financeira** (app novo): empresas de Serviços com especialização
  Financeira ganham poupança (juros semanais compostos, calculados sob
  demanda), empréstimo (juros de 5% fixo), cartão de crédito (limite
  calculado por skill Carisma + renda recente, juros compostos mensais
  de 10%), transferência entre jogadores (taxa de 2% pro dono da
  financeira), reserva obrigatória de 20% (bloqueia saque/empréstimo/
  saque de cartão que deixaria o caixa abaixo disso), rating público
  de solvência (A a F) e falência (reduz saldo dos depositantes em 30%,
  bloqueia saque por 30 dias)
- Painel administrativo do Django pronto (`/admin/`) pra editar qualquer
  dado do jogo sem escrever tela nenhuma

## Estrutura do projeto

```
polis/            configurações do projeto (settings.py, urls.py)
accounts/         Usuario customizado, Perfil (energia/saúde/nutrição/QoL/dinheiro), ItemDoJogador (inventário), cadastro/login/painel
geography/        Estado, Cidade, Bairro + comando de seed
skills/            as 3 skills fixas (Inteligência/Físico/Carisma) + progresso por jogador
empresas/          Empresa (tipo + classificação + estrelas), Cargo, Produto/Receita/Estoque, Mercado
financeira/        Poupança, Empréstimo, Cartão de crédito, transferência, reserva obrigatória e falência
core/              ações de jogo (trabalho freelance genérico)
templates/         template base compartilhado
DESIGN.md          documento de design completo — regras, números, pendências
```

## Simplificações atuais (documentadas de propósito)

- Qualidade afeta o **preço** de venda, mas ainda não o **efeito**
  (nutrição/QoL) do item ao consumir — isso exigiria rastrear a
  qualidade por lote no inventário, não só a quantidade (Fase 6+)
- QoL "base" é fixa em 1.00 pra todo mundo — ainda não existe posse de
  imóvel/carro/roupa pra calcular isso de verdade (Fase 6 e além)
- Médico reduzindo tempo de internação ainda não existe (depende do
  sistema de diploma/profissão formal)

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

# 5. Popular os bairros e o catálogo de produtos
python manage.py seed_geography
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
   `python manage.py seed_geography` + `python manage.py seed_produtos`
   no terminal do host

## Roadmap (ver DESIGN.md pra detalhe completo)

- [x] Fase 1 — Fundação: skills (3 stats fixos) + classificação de empresa (terreno/tipo_industria/especialização)
- [x] Fase 2 — Catálogo expandido (67 produtos), compra Industrial→Industrial, consumo operacional, estrela mínima por receita
- [x] Fase 3 — Loop do jogador: inventário, QoL pessoal/Saúde/Nutrição, produção via funcionário
- [x] Fase 4a — Qualidade afetando preço, especialização de funcionário
- [x] Fase 4b — Financeira: poupança, empréstimo, cartão, transferência, reserva obrigatória, rating, falência (bolsa de valores e intervenção do governo ficaram de fora — dependem de fases futuras)
- [ ] Fase 5 — Governo: cargos políticos, orçamento público, leis com trade-off
- [ ] Fase 6 — Imóveis e Construtora
- [ ] Fase 7 — População/NPC
