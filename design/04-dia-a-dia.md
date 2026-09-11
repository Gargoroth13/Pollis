# 04 — Dia a Dia

> **Status:** REVIEW
>
> Este documento define o funcionamento geral do ciclo diário do jogador,
> incluindo Energia, QoL, Saúde, Nutrição, Burnout, Lazer e deslocamento.
>
> O documento ainda não é FINAL — BOT TEST porque alguns parâmetros de
> balanceamento e detalhes de sistemas relacionados ainda serão definidos.

---

# 1. Visão geral

O sistema de Dia a Dia representa o conjunto de ações e estados que determinam
a rotina do jogador.

Os principais sistemas são:

- Energia;
- Qualidade de Vida (QoL);
- Saúde;
- Nutrição;
- Burnout;
- Trabalho;
- Estudo;
- Lazer;
- Viagem.

Esses sistemas são interdependentes e formam uma das principais estruturas de
progressão de Polis.

---

# 2. Energia

Energia é o principal recurso utilizado para realizar ações.

Atividades como:

- trabalho;
- estudo;
- lazer;
- outras ações futuras;

consomem energia.

A quantidade exata de energia consumida por cada ação é um parâmetro de
balanceamento.

O valor anteriormente considerado de 25 por ação não deve ser tratado como
definitivo.

---

## 2.1 Regeneração de energia

A energia é regenerada naturalmente ao longo do tempo.

A regeneração possui uma base fixa e um componente influenciado por QoL.

Estrutura conceitual:

regeneração por hora =
regeneração_base + (QoL × multiplicador)

Exemplo conceitual:

5 + (QoL × X)

O valor de X será definido posteriormente.

A regeneração deve possuir um piso mínimo para impedir que QoL extremamente
baixa torne a regeneração impossível.

A regeneração utiliza principalmente a QoL Base, e não a QoL Atual, para
evitar um ciclo excessivamente instável no qual uma queda temporária de QoL
reduza a regeneração e cause novas quedas de QoL.

3. Qualidade de Vida (QoL)

Qualidade de Vida é uma das variáveis centrais de Polis.

Quase todos os sistemas podem influenciar QoL e, ao mesmo tempo, QoL pode
influenciar o funcionamento de diversos outros sistemas.

QoL deve representar não apenas conforto, mas também as condições gerais de
vida do jogador.

Entre os fatores que podem influenciar QoL estão:

moradia;
alimentação;
saúde;
trabalho;
burnout;
localização;
serviços;
transporte;
população;
instituições;
decisões políticas;
outros sistemas futuros.

O equilíbrio entre:

ganhar dinheiro
vs.
manter ou melhorar QoL

é uma das principais decisões estratégicas do jogo.

4. QoL Base e QoL Atual

Existem duas formas de QoL.

4.1 QoL Base

Representa a condição estrutural da vida do jogador.

Pode ser afetada por fatores como:

moradia;
localização;
condições sociais;
instituições;
serviços;
outras características relativamente persistentes.

QoL Base influencia sistemas como:

regeneração de energia;
eficiência de atividades;
saúde;
outras mecânicas futuras.
4.2 QoL Atual

Representa o estado momentâneo do jogador.

Ela pode sofrer efeitos temporários de:

alimentação;
buffs;
atividades;
condições;
outros efeitos temporários.

A QoL Atual não deve substituir a QoL Base.

5. QoL e eficiência

QoL pode atuar como multiplicador ou modificador de eficiência de diversas
atividades.

Conceitualmente:

QoL maior
→ maior eficiência

Isso pode afetar:

trabalho;
estudo;
produção;
outras atividades.

A relação exata entre QoL e eficiência deve permanecer parametrizada para
permitir balanceamento posterior.

O objetivo é criar uma relação de causa e efeito:

melhores condições de vida
→ maior capacidade de trabalhar/estudar
→ maior progressão

Ao mesmo tempo, o sistema não deve tornar QoL alta um multiplicador que
automaticamente domine todas as outras formas de progressão.

6. Trabalho

O jogador pode trabalhar consumindo energia.

Trabalho gera benefícios como:

salário;
desenvolvimento de skill;
produção ou contribuição para a empresa;
desenvolvimento de especialização;
outras recompensas específicas do cargo.

