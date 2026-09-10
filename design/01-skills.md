# 01 — Skills

> **Status:** REVIEW
>
> Este documento contém as regras de design atualmente definidas para o sistema
> de skills, mas ainda não deve ser tratado como especificação final de
> implementação para o Bot Test.
>
> Algumas decisões de balanceamento dependem dos resultados das simulações com
> bots e de documentos relacionados, principalmente Empresas, Escolas e Política.

---

## 1. Visão geral

Existem apenas 3 skills de jogador:

- Inteligência
- Físico
- Carisma

As antigas categorias de jogador (Indústria, Comércio, Tecnologia etc.) foram
removidas e não existem mais como skills individuais. Essas categorias passam a
ser classificações de empresas.

As três skills crescem infinitamente.

O nível inicial das skills é definido pelo contexto de nascimento do personagem,
incluindo o bairro/faixa de renda, conforme definido pelo sistema de criação do
jogador.

---

## 1.1 Filosofia de progressão

O jogador **não escolhe diretamente qual skill aumentar**.

A atividade realizada determina qual skill, ou conjunto de skills, será
desenvolvido.

Isso significa que a progressão da personagem é consequência de suas escolhas
de vida, e não apenas de uma distribuição manual de pontos.

Exemplos:

- escola → desenvolvimento das 3 skills;
- emprego → desenvolvimento da skill relevante do cargo;
- atividades específicas → podem desenvolver uma ou mais skills;
- freelance → desenvolvimento mínimo, funcionando principalmente como rede de
  segurança.

A especialização deve surgir naturalmente das atividades escolhidas pelo jogador.

---

## 1.2 Como cada skill cresce

As principais fontes de desenvolvimento são:

| Fonte | Efeito |
|---|---|
| Trabalho | Desenvolve a skill relevante do cargo. O ganho é menor que o ganho por estudo. |
| Escola / Universidade | Desenvolve skills mais rapidamente que o trabalho. |
| Atividades de lazer / grupos de estudo | Podem desenvolver uma ou mais skills fora da educação formal. |
| Freelance | Permite algum desenvolvimento, mas deve ser uma fonte menos eficiente de progresso. |

Uma atividade pode depender de mais de uma skill quando isso fizer sentido para a
atividade.

Não é necessário que todas as atividades utilizem apenas uma skill.

Ao mesmo tempo, múltiplas skills só devem ser utilizadas quando houver uma
justificativa real de design, e não apenas para aumentar a complexidade.

---

## 1.3 Fórmula base de ganho

A fórmula atualmente definida para o ganho de skill é:

ganho_base = QoL_base × qualidade_da_escola × ganho_base_da_atividade

Exemplos:

QoL 1.0 × escola 1.0 × ganho base 1.0 = 1.0
QoL 0.5 × escola 1.0 × ganho base 1.0 = 0.5
QoL 0.5 × escola 0.5 × ganho base 1.0 = 0.25

A fórmula deve ser implementada de forma parametrizada, para que os valores
possam ser ajustados posteriormente durante o balanceamento com bots.

O ganho final também poderá ser afetado pelo diminishing returns descrito na
seção 1.5.

1.4 Escola como fase inicial do jogador

Durante a fase inicial da conta, a escola funciona como uma espécie de
prólogo jogável.

A intenção é que o novo jogador aprenda progressivamente:

uso de energia;
realização de ações;
trabalho;
estudo;
desenvolvimento de skills;
obtenção e gasto de dinheiro;
rotina básica do jogo.

Durante essa fase, o jogador não fica limitado exclusivamente à escola e pode
interagir com outros sistemas do jogo.

A duração atualmente considerada é de 2 meses, mas esse valor ainda não é
definitivo e poderá ser revisado após testes.

Durante a fase escolar inicial:

Estudar → desenvolve as 3 skills

A escola em que o jogador inicia também pode influenciar o nível inicial ou o
ritmo de desenvolvimento, de acordo com as regras do sistema de educação.

