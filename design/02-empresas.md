# 02 — Empresas

> **Status:** REVIEW
>
> Este documento define o funcionamento atual do sistema de empresas,
> consolidando as decisões de design já tomadas.
>
> O documento ainda não é FINAL — BOT TEST porque algumas partes, especialmente
> Financeira e Transporte, ainda precisam de revisão e algumas variáveis de
> balanceamento serão definidas posteriormente através dos bots.

---

## 1. Visão geral

Empresas são uma das principais estruturas econômicas de Polis.

A economia é formada principalmente por empresas controladas por jogadores,
com funções diferentes dentro da cadeia produtiva.

Os principais tipos de empresa são:

- Varejo
- Serviços
- Matriz
- Construtora
- Industrial
- Financeira

Financeira é uma especialização de Serviços.

A localização da empresa é relevante para algumas regras e, no caso das
Matrizes, determina a categoria de recurso que pode ser explorada.

---

# 2. Tipos de empresa

## 2.1 Matriz

A Matriz é a porta de entrada da cadeia produtiva.

Sua função principal é extrair matérias-primas diretamente do ambiente.

A Matriz:

- não precisa consumir matéria-prima para produzir;
- consome apenas materiais operacionais necessários à atividade;
- possui margens menores que empresas posteriores da cadeia;
- vende as matérias-primas para empresas que realmente possam consumi-las.

A categoria da Matriz é determinada pelo tipo de terreno em que ela está
localizada.

Exemplos conceituais:

Terreno Agro
→ Matriz Agro
Terreno Mineral
→ Matriz Mineral

O terreno define a categoria macro da Matriz.

O proprietário escolhe qual produto produzir dentro daquela categoria, desde
que possua uma receita/produção válida para isso.

Exemplo

Uma Matriz Agro pode escolher entre diferentes produtos pertencentes à
categoria Agro.

Ela não pode escolher livremente produtos fora da categoria determinada pelo
terreno.

2.2 Industrial

Indústrias transformam matérias-primas e produtos intermediários em outros
produtos.

Podem:

comprar materiais operacionais;
comprar matérias-primas de Matrizes;
comprar produtos intermediários de outras Industriais;
vender produtos para empresas que os utilizem;
fornecer produtos ao Varejo quando esses produtos forem destinados ao
consumidor final;
fornecer produtos para outras empresas, incluindo Construtoras, quando
houver consumo válido.

A Industrial não possui acesso irrestrito ao catálogo.

Sua capacidade de compra e venda depende das receitas e operações que a empresa
possui.

2.3 Varejo

O Varejo é a etapa final da cadeia empresarial antes do consumidor.

Sua função é:

comprar produtos
↓
disponibilizá-los ao consumidor

Um Varejo não pode comprar qualquer produto.

Ele só pode comprar produtos compatíveis com sua atividade e seu catálogo de
venda.

Exemplo

Um Varejo especializado em automóveis não pode comprar móveis.

Um Varejo especializado em móveis não pode comprar automóveis sem possuir uma
atividade/receita que permita isso.

### Consumo operacional (mecânica nova) 🤝

Empresas e instituições agora **consomem** produtos continuamente pra
funcionar, não só o jogador:

| Quem consome | Consome |
|---|---|
| Escolas/Universidades | Uniformes + Materiais escolares |
| Hospitais | Uniformes + Materiais hospitalares |
| Matriz e Industrial | EPIs + Uniformes (gasto por funcionário a cada trabalho) |
| Varejo e Serviços | Uniformes |

2.4 Serviços

Empresas de Serviços fornecem atividades diretamente para jogadores ou outras
entidades.

As categorias inicialmente planejadas incluem:

Transporte
Publicidade
Lazer

Financeira é tratada como uma especialização específica de Serviços.

As regras detalhadas de cada serviço serão definidas nos sistemas
correspondentes.

2.5 Construtora

A Construtora transforma insumos da cadeia industrial em imóveis prontos.

O processo conceitual é:

Materiais de Construção
+
Acabamentos
↓
Imóvel

Construtoras não utilizam Móveis como insumo de construção.

Móveis são produtos separados, utilizados posteriormente pelo jogador para
mobiliar e melhorar sua residência.

2.6 Financeira