A quantidade de energia que o jogador decide gastar determina quantos trabalhos
pode realizar.

O proprietário da empresa pode estabelecer expectativas de trabalho e
recompensar ou punir funcionários através das ferramentas disponíveis no
sistema de Empresas.

7. Burnout

Trabalhar repetidamente em alta intensidade aumenta o risco de burnout.

Conceitualmente:

trabalho consecutivo
→ Burnout aumenta
→ risco de atingir o limite aumenta

Ao atingir o limite de burnout:

Burnout máximo
→ jogador fica temporariamente impedido de trabalhar

Durante o período de burnout:

QoL Base sofre uma redução temporária

Quando o burnout termina:

QoL Base retorna ao valor anterior

Burnout deve ser uma consequência crescente do excesso de trabalho, mas não
deve tornar o trabalho intenso automaticamente uma escolha ruim.

A intenção é criar um trade-off:

trabalhar mais
→ mais dinheiro
→ mais skill
→ mais produção
→ maior risco de burnout

Atividades de descanso ou determinadas atividades específicas podem reduzir
burnout.

A existência e magnitude do efeito de cada atividade serão definidas
posteriormente.

8. Estudo

Estudar consome energia.

O jogador pode decidir quanto de energia quer dedicar ao estudo.

Quanto mais energia for dedicada:

mais estudo
→ maior ganho diário de skill

Estudo não impede que o jogador trabalhe no mesmo período.

O jogador deve decidir como dividir sua energia entre:

trabalho;
estudo;
lazer;
outras atividades.
9. Escola e Universidade

As regras específicas de educação estão definidas no documento
03-escolas.md.

O sistema de Dia a Dia define apenas a relação com Energia e rotina:

estudar
→ consome energia
→ aumenta progressão acadêmica

A quantidade exata de energia por ação e os ganhos decorrentes serão
balanceados posteriormente.

10. Saúde

Saúde é uma variável independente, mas interligada a QoL.

A saúde pode ser influenciada por:

QoL;
Nutrição;
ações e condições do jogador;
infraestrutura de saúde;
outros eventos do mundo.

A estrutura conceitual é:

QoL
        ↓
Nutrição → Saúde
        ↑
Condições
        ↑
Infraestrutura médica

Saúde também influencia QoL.

Portanto:

Saúde ruim
→ QoL pior

QoL ruim
→ maior dificuldade para manter/recuperar Saúde

O sistema deve evitar que Saúde seja apenas uma cópia de QoL.

11. Saúde e infraestrutura médica

Hospitais são estruturas institucionais localizadas no mundo.

O hospital influencia principalmente a velocidade de recuperação de Saúde
dos jogadores do bairro.

A eficiência do hospital depende do trabalho dos médicos.

Conceitualmente:

Hospital
+
Médicos trabalhando
↓
eficiência médica
↓
maior velocidade de recuperação de Saúde

O trabalho do médico consome energia.

A contribuição do médico pode depender de:

skill relevante;
especialização;
quantidade de trabalho realizada.

Estrutura conceitual:

eficiência médica =
trabalho × f(skill) × f(especialização)

Os valores exatos serão definidos posteriormente.

Um hospital não deve garantir saúde perfeita nem impedir completamente doenças
ou outros problemas.

Sua principal função é melhorar a recuperação.

12. Saúde Crítica

Quando a Saúde atingir um nível muito baixo, o jogador entra em:

Saúde Crítica

A condição possui histerese para impedir alternância constante entre estados.

Conceitualmente:

Saúde ≤ limite_inferior
→ Saúde Crítica

Saúde > limite_superior
→ retorna ao estado normal

A condição representa um estado de saúde gravemente debilitada e não uma
diagnose médica específica.

13. Nutrição

Nutrição representa o estado alimentar do jogador.

A escala deve ser simples e não pretende simular nutrição real em profundidade.

A alimentação ocorre através do consumo de itens de comida do inventário.

Conceitualmente:

comida
→ consumo
→ aumenta Nutrição
→ pode fornecer buffs adicionais

Alguns alimentos podem oferecer efeitos além da recuperação de Nutrição.