1.5 Diminishing returns

As skills não possuem um limite máximo.

Entretanto, níveis maiores devem exigir progressivamente mais tempo e esforço
para serem aumentados.

A intenção é criar uma curva de diminishing returns:

skill maior
↓
mesma atividade gera proporcionalmente menos progresso
↓
especialização extrema exige muito tempo

A fórmula exata ainda não está fechada.

Uma fórmula em faixas de 100 pontos foi considerada anteriormente, mas não deve
ser tratada como definitiva.

O sistema deve ser implementado de maneira parametrizada, permitindo alterar
facilmente a curva durante o balanceamento.

O formato final da curva será definido depois que os bots puderem simular
progressão durante períodos longos.

1.6 Skills e produção

A skill relevante de um funcionário influencia sua capacidade produtiva.

Em sistemas de empresa que utilizem uma skill específica:

skill relevante maior
→ maior eficiência produtiva

A relação exata entre nível da skill e produção deve permanecer parametrizada
para permitir balanceamento posterior.

1.7 Skills e salário

A skill relevante também pode determinar um limite de salário para impedir
que jogadores veteranos utilizem salários artificialmente altos para transferir
grandes quantidades de dinheiro para personagens novos.

A regra atualmente definida é:

salário máximo = nível da skill relevante × multiplicador salarial

O multiplicador atual considerado é:

1.5

Exemplo:

Físico 100
× 1.5
= salário máximo de R$150
Período do limite

O limite salarial é diário, e não por clique de trabalho.

A implementação deve manter um contador simples do total recebido pelo jogador
naquele dia.

Exemplo conceitual:

ganho_hoje
data_referência

Quando o dia mudar, ganho_hoje é reiniciado.

Se um pagamento fizer o jogador ultrapassar o limite diário:

o pagamento é reduzido para o valor restante disponível

O trabalho não é bloqueado; apenas o valor efetivamente recebido é limitado.

Evolução futura

Existe interesse em transformar esse limite em uma decisão política do mundo.

Uma possibilidade é o governo definir, por lei, o multiplicador utilizado na
fórmula:

salário máximo = skill × X

Nesse modelo:

X baixo
→ maior controle econômico

X alto
→ maior liberdade econômica
→ maior risco de concentração e abuso

Essa possibilidade ainda precisa ser avaliada em conjunto com o sistema de
Política e Leis antes de ser considerada uma regra final.

Independentemente disso, algum mecanismo de proteção contra transferências
artificiais de riqueza deve existir para preservar a integridade econômica do
jogo.

1.8 Relevância das três skills

As três skills devem possuir caminhos legítimos de progressão econômica.

Inteligência

Deve ter relevância em áreas como:

cargos intelectuais;
educação;
pesquisa;
gestão;
outras atividades cognitivas.
Físico

Deve possuir caminhos economicamente relevantes, especialmente por meio de
cargos e setores que dependam de capacidade física ou operacional.

Exemplos potenciais:

construção;
indústria;
transporte;
operações;
segurança;
outros setores que façam sentido para o jogo.

Físico não deve existir apenas como uma "skill secundária" destinada a trabalhos
de baixa remuneração.

Carisma

Deve ter relevância principalmente em áreas envolvendo:

negociação;
atendimento;
vendas;
liderança;
política;
relações sociais;
outras atividades baseadas em interação.

A distribuição exata dos cargos entre as três skills será refinada durante a
definição dos sistemas de Empresas, Política e demais atividades.

1.9 Requisitos de skill

Skills não servem apenas como multiplicadores.

Determinadas atividades e cargos podem exigir um nível mínimo de uma ou mais
skills para que o jogador possa se candidatar ou acessar aquela função.

Exemplos:

cargos de gestão;
cargos políticos;
cargos de pesquisa;
profissões especializadas.

A mecânica deve reutilizar o sistema de requisitos já existente para cargos
sempre que possível.