Financeira é uma especialização de Serviços e representa uma empresa de
endgame.

Pode fornecer:

depósitos/poupança;
empréstimos;
cartões de crédito;
transferências;
outros produtos financeiros.

O sistema financeiro possui regras próprias de:

reserva obrigatória;
rating;
juros;
falência;
intervenção.

A definição completa da Financeira ainda está em REVIEW.

3. Cadeia econômica

A economia deve incentivar especialização e interdependência entre empresas.

Estrutura conceitual:

Matriz
↓
Industrial
↓
Industrial / Varejo / Construtora / outras empresas consumidoras
↓
Jogador

Nem todas as cadeias passam por todas as etapas.

Uma matéria-prima pode ser transformada várias vezes antes de chegar ao
consumidor.

A existência de múltiplas empresas produzindo o mesmo produto é desejável,
pois cria:

concorrência;
escassez;
variações de preço;
arbitragem;
oportunidades para novos empresários;
pressão econômica e política.

Uma economia em que uma empresa consegue produzir praticamente tudo deve ser
evitada.

4. Permissões de compra e venda

A regra central do comércio empresarial é:

Produto
↓
usos permitidos
↓
empresas capazes de consumi-lo

Uma empresa só pode comprar um produto se esse produto for uma entrada válida
para alguma operação, atividade ou receita daquela empresa.

Da mesma forma, uma empresa só pode vender um produto para empresas que tenham
um uso válido para ele.

A permissão comercial deve ser derivada do catálogo de produtos e receitas,
evitando listas independentes e duplicadas de permissões.

Exemplos

Se Ferro for utilizado em uma receita de produção de Aço:

Matriz de Ferro
→ pode vender Ferro
→ Industrial que produz Aço pode comprar Ferro

Uma empresa que não possua qualquer uso válido para Ferro não pode comprá-lo.

Se uma Industrial produz um produto que é consumido por uma Construtora:

Industrial
→ pode vender o produto
→ Construtora pode comprar

O mesmo princípio se aplica ao Varejo.

Um Varejo só pode comprar produtos que sejam compatíveis com sua atividade.

5. Produção
5.1 Um produto por vez

Cada empresa produtiva trabalha com um único produto de produção por vez.

Isso vale principalmente para Matriz e Industrial.

O objetivo é estimular:

especialização;
concorrência;
criação de múltiplas empresas;
dependência econômica;
decisões estratégicas de produção.

Uma empresa não deve funcionar como uma fábrica universal capaz de produzir
diversos produtos simultaneamente.

5.2 Seleção do produto

O proprietário da empresa escolhe qual produto a empresa está produzindo.

A seleção deve respeitar:

tipo da empresa;
categoria;
terreno, quando aplicável;
receitas disponíveis;
requisitos de estrelas;
demais restrições da empresa.

Funcionários não escolhem o produto.

5.3 Mudança de produção

A troca do produto produzido possui três formas de fricção:

troca de produto
+
custo fixo
+
tempo de setup
+
cooldown longo

Durante o setup:

a empresa fica fora de operação;
nenhum funcionário pode trabalhar;
a empresa não produz.

O cooldown entre alterações de produção deve ser de aproximadamente 1 semana.

O valor exato e a duração exata do setup serão definidos posteriormente
através de balanceamento.

O estoque existente não é destruído quando a empresa muda de produção.

6. Trabalho dos funcionários

A produção empresarial é baseada na contribuição dos funcionários.

O proprietário define a atividade/produto da empresa.

O funcionário decide quanto de sua energia deseja gastar trabalhando.

Conceitualmente:

energia gasta
↓
trabalho realizado
↓
produção gerada
+
ganho de skill

Quanto mais energia o funcionário utiliza:

maior a produção gerada;
maior o ganho de skill;
maior a contribuição para a empresa.

A quantidade exata produzida por unidade de energia será parametrizada para
balanceamento posterior.

7. Relação entre funcionário e proprietário

O sistema deve permitir que o proprietário da empresa estabeleça padrões de
trabalho e recompense ou puna funcionários conforme sua atuação.

O proprietário pode, de acordo com as regras do sistema:

definir expectativas mínimas;
definir salário;
promover;
conceder bônus;
demitir.

O funcionário, por sua vez:

escolhe quanto trabalhar;
decide se permanece na empresa;
pode procurar outro emprego;
pode buscar empresas que valorizem melhor sua contribuição.

A relação deve funcionar como uma relação de trabalho emergente, em que a
empresa e o funcionário possuem interesses parcialmente alinhados, mas não
necessariamente idênticos.

8. Cargo Dono

Ao fundar uma empresa, o fundador recebe automaticamente o cargo de Dono.

O cargo Dono não conta para o limite normal de um único emprego contratado.

Assim:

Dono da Empresa A
+
Funcionário da Empresa B

é permitido.

O fundador define o salário associado ao cargo Dono.

9. Especialização dos funcionários

Funcionários desenvolvem especialização conforme trabalham em determinada área
ou produto.

A especialização melhora a eficiência do funcionário naquela atividade.

A especialização não é totalmente permanente.

Decaimento

Quando uma especialização deixa de ser utilizada:

especialização
↓
decai lentamente ao longo do tempo

A decadência deve ocorrer em ritmo diário baixo.

A especialização nunca deve cair abaixo de 50% do maior valor já atingido
naquela especialização.

Recuperação

Quando o jogador volta a trabalhar em uma área antiga, sua especialização se
recupera mais rapidamente.

A velocidade de recuperação será aproximadamente:

1.5× a velocidade normal

Os valores exatos de decadência e recuperação serão balanceados posteriormente
com bots.

O histórico de especialização deve continuar existindo para que experiência
anterior tenha valor mesmo depois de uma mudança de carreira.

10. Produção e funcionários de suporte

Nem todo funcionário precisa gerar produção diretamente.

Existem funções de suporte que aumentam a eficiência da operação.

Os exemplos atualmente considerados incluem:

10.1 Engenheiro

Cada trabalho realizado pelo Engenheiro aumenta a eficiência dos demais
funcionários da empresa em uma pequena porcentagem.

O efeito deve ser limitado pela energia disponível para o Engenheiro.

Conceitualmente:

energia do Engenheiro
↓
trabalhos realizados
↓
bônus de eficiência dos funcionários

O bônus exato por trabalho ainda será balanceado.

10.2 Advogado

Cada trabalho realizado pelo Advogado reduz a chance de os funcionários da
empresa sofrerem burnout.

O efeito também é limitado pela energia disponível para o Advogado.

Conceitualmente:

energia do Advogado
↓
trabalhos realizados
↓
menor risco de burnout

O valor exato da redução será balanceado posteriormente.

Outros cargos de suporte poderão ser adicionados futuramente quando houver
justificativa de design.

11. Burnout

Trabalhar repetidamente em grande intensidade deve possuir um custo.

Cada trabalho consecutivo pode aumentar o risco de burnout.

Conceitualmente:

trabalho
↓
burnout aumenta
↓
trabalho consecutivo
↓
risco aumenta

Ao atingir o limite de burnout:

burnout máximo
↓
jogador fica temporariamente impedido de trabalhar

O bloqueio dura um período definido pelo sistema.

Algumas atividades de descanso ou recuperação podem reduzir burnout.

Trabalhar mais deve continuar sendo vantajoso, mas deve criar um risco
crescente de exaustão.

O sistema deve permitir escolhas como:

trabalhar muito
→ maior produção
→ maior ganho de skill
→ maior risco de burnout

Os números exatos serão definidos durante o balanceamento.

12. Operacionais

Algumas empresas consomem produtos operacionais de forma recorrente.

Esses produtos não representam necessariamente matéria-prima da principal
produção.

Exemplos de consumidores incluem:

Escolas;
Hospitais;
Matrizes;
Industriais;
Varejos;
Serviços.

A frequência de consumo pode variar conforme o tipo de produto e atividade.

Produtos que representam equipamentos de longa duração não devem ser tratados
automaticamente como consumíveis de cada trabalho.

A frequência de consumo deverá ser definida por produto/operação.

13. Qualidade e estrelas

Empresas possuem nível de qualidade representado por estrelas.

As estrelas influenciam o potencial econômico da empresa.

Entre os efeitos previstos estão:

acesso a receitas;
acesso a produtos mais complexos;
qualidade da produção;
capacidade de disputar determinados mercados;
valor/preço percebido.

