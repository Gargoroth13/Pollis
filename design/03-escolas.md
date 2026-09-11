# 03 — Escolas

> **Status:** REVIEW
>
> Este documento define o funcionamento atual do sistema de escolas e
> universidades, consolidando as decisões de design já tomadas.
>
> O documento ainda não é FINAL — BOT TEST porque alguns parâmetros de
> balanceamento e alguns detalhes secundários serão definidos posteriormente.

---

## 1. Visão geral

Educação é um dos principais sistemas de progressão de Polis.

O sistema é dividido em:

- Escolas;
- Cursos;
- Universidades;
- Diplomas.

A educação deve:

- desenvolver skills;
- desenvolver especializações;
- abrir acesso a profissões e oportunidades;
- contribuir para mobilidade social;
- funcionar como parte da economia e da política do mundo.

---

# 2. Escola inicial

Todo jogador novo é associado a uma escola localizada em seu bairro.

Normalmente haverá uma única escola por bairro.

É permitido existir mais de uma escola no mesmo bairro, mas isso não deve ser
a situação predominante.

A escola inicial do jogador é determinada automaticamente.

Caso exista mais de uma escola elegível no bairro, o jogador é inicialmente
atribuído a uma delas.

O jogador pode tentar mudar de escola, mas apenas para outra escola localizada
no mesmo bairro.

---

# 3. Tipos de escola

Existem dois modelos principais:

- Pública;
- Particular.

Os dois modelos coexistem no mundo.

---

# 4. Capacidade das escolas

A capacidade de alunos de uma escola deve acompanhar a capacidade residencial
do bairro.

Regra inicial:

vagas da escola =
número de residências possíveis no bairro × 1,5

O multiplicador deve ser parametrizado para permitir balanceamento posterior.

Exemplo:

bairro com 20 residências
→ capacidade base de 30 alunos

A existência de mais vagas do que residências permite que a capacidade escolar
não seja rigidamente limitada ao número de jogadores atualmente residentes.

5. Escola pública

A escola pública recebe orçamento do governo.

Fluxo de financiamento:

Governo Federal
↓
Governador
↓
Governo Estadual
↓
Prefeito
↓
Orçamento da cidade
↓
Escola Pública

O valor repassado para cada escola depende das regras orçamentárias definidas
pelo sistema de governo e orçamento público.

A escola pública utiliza esse orçamento para manter sua operação.

5.1 Diretor da escola pública

O diretor da escola pública é um funcionário da instituição.

O prefeito define o salário do diretor.

O diretor:

administra a escola;
define os salários dos demais funcionários;
administra os recursos operacionais da escola dentro das regras existentes;
acompanha materiais e qualidade.

O salário do diretor não é definido por ele mesmo.

6. Escola particular

A escola particular é uma instituição controlada por um jogador.

O diretor da escola particular é o proprietário da instituição.

O proprietário:

utiliza seu próprio dinheiro;
contrata funcionários;
define salários;
compra materiais;
administra a instituição;
define o valor cobrado dos alunos.

A escola particular não recebe orçamento público como fonte principal de
financiamento.

6.1 Mensalidade

A cobrança da escola particular é realizada diariamente.

A mensalidade representa um valor periódico que, na implementação, é cobrado
diariamente do aluno.

Caso o aluno não consiga pagar:

inadimplência
→ expulsão da escola

A existência, valor e regras adicionais de mensalidade também podem ser
afetados pela legislação.

7. Qualidade da escola

Cada escola possui uma métrica de qualidade.

A qualidade possui dois componentes principais:

Qualidade da escola
=
Qualidade Base
+
Bônus dos Professores

A qualidade é atualizada diariamente.

8. Qualidade Base

A Qualidade Base é determinada pela quantidade de materiais disponíveis para
a escola.

O estoque de materiais possui um limite máximo definido pela estrela da
escola.

Conceitualmente:

materiais disponíveis
→ determinam a qualidade base

O limite de armazenamento depende do nível de estrelas da escola.

Exemplo:

escola 3★
→ máximo de 1.000 materiais
→ qualidade base máxima de 1.000

Materiais acima da capacidade da escola não podem ser armazenados.

A quantidade exata de materiais por estrela será definida posteriormente.

9. Decaimento dos materiais

Os materiais da escola sofrem decaimento diário.

