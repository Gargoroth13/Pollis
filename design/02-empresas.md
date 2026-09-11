# 02 — Empresas

> **Status:** FINAL — BOT TEST
>
> Este documento define o funcionamento do sistema de empresas para a primeira
> versão destinada aos testes com bots.
>
> Regras de balanceamento e parâmetros numéricos que não afetam a estrutura
> do sistema podem ser ajustados após os testes sem alterar o design.

---

# 1. Visão geral

Empresas são uma das principais estruturas econômicas de Polis.

A economia é formada principalmente por empresas controladas por jogadores,
com diferentes funções dentro da cadeia produtiva.

Os principais tipos de empresa são:

- Varejo
- Serviços
- Matriz
- Industrial
- Construtora
- Financeira

Financeira é uma especialização de Serviços.

Cada empresa possui:

- proprietário;
- funcionários;
- cargos;
- qualidade/estrelas;
- estoque, quando aplicável;
- operações determinadas por seu tipo;
- localização;
- regras específicas de compra, produção ou venda.

---

# 2. Tipos de empresa

## 2.1 Matriz

A Matriz é a porta de entrada da cadeia produtiva.

Sua função principal é extrair matérias-primas sem consumir outras matérias-primas
como insumo de produção.

A Matriz:

- consome materiais operacionais;
- não precisa consumir matérias-primas para produzir;
- possui margens menores;
- fornece matérias-primas para empresas que realmente as utilizam.

A categoria da Matriz é determinada pelo tipo de terreno em que ela está
localizada.

O terreno define uma categoria macro de produção.

Exemplo:

Terreno Agro
→ Matriz Agro

O proprietário pode escolher qual produto produzir dentro da categoria
permitida pelo terreno.

A Matriz não pode produzir produtos fora dessa categoria.

A lista de categorias, produtos e receitas é definida em
22 — Receitas-Produção.

2.2 Industrial

A Industrial transforma matérias-primas e produtos intermediários.

Uma Industrial pode:

comprar materiais operacionais;
comprar produtos de Matrizes;
comprar produtos de outras Industriais;
vender produtos para outras empresas consumidoras;
fornecer produtos para Varejos;
fornecer produtos para Construtoras;
realizar outras operações previstas nas receitas.

Uma Industrial não pode comprar ou vender qualquer produto arbitrariamente.

As operações válidas são determinadas pelas receitas e usos definidos no
catálogo de Produtos e Receitas.

2.3 Varejo

O Varejo é a principal etapa empresarial de venda ao consumidor final.

O Varejo:

compra produtos de empresas produtoras;
mantém estoque;
disponibiliza produtos aos jogadores;
possui capacidade diária de venda determinada pelos funcionários.

O Varejo não pode comprar qualquer produto.

A empresa só pode comercializar produtos compatíveis com sua atividade e suas
receitas.

Exemplo:

Varejo de automóveis
→ pode comprar automóveis

Varejo de automóveis
→ não pode comprar móveis
2.4 Serviços

Serviços fornece atividades diretamente para jogadores ou outras entidades.

As principais especializações previstas são:

Transporte;
Lazer;
Publicidade.

A lógica detalhada de cada especialização é definida pelos sistemas
correspondentes.

Financeira é uma especialização de Serviços.

2.5 Construtora

A Construtora transforma insumos da cadeia industrial em imóveis.

A Construtora trabalha com uma obra ativa por vez.

Fluxo:

Dono
↓
inicia obra
↓
obra = 0%
↓
funcionários trabalham
↓
progresso aumenta
↓
obra = 100%
↓
imóvel concluído
↓
nova obra pode ser iniciada

Construtoras maiores não precisam de múltiplas obras simultâneas.

Mais funcionários significam maior velocidade de conclusão e, portanto, maior
quantidade de obras concluídas ao longo do tempo.

A receita da construção é:

Materiais de Construção
+
Acabamentos
→ Imóvel
2.6 Financeira

Financeira é uma especialização de Serviços e representa um sistema de
empresa de endgame.

Seu funcionamento detalhado não faz parte do escopo do Bot Test atual e será
revisado separadamente.

Conceitos previstos para o futuro incluem:

empréstimos;
depósitos;
cartões;
ações;
mercado financeiro;
rating;
falência;
intervenção;
outros serviços financeiros.
3. Cadeia econômica

A economia deve incentivar especialização e interdependência.

Estrutura conceitual:

Matriz
↓
Industrial
↓
Industrial / Varejo / Construtora / outras empresas consumidoras
↓
Jogador

Nem todos os produtos percorrem todas essas etapas.