Exemplos conceituais:

alimento
→ +Nutrição
→ +efeito temporário

A lista de alimentos, valores nutricionais e buffs pertence ao catálogo de
produtos/receitas do jogo.

14. Nutrição e Saúde

Nutrição influencia Saúde.

Conceitualmente:

Nutrição adequada
→ maior capacidade de manter/recuperar Saúde

Nutrição baixa
→ maior dificuldade de manter/recuperar Saúde

O sistema deve evitar modelar individualmente nutrientes reais como proteínas,
vitaminas, carboidratos etc., salvo futura decisão explícita de design.

15. Nutrição e QoL

Nutrição também pode influenciar QoL.

Quando a Nutrição estiver baixa, a QoL pode sofrer redução.

A alimentação adequada pode contribuir para manter ou melhorar QoL.

Alimentos específicos podem fornecer efeitos temporários adicionais.

16. Lazer

Lazer é uma categoria de atividades, e não uma ação única.

A categoria existe para permitir que os jogadores tenham alternativas a:

trabalho;
estudo.

Atividades de lazer podem:

recuperar ou aumentar QoL;
reduzir burnout;
oferecer buffs;
fornecer experiências;
criar interações sociais;
gerar outras recompensas futuras.

Cada atividade pode ter custo de energia e efeitos diferentes.

17. Empresas de lazer

Empresas de Serviços especializadas em Lazer podem oferecer atividades
diferentes aos jogadores.

O objetivo é permitir variedade de experiências sem criar sistemas excessivamente
complexos.

Exemplos:

Cinema

O proprietário pode cadastrar conteúdo textual e exibi-lo aos jogadores.

dono
→ cadastra roteiro/conteúdo
→ cria sessão
→ jogadores participam
→ recebem efeito de QoL
Rinque

Pode oferecer um minigame simples.

jogador
→ participa
→ obtém resultado
→ recebe efeito de QoL

Outros tipos de lazer podem existir.

O sistema de conteúdo criado por jogadores deve possuir limitações de segurança
e não permitir execução arbitrária de código.

O jogador pode criar conteúdo dentro das ferramentas fornecidas pelo jogo, mas
não criar novas mecânicas ou alterar diretamente o funcionamento do servidor.

18. Viagem

Viagem representa deslocamento físico entre bairros, cidades e outras regiões.

A viagem deve possuir tempo real de deslocamento.

Conceitualmente:

local A
↓
tempo de viagem
↓
local B
↓
atividade
↓
tempo de retorno
↓
local A

Viajar não aplica automaticamente um "dia sem trabalho".

O jogador simplesmente não pode realizar ações que dependam de estar fisicamente
na empresa enquanto estiver longe dela.

19. Motivos para viajar

O sistema de transporte deve criar razões reais para deslocamento.

Exemplos:

entretenimento;
preços melhores;
produtos que não existem no local de origem;
empregos;
serviços;
eventos;
atividades sociais;
oportunidades econômicas;
outros motivos futuros.

A intenção é que a geografia tenha impacto real no comportamento dos jogadores.

20. Progressão geográfica

O sistema de transporte deve apoiar uma progressão de alcance:

bairro
↓
cidade
↓
estado
↓
outras regiões

No início, o bairro deve concentrar grande parte das necessidades do jogador.

À medida que o jogador progride, deslocar-se para outras regiões se torna mais
viável e passa a abrir novas oportunidades.

Transporte, portanto, não deve funcionar simplesmente como teletransporte.

Tempo e custo devem possuir relevância econômica.

21. Modelo temporal

O jogo utiliza um sistema de ticks com intervalos de tempo fixos.

Nem todos os sistemas precisam utilizar o mesmo intervalo.

Possíveis categorias:

Hourly Tick
Daily Tick
Scheduled Event
On Action
On Access

O intervalo e a categoria de cada sistema devem ser definidos explicitamente.

22. Processamento atrasado de ticks

O servidor não deve executar continuamente todos os ticks de todos os
jogadores.

Quando um jogador acessar o jogo:

último processamento
↓
momento atual
↓
quantidade de ticks não processados
↓
executa ticks necessários
↓
atualiza estado do jogador/mundo

Exemplo:

último processamento: 10:00
acesso: 13:20
tick: 1 hora

→ processar 11:00
→ processar 12:00
→ processar 13:00

O sistema deve executar apenas os tipos de eventos relevantes para cada tick.

23. Eventos simultâneos

Quando múltiplos eventos possuem o mesmo timestamp, eles devem ser
processados em uma ordem determinística.

A ordem exata dos eventos deve ser definida pelo sistema quando houver
dependências.

Isso evita resultados diferentes causados apenas pela ordem de processamento.

Exemplo conceitual:

tick
→ calcular salário
→ processar dívida
→ processar aluguel
→ atualizar recursos

A ordem específica deve ser documentada quando necessária.

24. Feedback de fórmulas

Fórmulas compostas importantes devem retornar:

valor final
+
detalhamento dos componentes

Exemplo:

QoL = 0.82

Moradia       +0.10
Nutrição      +0.05
Saúde         -0.03
População     -0.10
Serviços      +0.02

Isso permite que a interface mostre ao jogador por que um valor foi obtido.

Esse princípio é uma regra arquitetural geral do projeto e não deve ser
limitado à interface de QoL.

25. Relação entre sistemas

O sistema de Dia a Dia deve permitir interações entre diversas partes do jogo.

Exemplos:

Moradia
→ QoL
→ Energia
→ trabalho/estudo
Trabalho
→ dinheiro
→ skill
→ produção
→ Burnout
→ QoL
Alimentação
→ Nutrição
→ Saúde
→ QoL
Hospital
→ recuperação de Saúde
→ Saúde
→ QoL
Transporte
→ tempo
→ acesso a atividades
→ oportunidades
→ localização

O objetivo não é que todos os sistemas afetem todos os outros diretamente.

Cada relação deve existir apenas quando houver uma justificativa de design.

26. Balanceamento

Os seguintes parâmetros devem permanecer configuráveis:

energia máxima;
custo de energia por ação;
regeneração base;
multiplicador de regeneração por QoL;
piso de regeneração;
influência de QoL na eficiência;
ganho de burnout;
limite de burnout;
duração do burnout;
redução temporária de QoL por burnout;
recuperação de burnout;
ganho de Saúde;
eficiência de hospitais;
efeito do trabalho dos médicos;
escala de Nutrição;
ganho de Nutrição por alimento;
efeitos dos alimentos;
duração das atividades de lazer;
custo de energia das atividades;
tempo de viagem;
custo de viagem;
intervalos de ticks.

Esses valores serão calibrados posteriormente através dos bots e testes de
jogabilidade.

27. Questões em aberto
Escala final de Energia.
Regeneração exata de Energia.
Escala de QoL.
Fórmula final de QoL → eficiência.
Fórmula completa de Saúde.
Recuperação natural de Saúde.
Fórmula do hospital.
Fórmula dos médicos.
Regras completas de Burnout.
Lista completa de atividades de lazer.
Sistema completo de Transporte.
Custos e tempos de viagem.
Classificação de cada sistema por tipo de tick.
Ordem completa de processamento dos eventos.
Catálogo final de alimentos e respectivos efeitos.
28. Fora do escopo

Este documento não define detalhadamente:

sistema de empresas;
sistema de escolas;
inventário;
geografia;
imóveis;
orçamento público;
política;
leis;
sociedades;
contratos;
sistema militar.

Esses sistemas possuem documentação própria.

Este documento define apenas as interações entre o sistema de Dia a Dia e esses
sistemas.


### Duas decisões que eu considero especialmente importantes

**Primeiro:** tirei definitivamente o antigo `-0.2 QoL por trabalho/estudo`. Agora o desgaste passa pelo **Burnout**, e o burnout é o que reduz temporariamente a QoL Base.

**Segundo:** incorporei a questão dos ticks de forma mais precisa. O que você descreveu não é simplesmente "rodar ticks quando o jogador entra"; é um modelo de **simulação atrasada por eventos**, e isso vai ser muito importante para a arquitetura.

E tem um ponto que eu propositalmente **não inventei**: a lista detalhada de alimentos. Como você encontrou essa informação no design antigo, quando criar o `catalogo-produtos-receitas.md`.