O estoque utilizado para determinar a qualidade de um determinado dia é o
estoque registrado no ciclo anterior.

Conceitualmente:

Dia D
→ estoque de materiais
↓
Dia D+1
→ qualidade base derivada desse estoque

A taxa de decaimento será definida posteriormente.

10. Professores

Professores são funcionários da escola.

O desempenho de um professor influencia a qualidade operacional da escola.

Cada vez que um professor realiza um trabalho:

trabalho do professor
→ contribui para o bônus de qualidade do dia seguinte

A contribuição depende de:

skill relevante;
especialização como professor;
diminishing returns;
valor base por trabalho.
11. Fórmula de qualidade dos professores

A estrutura conceitual é:

eficiência do professor
=
DiminishingReturns(skill)
×
(1 + especialização × bônus_especialização)

E:

bônus de qualidade
=
trabalhos realizados
×
valor_base_do_trabalho
×
eficiência do professor

A fórmula deve ser parametrizada.

Os valores exatos de:

diminishing returns;
valor base;
bônus de especialização;

serão definidos posteriormente.

12. Ciclo diário de qualidade

O trabalho realizado pelos professores durante um dia gera um bônus utilizado
no dia seguinte.

Exemplo:

Dia 01
Professor trabalha 50 vezes
↓
gera bônus de qualidade

Dia 02
Qualidade =
Qualidade Base
+
bônus gerado no Dia 01

Se o professor não trabalhar no Dia 02, seu trabalho anterior não continua
acumulando indefinidamente:

Dia 03
→ não recebe novo bônus daquele professor

A qualidade operacional deve retornar à Qualidade Base quando não houver novo
bônus proveniente do ciclo anterior.

13. Qualidade e estrelas

As estrelas representam o potencial/estrutura máxima da escola.

Uma escola com mais estrelas possui maior capacidade de armazenamento de
materiais e potencial para alcançar qualidade maior.

Estrelas não representam automaticamente qualidade alta.

Uma escola com muitas estrelas pode apresentar qualidade baixa caso:

tenha poucos materiais;
tenha poucos professores trabalhando;
possua profissionais pouco qualificados;
esteja mal administrada.
14. Cursos

A educação pode aumentar:

skills;
especializações.

Cada especialização deverá possuir um ou mais cursos correspondentes.

Os cursos utilizarão nomes de cursos reais sempre que possível.

Cada curso poderá estar associado a uma ou mais skills dependendo de sua
natureza.

15. Ensino escolar e skills

Durante a fase inicial do jogador:

Estudar
→ desenvolve as 3 skills

A escola funciona como uma fase introdutória do jogo.

A intenção é ensinar o jogador a compreender:

energia;
ações;
estudo;
trabalho;
progressão;
dinheiro;
rotina;
funcionamento básico do mundo.

O jogador não fica limitado exclusivamente à escola durante essa fase.

16. Duração da fase escolar inicial

A duração planejada para a fase escolar inicial é aproximadamente 2 meses no
servidor final.

Para o primeiro Bot Test, a duração poderá ser reduzida para acelerar as
simulações.

O período exato do Bot Test deve ser tratado como parâmetro de simulação e não
como alteração definitiva do design.

17. Universidade

Universidades oferecem cursos mais especializados.

Cada jogador pode estar matriculado em apenas um curso universitário por vez.

Cursos possuem:

requisitos;
duração;
custo;
progressão de skills;
progressão potencial de especialização;
diploma correspondente.
18. Requisitos universitários

Os requisitos dependem do curso.

Exemplos atualmente previstos:

Medicina
→ INT ≥ 100
Engenharia
→ INT ≥ 100
→ FIS ≥ 100
Direito
→ INT ≥ 100
→ CAR ≥ 100

Cursos diferentes podem exigir combinações diferentes de skills.

Os requisitos completos devem ser definidos curso a curso.

19. Duração dos cursos

Cursos universitários devem possuir duração significativamente menor que a fase
escolar inicial.

A referência atual é aproximadamente:

1 mês

O valor exato pode variar entre cursos e deve ser definido posteriormente.

20. Estudo e energia

Estudar consome energia.

A quantidade de estudo realizado pelo jogador é limitada pela energia
disponível.

Quanto mais energia o jogador estiver disposto a gastar estudando:

mais estudo
→ maior ganho diário de skills

Portanto estudar não é obrigatório para obter o diploma.