Alguns produtos podem ser consumidos diretamente por empresas, enquanto outros
chegam ao consumidor.

A economia deve permitir concorrência entre empresas que produzem o mesmo
produto.

Escassez deve ser uma característica desejável da economia:

escassez
→ preço sobe
→ oportunidade de produção
→ empresas entram no mercado
→ oferta aumenta
→ preço tende a se ajustar

A intenção é permitir que a própria economia gere pressão por decisões
políticas, como impostos, incentivos e regulamentações.

4. Permissões de compra e venda

A regra central para o comércio é:

Produto
↓
usos permitidos
↓
empresas capazes de consumi-lo

Uma empresa só pode comprar um produto quando ele for uma entrada válida para
uma receita ou operação disponível para aquela empresa.

Uma empresa só pode vender um produto para uma entidade que possua uma receita,
operação ou necessidade definida que consuma aquele produto.

As permissões devem ser derivadas das receitas e usos do catálogo, evitando
listas independentes e duplicadas.

Exemplo:

Ferro
↓
receita de Aço
↓
Industrial que produz Aço

Essa Industrial pode comprar Ferro.

Uma empresa sem uso válido para Ferro não pode comprá-lo.

O mesmo princípio se aplica ao Varejo.

5. Produção
5.1 Um produto por vez

Cada empresa produtiva possui apenas um produto em produção por vez.

O proprietário escolhe o produto.

Funcionários não escolhem o produto individualmente.

Isso é intencional para incentivar:

especialização;
concorrência;
criação de múltiplas empresas;
dependência entre produtores;
decisões estratégicas de produção.
5.2 Seleção de produção

A escolha do produto deve respeitar:

tipo da empresa;
categoria da empresa;
terreno, no caso de Matrizes;
receitas disponíveis;
requisitos de estrelas;
demais regras do catálogo.
5.3 Troca de produção

Mudar o produto de produção possui três formas de fricção:

custo fixo;
tempo de setup;
cooldown.

Durante o setup:

a empresa fica fora de operação;
nenhum funcionário pode trabalhar;
a produção é interrompida.

O cooldown entre mudanças deve ser aproximadamente de uma semana.

O setup deve ser significativamente menor que o cooldown, funcionando como
um período temporário de inatividade.

Os valores exatos de cooldown, setup e custo serão balanceados posteriormente.

6. Trabalho dos funcionários

O trabalho é baseado em Energia.

A Energia utilizada para o trabalho determina a quantidade de trabalhos
realizados.

Conceitualmente:

Energia gasta
→ 1 trabalho

Um trabalho pode gerar diferentes quantidades de resultado dependendo da
atividade.

Para funções produtivas:

produção por trabalho
=
f(skill, especialização)
×
eficiências adicionais

O jogador pode gastar mais energia realizando mais trabalhos.

Quanto mais trabalho realiza, maior tende a ser:

sua produção;
seu ganho de skill;
sua contribuição para a empresa.

Os valores exatos são parâmetros de balanceamento.

7. Produção e skills

A quantidade produzida por um trabalho depende da skill relevante e da
especialização do funcionário.

A estrutura deve permitir valores como:

Skill 1
Especialização 0
→ aproximadamente 1 unidade por trabalho

e:

Skill maior
+
especialização maior
→ maior produção por trabalho

Os números acima são apenas exemplos conceituais.

A fórmula definitiva deve ser parametrizada.

8. Qualidade da produção

A qualidade efetiva da produção depende das skills dos funcionários que
realmente realizaram o trabalho.

A qualidade deve utilizar uma média ponderada pela contribuição de trabalho.

Ou seja, funcionários que realizaram mais trabalho possuem maior peso no
resultado.

A qualidade produzida é limitada pelo teto determinado pelas estrelas da
empresa.

Conceitualmente:

qualidade da produção
=
média ponderada das skills relevantes

e:

qualidade final
=
MIN(qualidade da produção, teto da estrela)

A estrela representa o potencial máximo da empresa, não seu desempenho
garantido.

Uma empresa 5★ pode possuir baixa qualidade efetiva caso tenha funcionários
pouco qualificados ou pouca atividade produtiva.

9. Funcionários de suporte

Nem todos os cargos precisam produzir itens diretamente.

Existem cargos cuja função é aumentar a eficiência da operação.

Os cargos inicialmente definidos incluem:

Engenheiro;
Advogado.
9.1 Engenheiro

O Engenheiro realiza trabalhos consumindo Energia.

Cada trabalho contribui para o bônus de eficiência produtiva da empresa.

O efeito depende de:

skill relevante;
especialização;
quantidade de trabalhos;
outros parâmetros definidos pelo sistema.

