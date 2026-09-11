# 05 — Inventário

> **Status:** REVIEW
>
> Este documento define o funcionamento do inventário pessoal do jogador.
>
> O inventário deve permanecer simples e servir principalmente como representação
> da posse física de produtos, permitindo que outros sistemas interajam com esses
> itens.
>
> Sistemas específicos de produtos, receitas, alimentação e efeitos devem ser
> definidos no catálogo correspondente.

---

# 1. Visão geral

O inventário representa os itens pertencentes ao jogador.

O jogador pode:

- visualizar seus itens;
- organizar itens por categoria;
- utilizar itens;
- enviar itens para outros jogadores;
- manter itens armazenados para uso futuro.

O inventário não deve possuir, nesta versão, sistemas complexos de:

- slots;
- peso;
- mochila;
- durabilidade;
- raridade;
- limite genérico de capacidade.

A quantidade e as regras de cada produto são definidas pelo catálogo de
Produtos e Receitas.

---

# 2. Estrutura

A posse básica de um item é representada conceitualmente por:

Jogador
↓
Produto
↓
Quantidade

Exemplo:

Arroz × 20

Produtos empilháveis devem possuir uma quantidade agregada, em vez de uma
entrada individual para cada unidade.

3. Categorias

Os itens devem ser organizados por categorias para facilitar a navegação e
utilização.

Exemplos:

Alimentos;
Roupas;
Materiais;
Móveis;
Outros produtos.

As categorias são determinadas pelo catálogo de produtos.

O inventário não deve criar classificações duplicadas ou diferentes das
classificações definidas pelo sistema de Produtos e Receitas.

4. Compra

Comprar um produto significa adquirir sua posse física.

Fluxo:

Jogador
↓
compra
↓
dinheiro → vendedor
produto → inventário

A compra não aplica automaticamente o efeito do produto.

O produto permanece no inventário até que seja utilizado, transferido ou
vendido através de um sistema permitido.

5. Utilização de itens

Itens que possuam utilização devem disponibilizar uma ação correspondente.

Exemplos:

Alimento
→ Consumir

Roupa
→ Equipar

Material
→ utilizar em atividade

Móvel
→ utilizar na residência

O efeito da utilização é definido pelo tipo de produto e pelo sistema que o
consome.

Ao utilizar um item consumível:

item
→ efeito
→ quantidade reduzida
6. Alimentação

Alimentos são mantidos no inventário até serem consumidos.

Fluxo:

Comprar alimento
↓
Inventário
↓
Consumir
↓
Nutrição
+
buffs específicos
↓
alimento consumido

A quantidade de Nutrição recuperada e os buffs fornecidos por cada alimento
são definidos no documento de Produtos e Receitas.

O Inventário apenas realiza a posse e o consumo do item.

7. Itens ativos

Alguns itens ou propriedades do jogador podem existir simultaneamente, mas
apenas um deles deve estar ativo quando o sistema precisar determinar qual
está sendo utilizado.

Exemplos:

Inventário:
Roupa comum
Roupa premium
Roupa esportiva

Roupa ativa:
Roupa premium

Apenas a roupa ativa fornece seus efeitos relacionados ao uso.

O mesmo princípio pode ser aplicado a outros sistemas.

8. Residência ativa

Um jogador pode possuir mais de um imóvel caso outras regras do jogo permitam.

Apenas um imóvel pode ser considerado sua residência ativa.

A residência ativa determina os efeitos de moradia aplicados ao jogador, como
os modificadores de QoL correspondentes.

Exemplo:

Jogador
├── Casa A
├── Casa B
└── Apartamento C

Residência ativa
→ Casa B

A posse de outros imóveis não aplica automaticamente seus benefícios de
moradia.

9. Veículo ativo

Caso o jogador possua mais de um veículo, um deles pode ser definido como
veículo ativo.

O veículo ativo determina os efeitos relacionados ao deslocamento, como:

características de transporte;
tempo de viagem;
custos;
outros efeitos específicos.

Exemplo:

Jogador
├── Carro A
├── Carro B
└── Moto C

Veículo ativo
→ Carro B

O sistema não precisa possuir um sistema complexo de equipamentos para isso.

10. Conceito de estado ativo

Quando um sistema precisar determinar qual bem de um determinado tipo o
jogador está efetivamente utilizando, deve existir uma referência de estado
ativo.

O conceito pode ser utilizado para:

roupa ativa;
veículo ativo;
residência ativa;
outros bens ou propriedades futuras.

Isso permite que o jogador possua múltiplos bens sem aplicar simultaneamente
os benefícios de todos eles.

11. Transferência entre jogadores

Itens podem ser enviados diretamente de um jogador para outro.

A transferência utiliza um serviço abstrato de correio.

O serviço de correio não representa uma empresa do jogo e não possui uma
economia própria.

Seu objetivo é apenas fornecer uma mecânica de envio de itens.

Fluxo:

Jogador A
↓
Serviço de Correio
↓
Jogador B

Toda transferência direta de item possui uma taxa obrigatória.

12. Taxa de transferência

A taxa de envio deve ser baseada no valor de referência do item.

Estrutura conceitual:

taxa =
MAX(taxa_mínima, valor_de_referência × percentual)

O valor de referência e o percentual são parâmetros de balanceamento.

O objetivo da taxa é impedir que transferências diretas se tornem uma forma
gratuita de comércio paralelo.

13. Comércio entre jogadores

Venda direta de itens entre jogadores não ocorre através de uma simples
transferência.

A venda de itens entre jogadores deve utilizar um mercado dedicado.

Fluxo:

Jogador A
↓
anuncia item
↓
Mercado de Jogadores
↓
Jogador B compra

O mercado possui suas próprias taxas.

As taxas e regras do mercado devem ser suficientemente relevantes para que o
Varejo continue sendo uma parte importante da economia.

14. Transferência versus venda

O sistema não deve tentar determinar automaticamente se uma transferência
foi um presente ou uma venda disfarçada.

Não devem existir algoritmos que tentem inferir:

item enviado
+
dinheiro enviado posteriormente
=
possível venda

Essa abordagem é considerada excessivamente complexa e fácil de contornar.

A regra é simples:

transferência direta de item
→ taxa obrigatória

venda entre jogadores
→ mercado dedicado

Não existe transferência gratuita de itens.

15. Varejo

O Varejo continua sendo o principal mecanismo de comércio entre empresas e
consumidores.

Estrutura:

Empresa de Varejo
↓
produto
↓
Jogador

A transferência direta entre jogadores não deve substituir o Varejo como
forma normal de aquisição.

O Mercado de Jogadores existe como alternativa para comércio entre jogadores,
mas deve possuir fricções próprias.

16. Venda de itens do jogador

Jogadores não podem transformar seu inventário em uma loja de varejo informal
vendendo diretamente qualquer item para outro jogador.

A venda de produtos entre jogadores utiliza o Mercado de Jogadores.

A existência dessa separação preserva a função econômica do Varejo.

17. Estoque empresarial e inventário pessoal

Estoque de empresa e inventário de jogador são estruturas diferentes.

Produto
↑
├── Estoque da Empresa
└── Inventário do Jogador

Ambos utilizam a mesma definição de Produto.

O Inventário não deve duplicar informações do produto.

18. Armazenamento

Nesta versão não existe um limite genérico de capacidade do inventário.

O jogador pode armazenar seus itens sem controle de:

peso;
slots;
volume;
limite geral.

Essa decisão pode ser revisada futuramente caso os testes demonstrem que
acumulação excessiva de itens gera problemas.

Possíveis soluções futuras incluem capacidade de armazenamento associada a
imóveis ou outras estruturas.

19. Auditoria

Alterações relevantes na posse de itens devem ser rastreáveis.

Operações importantes incluem:

compra;
consumo;
transferência;
venda;
recebimento;
produção, quando aplicável.

Conceitualmente, uma operação deve permitir identificar:

origem
destino
produto
quantidade
timestamp
tipo da operação

O nível de detalhamento e retenção histórica será definido pelo sistema de
auditoria/transparência.

O objetivo principal é facilitar:

investigação de exploits;
debugging;
análise econômica;
suporte;
testes com bots.
20. Bots e inventário

O inventário deve ser simples o suficiente para que bots possam interagir
com ele sem precisar de lógica excessivamente complexa.

Comportamentos básicos esperados:

comprar
→ armazenar
→ consumir
→ transferir
→ vender através do mercado

O Bot Test deverá observar principalmente:

acumulação excessiva;
concentração de itens;
frequência de consumo;
impacto das taxas;
uso do Mercado de Jogadores;
relação entre Varejo e comércio entre jogadores.
21. Balanceamento

Os seguintes elementos devem permanecer parametrizados:

taxa mínima de correio;
percentual da taxa de correio;
valor de referência dos itens;
taxas do Mercado de Jogadores;
limites ou restrições futuras de armazenamento;
outras fricções relacionadas ao comércio.

O balanceamento será definido posteriormente através dos bots.

22. Questões em aberto
Percentual exato da taxa de correio.
Taxa mínima do correio.
Metodologia para determinar o valor de referência dos itens.
Taxas do Mercado de Jogadores.
Regras detalhadas do Mercado de Jogadores.
Estrutura completa de auditoria.
Modelo futuro de armazenamento, caso seja necessário.
Categorias definitivas de itens.
Regras específicas para itens permanentes e consumíveis.
23. Fora do escopo

Este documento não define detalhadamente:

Produtos e Receitas;
produção empresarial;
funcionamento do Varejo;
alimentação;
QoL;
imóveis;
veículos;
contratos;
transparência de mercado.

Esses sistemas possuem documentação própria.

Este documento define apenas como o Inventário se relaciona com eles.


Eu fiz questão de manter **correio, Mercado P2P e Varejo como três coisas distintas**. Também deixei a capacidade de armazenamento explicitamente **fora da implementação atual**, mas registrada como possível evolução baseada nos resultados dos bots.

E um ponto que considero importante para os próximos documentos: **o conceito de "estado ativo" provavelmente merece aparecer também em Imóveis e depois em Veículos**, porque não é realmente uma função exclusiva do Inventário.