O jogador pode escolher entre:

estudar muito
→ maior progressão acadêmica
→ menos energia disponível para outras atividades

ou:

estudar pouco
→ progresso menor
→ mais energia disponível para trabalho e outras atividades
21. Trabalho durante a universidade

O jogador pode trabalhar enquanto estiver matriculado em um curso.

A quantidade de energia dedicada a trabalho ou estudo é decisão do próprio
jogador.

O jogador deve administrar sua energia entre:

trabalho;
estudo;
outras atividades.
22. Abandono de curso

O jogador pode abandonar um curso.

Abandonar um curso:

não apaga o progresso realizado;
não aplica uma punição significativa;
permite retorno futuro;
permite continuar de onde o jogador parou.

Não é permitido manter dois cursos universitários simultaneamente.

23. Conclusão e diploma

Ao concluir um curso, o jogador recebe um diploma.

O diploma é permanente.

Uma vez obtido:

curso concluído
→ diploma permanente

O diploma pode posteriormente servir como requisito para:

profissões;
cargos;
empresas;
outras oportunidades.
24. Educação e economia

Escolas fazem parte da economia do jogo.

Elas podem contratar:

professores;
diretores;
outros funcionários.

Esses funcionários possuem:

skills;
salários;
energia;
especializações.

Professores geram qualidade através do trabalho.

Isso cria o ciclo:

funcionário
→ skill
→ especialização
→ trabalho
→ qualidade da escola
→ formação dos alunos
→ novos profissionais
25. Educação pública e política

A educação pública faz parte das decisões do governo.

O orçamento disponível para escolas depende da estrutura de orçamento público.

Leis podem posteriormente influenciar:

mensalidades;
financiamento;
acesso;
condições de ensino;
outros aspectos da educação.

Isso permite que educação seja uma questão política real dentro do jogo.

26. Desigualdade e mobilidade social

A qualidade da educação pode variar de acordo com:

bairro;
condição econômica;
estrutura da instituição;
recursos disponíveis;
qualidade dos profissionais;
decisões políticas.

Jogadores podem começar com oportunidades diferentes.

A mobilidade social deve existir, mas não deve depender exclusivamente do
esforço individual.

A estrutura social, as oportunidades, as instituições e as decisões políticas
devem possuir influência significativa sobre a trajetória do jogador.

O objetivo é permitir que:

origem social
→ influencie a trajetória

sem tornar:

origem social
→ destino inevitável
27. Balanceamento

Os seguintes parâmetros devem permanecer configuráveis para posterior
balanceamento:

quantidade de materiais por estrela;
capacidade de alunos;
taxa de decaimento de materiais;
valor base do trabalho do professor;
impacto da skill;
diminishing returns;
bônus de especialização;
ganho de skill por estudo;
duração dos cursos;
duração da fase escolar;
custos;
mensalidades;
orçamento público;
salários.

O objetivo desta etapa é definir as regras estruturais.

O balanceamento será testado posteriormente através dos bots.

28. Questões em aberto
Quantidade exata de materiais por estrela.
Taxa de decaimento dos materiais.
Fórmula final de diminishing returns.
Valor base do trabalho do professor.
Impacto exato da especialização de professor.
Lista completa de cursos e especializações.
Requisitos individuais dos cursos.
Custos individuais.
Duração individual dos cursos.
Valores de mensalidade.
Modelo detalhado de orçamento das escolas públicas.
Regras de lotação e transferência entre escolas quando houver mais de uma
no bairro.
Detalhes adicionais da gestão de escolas públicas e privadas.
29. Fora do escopo

Este documento não define detalhadamente:

orçamento público;
leis;
geografia;
imóveis;
sistema completo de empregos;
transporte;
atividades de lazer;
sistema geral de QoL.

Esses sistemas possuem ou possuirão documentação própria.

Este documento define apenas como o sistema de educação se conecta a eles.


### Uma mudança que eu considero particularmente importante

Eu **não coloquei "30 alunos" como valor definitivo**, apenas:

```text
vagas = residências × 1,5

Isso é uma regra estrutural excelente para o sistema, enquanto 1,5 fica parametrizado para os bots. Assim, depois podemos descobrir algo como:

1,2 produz escolas lotadas demais
1,5 funciona bem
2,0 deixa escolas vazias

sem reescrever o sistema.