Empresas com maior estrela podem acessar receitas mais avançadas.

A relação exata entre estrelas, qualidade e preços ainda será balanceada.

14. Qualidade do produto e preço

A qualidade de um produto pode influenciar seu preço.

Conceitualmente:

qualidade maior
→ maior valor percebido
→ preço potencialmente maior

Produtos podem possuir qualidade diferente dependendo da empresa e do processo
de produção.

Os multiplicadores exatos serão definidos através do balanceamento com bots.

15. Vagas de emprego

Deve existir um mural público de vagas.

O jogador pode visualizar cargos vagos disponíveis.

A candidatura ocorre através do mural.

A contratação depende da aprovação do proprietário ou de uma futura estrutura
de administração da empresa.

O sistema deve substituir o modelo em que o proprietário simplesmente informa o
nome de qualquer jogador para contratá-lo.

16. Varejo e disponibilidade

O Varejo deve funcionar como uma etapa real da cadeia econômica.

A existência de um produto no mundo não significa que ele esteja
automaticamente disponível para qualquer jogador.

O produto precisa:

ser produzido
→ chegar ao Varejo apropriado
→ possuir disponibilidade operacional
→ ser vendido ao consumidor

O objetivo é permitir:

escassez;
variações de preço;
diferenças regionais;
oportunidades de mercado.

A economia normal deve ser composta por empresas controladas por jogadores.

17. Sistema de segurança para necessidades básicas

A economia deve continuar essencialmente baseada em jogadores.

Entretanto, o sistema pode possuir mecanismos mínimos de segurança para impedir
que um bairro completamente abandonado torne o jogo impraticável.

Exemplo:

bairro sem empresas de alimentação
↓
serviço emergencial controlado pelo sistema
↓
alimento disponível
↓
QoL pior

Esse mecanismo não deve funcionar como uma empresa NPC normal nem competir
economicamente com jogadores.

Ele existe apenas como fallback para necessidades básicas.

18. Construtora

A Construtora utiliza produtos industriais como insumos.

A receita base atualmente prevista é:

Materiais de Construção
+
Acabamentos
→ Imóvel
Acabamentos

Acabamentos são um produto industrial separado de Móveis.

Receita:

Tábuas
+
Vidro
→ Acabamentos

Acabamentos são utilizados na construção dos imóveis.

Móveis

Móveis continuam sendo produtos separados.

Eles não são necessários para que a Construtora conclua a construção de um
imóvel.

Podem posteriormente ser adquiridos pelo jogador para melhorar sua residência.

19. Transporte

O sistema de Transporte existe principalmente para influenciar a relação
entre geografia, trabalho e vida cotidiana.

A filosofia atual é:

início
→ jogador vive principalmente no próprio bairro

progressão
→ jogador amplia seu alcance para outras regiões

Transporte deve incentivar o jogador a encontrar emprego e atividades perto
de onde mora, sem impedir completamente deslocamentos maiores.

Sair do bairro deve ser possível, mas idealmente representa uma expansão gradual
do horizonte do jogador.

O sistema atual de Transporte está considerado insatisfatório e será
redesenhado antes da implementação definitiva.

20. Financeira

Financeira é considerada uma empresa de endgame e deve possuir profundidade
significativamente maior que os demais tipos de empresa.

Os sistemas previstos incluem:

depósitos;
empréstimos;
cartão de crédito;
transferências;
reserva obrigatória;
rating de solvência;
juros;
falência;
recuperação;
intervenção.

A complexidade desse sistema é intencional.

20.1 Falência

A falência não deve funcionar como reset econômico.

Ao entrar em recuperação:

a dívida continua existindo;
parte da renda futura pode ser automaticamente destinada ao pagamento;
o jogador pode realizar pagamentos adicionais;
o jogador não pode fundar novas empresas enquanto a dívida estiver pendente;
o acesso a crédito é restringido;
o acesso a determinados cargos políticos é restringido.

A porcentagem da renda destinada ao pagamento será definida posteriormente.

20.2 Fraude

O sistema deve considerar explicitamente a possibilidade de um jogador tentar
utilizar uma Financeira de maneira fraudulenta.

Fraude pode gerar consequências como:

perda de reputação;
deterioração do rating;
restrição de acesso a crédito;
restrição de criação de empresas;
consequências políticas;
outras punições futuras.

O sistema precisa impedir que captar depósitos e quebrar deliberadamente seja
uma estratégia economicamente ótima.

20.3 Rating

Financeiras devem possuir informação pública sobre sua saúde financeira.

O rating deve ser influenciado por fatores como:

solvência;
histórico;
obrigações;
comportamento financeiro.

A fórmula definitiva do rating ainda será detalhada.

21. Fundação de empresas

Fundar uma empresa possui custo financeiro.

Custos atuais:

Tipo	Custo
Varejo	R$15.000
Serviços	R$25.000
Matriz	R$40.000
Construtora	R$60.000
Industrial	R$80.000
Financeira	R$100.000

Fundar empresas deve representar uma conquista econômica significativa.

A Fundação é considerada uma das formas de progressão de longo prazo.

A criação de determinadas empresas pode futuramente depender de requisitos
adicionais, como diplomas.

22. Produtos, receitas e especializações

O sistema deve tratar produtos e receitas como dados centrais do jogo.

Uma receita define, entre outras coisas:

entradas;
produto produzido;
requisitos;
estrelas mínimas;
tipo de empresa permitido;
categoria de operação.

Essas informações devem ser utilizadas para validar automaticamente:

compra;
venda;
produção;
elegibilidade da empresa.

O sistema deve evitar regras duplicadas espalhadas pelas diferentes views.

23. Princípios econômicos

O sistema de empresas deve favorecer:

especialização;
concorrência;
escassez;
interdependência;
formação de cadeias produtivas;
mercados regionais;
entrada de novos jogadores;
decisões empresariais.

Um jogador não deve conseguir transformar uma única empresa em uma solução
universal para toda a economia.

Ao mesmo tempo, a economia não deve depender de uma única empresa ou jogador
para manter necessidades essenciais funcionando.

24. Balanceamento

Os seguintes elementos devem ser parametrizados e considerados candidatos a
balanceamento através de bots:

produção por unidade de energia;
impacto de skill na produção;
diminishing returns;
bônus do Engenheiro;
redução de burnout do Advogado;
especialização;
decadência da especialização;
recuperação da especialização;
cooldown de troca de produção;
tempo de setup;
custo de setup;
impacto de estrelas;
preço relacionado à qualidade;
consumo operacional;
retenção de renda para recuperação de dívida;
juros;
rating;
limites financeiros.

O objetivo desta etapa não é encontrar os números perfeitos, mas construir um
sistema internamente consistente e fácil de ajustar.

25. Questões em aberto

As seguintes decisões continuam em REVIEW:

Regras detalhadas de compra e venda por categoria de empresa.
Valores exatos de produção por energia.
Fórmula final do bônus do Engenheiro.
Fórmula final do efeito do Advogado.
Frequência de consumo dos produtos operacionais.
Valor exato do cooldown e setup de produção.
Sistema completo de Transporte.
Detalhes completos da Financeira.
Fórmula e consequências finais de rating.
Sistema completo contra fraude.
Regras detalhadas de qualidade e estrelas.
Valores de balanceamento em geral.
26. Fora do escopo deste documento

Este documento não define detalhadamente:

educação;
geografia e lotes;
imóveis;
população;
política;
leis;
sistema completo de transporte;
atividades gerais do jogador.

Esses sistemas possuem documentação própria.

Quando uma empresa depender deles, este documento deve definir apenas a
interface entre os sistemas, deixando a implementação específica para o
documento responsável.


### Uma mudança importante que fiz

Eu **não coloquei `Financeira` como "praticamente pronta"**, mesmo que boa parte já exista no código. Para o nosso propósito de `FINAL — BOT TEST`, o design financeiro ainda está longe de fechado. Assim evitamos que o Claude leia algo existente no código e assuma que já é a regra definitiva.

Também deixei **Transporte explicitamente em REVIEW**, em vez de fingir que a versão atual está pronta.

E mantive os números que já decidimos, mas marquei como **balanceáveis** onde ainda não temos certeza.

Eu salvaria essa versão como está em `design/02-empresas.md` e manteria:

> **Status: REVIEW**