Uma atividade pode exigir mais de uma skill.

Exemplo conceitual:

Atividade X:
INT ≥ 100
FIS ≥ 75

Isso permite criar especializações mais complexas sem transformar todas as
atividades em sistemas excessivamente complexos.

1.10 Progressão infinita

A progressão das skills é deliberadamente infinita.

Um jogador veterano deve poder possuir vantagens significativas sobre alguém que
começou recentemente.

Essas vantagens podem incluir:

maior skill;
acesso a cargos melhores;
maior capacidade produtiva;
maior potencial de renda;
maior acesso a oportunidades;
maior capacidade de disputar posições políticas;
outras vantagens acumuladas pela experiência.

O objetivo não é impedir a diferença entre veteranos e novatos.

O objetivo é evitar que essa vantagem se transforme em uma progressão
completamente irreversível ou em um sistema no qual uma única skill seja sempre
a melhor escolha.

O balanceamento entre progressão e snowball será avaliado principalmente através
das simulações com bots.

1.11 Freelance

Freelance existe como um caminho alternativo ao emprego formal.

A intenção não é tornar freelance inútil.

Um jogador pode potencialmente construir uma carreira forte como freelancer,
mas isso deve exigir mais dedicação e/ou apresentar desvantagens em relação ao
emprego formal.

Freelance deve oferecer:

liberdade;
possibilidade de crescimento;
possibilidade de especialização;

mas não deve ser automaticamente a opção economicamente dominante.

Também funciona como rede de segurança para jogadores que estejam sem emprego.

O ganho inicial de dinheiro e skill deve ser baixo, mas o sistema pode permitir
que um jogador dedicado cresça significativamente através dele.

Os detalhes econômicos do freelance serão definidos no sistema correspondente.

1.12 Balanceamento

O balanceamento profundo das skills não será finalizado nesta etapa do
design.

Antes da execução dos bots, devemos apenas garantir que:

as regras estejam claras;
as fórmulas estejam parametrizadas;
as três skills tenham caminhos relevantes;
o sistema suporte progressão infinita;
não existam dependências arquiteturais desnecessárias;
os números importantes possam ser ajustados sem grandes alterações de código.

Após a criação dos bots, serão avaliados:

velocidade de progressão;
distribuição das skills;
concentração em uma skill específica;
diferença entre veteranos e novatos;
impacto econômico das skills;
viabilidade de diferentes estilos de vida;
risco de snowball;
efeito de requisitos de skill;
equilíbrio entre emprego e freelance.
2. Decisões em aberto

As seguintes questões ainda não devem ser consideradas finalizadas:

Fórmula exata do diminishing returns.
Multiplicador salarial definitivo.
Se o multiplicador salarial poderá ser alterado por lei.
Duração exata da fase escolar inicial.
Distribuição definitiva dos cargos entre Inteligência, Físico e Carisma.
Quais atividades específicas utilizarão múltiplas skills.
Relação exata entre skill e produção.
Balanceamento dos ganhos de skill por atividade.
Balanceamento de freelance.
Quais atividades existem fora de trabalho e estudo e quais skills elas
desenvolvem.

Essas decisões devem ser resolvidas antes de marcar este documento como:

FINAL — BOT TEST

3. Princípios que não devem ser alterados sem revisão
Existem apenas três skills: Inteligência, Físico e Carisma.
Skills crescem infinitamente.
O jogador não distribui pontos manualmente para escolher qual skill subir.
A atividade realizada determina o desenvolvimento das skills.
Progressão de veteranos deve ser significativamente maior que a de novatos.
Veteranos não devem ser artificialmente nivelados aos novatos.
O sistema deve ser parametrizado para permitir balanceamento posterior.
As três skills devem possuir caminhos economicamente relevantes.
Algum mecanismo anti-abuso deve impedir transferências artificiais de riqueza
que destruam a progressão econômica.