O bônus é diário e é reiniciado a cada novo ciclo diário.

A quantidade de Engenheiros disponíveis é limitada pela estrela da empresa.

Uma empresa grande, com todos os Engenheiros utilizando uma barra completa
de Energia, deve atingir aproximadamente até 2,5× da produção base.

Esse valor é um alvo de balanceamento e poderá ser ajustado após os testes.

O sistema não precisa de um teto artificial adicional além das limitações
estruturais de:

estrela
+
quantidade de Engenheiros
+
Energia
9.2 Advogado

O Advogado realiza trabalhos consumindo Energia.

Cada trabalho reduz o risco de Burnout dos funcionários da empresa.

O efeito depende de:

skill relevante;
especialização;
quantidade de trabalhos;
outros parâmetros definidos pelo sistema.

O efeito é diário e é reiniciado a cada novo ciclo diário.

O risco de Burnout nunca pode ser reduzido abaixo de 1%.

A quantidade de Advogados disponíveis é limitada pela estrela da empresa.

10. Consumo operacional

Materiais operacionais são consumidos de forma diária.

A regra geral é:

consumo diário =
funcionários ativos
×
consumo por funcionário

O consumo é baseado na quantidade de funcionários e não no número de cliques
de trabalho realizados.

Funcionários de produção e suporte contam para o consumo, salvo exceção
explicitamente definida pelo catálogo.

Cada produto operacional possui sua própria regra de consumo no catálogo de
Produtos e Receitas.

11. Varejo

O Varejo possui duas características independentes:

Estoque
≠
Capacidade de venda
11.1 Estoque

O estoque máximo é determinado pelas estrelas da empresa.

Uma empresa de maior estrela possui maior capacidade de armazenar produtos.

11.2 Capacidade de venda

Funcionários do Varejo produzem capacidade de venda.

O trabalho de um vendedor:

Energia
→ trabalho
→ capacidade adicional de venda naquele ciclo

A capacidade de venda depende dos funcionários e de suas características.

Uma venda consome simultaneamente:

uma unidade de estoque;
uma unidade da capacidade de venda.

Portanto:

vendas realizadas
≤ estoque disponível

e:

vendas realizadas
≤ capacidade de venda disponível

O valor exato da capacidade por trabalho será definido pelo balanceamento.

O estoque deve ser maior que a capacidade de venda potencial do período, para
que capacidade de operação seja uma limitação distinta do armazenamento.

12. Construtora

A Construtora possui uma obra ativa por vez.

A obra possui um progresso percentual:

0% → 100%

O proprietário escolhe e inicia uma construção.

Cada trabalho dos funcionários contribui para o progresso.

A eficiência do trabalho pode depender de:

skill;
especialização;
quantidade de funcionários;
Engenheiro;
outras regras empresariais.

Quando o progresso chega a 100%, o imóvel é concluído e a Construtora pode
iniciar outra obra.

13. Especialização

Funcionários desenvolvem especialização através do trabalho em determinada
atividade ou produto.

A especialização melhora o desempenho naquela área.

A especialização não é totalmente permanente.

Quando o jogador deixa de utilizar uma especialização:

especialização
↓
decadência diária baixa

A especialização não pode cair abaixo de:

50% do maior valor histórico atingido

Quando o jogador volta a atuar naquela área:

recuperação
=
1,5× a velocidade normal

Os valores exatos de ganho e decadência serão definidos pelo balanceamento.

14. Estrelas

As estrelas representam a estrutura e o potencial da empresa.

Podem influenciar:

produtos disponíveis;
receitas;
limite de funcionários;
estoque;
qualidade máxima;
limites operacionais;
outras capacidades específicas.

Estrela não representa automaticamente desempenho.

Uma empresa com mais estrelas pode ter desempenho ruim se possuir funcionários
ou condições inadequadas.

15. Mural de empregos

Deve existir um mural público de vagas.

Fluxo:

vaga aberta
↓
mural público
↓
jogador se candidata
↓
proprietário ou pessoa autorizada aprova
↓
cargo ocupado

O sistema substitui o modelo de contratação direta por nome de jogador como
mecanismo principal de recrutamento.

16. Cargo Dono

Ao fundar uma empresa:

fundador
↓
cargo Dono

O cargo Dono é criado automaticamente.

O cargo Dono não conta para o limite normal de um único emprego contratado.

Assim, é permitido:

Dono da Empresa A
+
funcionário da Empresa B

O fundador define o salário associado ao cargo Dono.

17. Fundação de empresas

Fundar uma empresa possui custo financeiro.

Valores atualmente definidos:

Tipo	Custo
Varejo	R$15.000
Serviços	R$25.000
Matriz	R$40.000
Construtora	R$60.000
Industrial	R$80.000
Financeira	R$100.000

Fundar uma empresa deve representar uma conquista econômica relevante.

Requisitos adicionais, como diplomas, poderão ser aplicados conforme a
documentação de outros sistemas.

18. Qualidade e preço

A qualidade do produto pode influenciar seu preço.

A empresa possui um teto de qualidade relacionado às estrelas.

A qualidade efetiva depende do trabalho dos funcionários.

A estrutura é:

Estrela
→ teto

Funcionários
→ qualidade efetiva

Qualidade efetiva
→ valor percebido/preço

Os multiplicadores de preço e seus efeitos são parâmetros de balanceamento.

19. Relação com o Inventário

Empresas produzem e vendem produtos que podem chegar ao inventário dos
jogadores.

Estrutura:

Empresa
→ estoque empresarial

Varejo
→ vende

Jogador
→ inventário

O inventário é definido em 05 — Inventário.

Transferências diretas de itens entre jogadores utilizam o serviço de correio
e possuem taxa própria.

20. Relação com Produtos e Receitas

O catálogo 22 — Receitas-Produção é a fonte de verdade para:

produtos;
receitas;
categorias;
matérias-primas;
produtos intermediários;
produtos finais;
consumidores;
requisitos de produção;
regras de consumo operacional;
efeitos específicos de produtos.

O sistema de Empresas deve consultar esse catálogo em vez de duplicar listas
de permissões.

21. Economia e concorrência

Empresas devem competir por:

funcionários;
matéria-prima;
clientes;
fornecedores;
localização;
preços;
qualidade.

Empresas não devem ser capazes de ignorar completamente a cadeia produtiva.

A especialização é desejável.

Diferentes empresas produzindo o mesmo produto são desejáveis.

Escassez é desejável quando puder gerar:

preço
→ oportunidade
→ concorrência
→ expansão da oferta

e não simplesmente tornar o jogo impossível.

22. Balanceamento

Os seguintes valores devem permanecer parametrizados:

produção por trabalho;
influência de skill;
influência de especialização;
bônus do Engenheiro;
redução de Burnout do Advogado;
capacidade de venda do Varejo;
estoque por estrela;
quantidade de Engenheiros por estrela;
quantidade de Advogados por estrela;
qualidade máxima por estrela;
relação qualidade/preço;
cooldown de troca de produção;
tempo de setup;
custo de setup;
consumo operacional;
ganho/decadência de especialização.

Esses valores serão calibrados principalmente através dos testes com bots.

A estrutura do sistema deve permanecer estável mesmo quando esses parâmetros
forem alterados.

23. Fora do escopo do Bot Test

Os seguintes sistemas não serão fechados ou implementados neste documento
para o primeiro Bot Test:

sistema completo de Financeira;
Bolsa de Valores;
empréstimos complexos;
cartões;
intervenção financeira;
sistema completo de Transporte;
sistemas econômicos futuros;
múltiplas obras simultâneas;
comércio informal direto entre jogadores;
sistemas avançados de logística.

Esses sistemas poderão ser desenvolvidos posteriormente sem alterar as regras
fundamentais deste documento.

24. Critério de estabilidade para o Bot Test

O sistema de Empresas deve ser considerado estável quando:

os tipos de empresa possuírem responsabilidades claras;
empresas não puderem comprar/vender produtos incompatíveis;
uma empresa produzir apenas um produto por vez;
trabalho e Energia determinarem a produção;
funcionários de suporte influenciarem a operação corretamente;
Varejo possuir separação entre estoque e capacidade de venda;
Construtora utilizar progresso de obra;
especialização possuir ganho, decadência e recuperação;
estrelas definirem limites estruturais;
a cadeia econômica puder funcionar sem depender de regras manuais
específicas para cada transação.

O objetivo do Bot Test será descobrir os valores adequados dessas mecânicas,
e não redefinir sua estrutura fundamental.


### Agora sim

Eu considero esse documento **`FINAL — BOT TEST`**.

E tem uma mudança de processo importante: **depois de salvar esse no GitHub, eu não quero mais ficar remodelando o `02` a cada descoberta pequena**. Se aparecer alguma questão durante a implementação, primeiro verificamos se é:

**ajuste de parâmetro** → deixa para os bots.

**bug/omissão técnica** → Claude corrige.

**nova decisão de design** → volta para nós, abrimos o documento novamente como `REVIEW`.

Isso evita exatamente o retrabalho que você estava tentando eliminar desde o começo.
