10 — IMÓVEIS E ZONAS

Status: FINAL — BOT TEST

1. Objetivo

Este documento define o sistema de imóveis do Polis: aquisição de lotes, construção, propriedade, ocupação, aluguel, venda e utilização dos imóveis.

A estrutura territorial e o zoneamento-base pertencem ao 08 — Geografia e Imóveis. Este documento define o que acontece com o lote depois que ele entra no sistema imobiliário.

A unidade física básica continua sendo o Lote.

O termo Zona não será utilizado como sinônimo de lote ou imóvel. Quando necessário, “zona” refere-se ao conjunto de regras territoriais/zoneamento definido no documento 08.

2. Estado inicial do mundo

No início do servidor:

Todos os lotes começam vazios.
Todos os lotes disponíveis para desenvolvimento são inicialmente propriedade do governo.
Os lotes são disponibilizados aos jogadores e empresas através de leilões públicos.
Nenhum imóvel privado começa construído, salvo eventual conteúdo especial definido pelo cenário inicial.

O objetivo é que a expansão imobiliária seja consequência das decisões dos jogadores e das construtoras.

3. Propriedade de lotes

Podem possuir propriedades privadas:

Jogadores.
Empresas.

O governo mantém a propriedade de terrenos e imóveis destinados à utilização pública.

A propriedade do lote e a propriedade do imóvel construído devem ser tratadas como parte do mesmo ativo imobiliário após sua construção, mas o histórico da aquisição deve permanecer registrável.

4. Leilões de lotes

Todo lote vazio disponibilizado pelo governo é adquirido através de leilão público.

O leilão define quem terá o direito de adquirir o lote.

4.1 Funcionamento básico
O governo disponibiliza um lote.
É definido um lance mínimo.
O leilão recebe lances dos participantes elegíveis.
Os participantes podem aumentar o valor ofertado.
Ao final do período, o maior lance válido vence.
O vencedor paga o valor arrematado.
A propriedade do lote é transferida ao vencedor.

O governo recebe integralmente o valor do lote.

4.2 Duração

Cada leilão possui:

Data/hora de início.
Data/hora de encerramento.
Valor inicial.
Lance atual.
Participantes/lances registrados.
Vencedor.

A duração exata é um parâmetro do sistema e poderá ser ajustada durante o Bot Test.

4.3 Extensão por lance final

Para evitar que o resultado seja decidido apenas por quem conseguiu clicar no último segundo, o sistema utiliza extensão automática.

Caso um novo lance seja realizado próximo do encerramento, o leilão é estendido por um período adicional.

A extensão e a janela que a ativa são parâmetros configuráveis.

Exemplo conceitual:

Leilão terminaria às 20:00.
Um jogador dá um lance às 19:59:30.
O encerramento é estendido.
Novos jogadores podem continuar disputando.

O objetivo é premiar a disposição de pagar, e não a velocidade de sincronização do clique.

4.4 Pagamento

O vencedor deve possuir dinheiro suficiente para pagar o lance.

Caso o pagamento não possa ser concluído, o sistema invalida a arrematação conforme as regras de falha do leilão.

A implementação deve evitar que jogadores façam lances que evidentemente não possam pagar, sempre que isso puder ser validado sem prejudicar a experiência.

4.5 Elegibilidade

As restrições para participação em um leilão podem depender de:

Tipo de lote.
Tipo de imóvel permitido.
Estrela mínima exigida.
Leis vigentes.
Outras condições específicas do lote.

O zoneamento continua sendo a principal fonte de permissões territoriais.

5. Construção de imóveis privados

Após adquirir um lote, o proprietário pode utilizar uma Construtora para construir um imóvel compatível com o zoneamento.

O fluxo é:

Lote vazio → aquisição → escolha do imóvel → contratação da Construtora → construção → imóvel concluído

O proprietário não constrói diretamente.

A construção é realizada por uma empresa do tipo Construtora, seguindo as regras definidas no documento 02 — Empresas.

6. Imóveis residenciais

Os imóveis residenciais são classificados por densidade e padrão de qualidade.

Tipo	Capacidade	Construtora mínima	QoL base
Baixa densidade simples	1 unidade	1★	+0
Baixa densidade luxo	1 unidade	3★	+0,3
Alta densidade simples	~20 unidades	2★	+0,1
Alta densidade luxo	~20 unidades	4★	+0,4

Esses valores são parâmetros iniciais para Bot Test.

6.1 Unidade residencial

A capacidade de um imóvel representa a quantidade de unidades residenciais independentes existentes nele.

Uma unidade residencial pode ser ocupada por:

Um único jogador.
Dois jogadores casados.

Dois jogadores que não possuam vínculo matrimonial não podem simplesmente compartilhar a mesma unidade residencial.

Um prédio com aproximadamente 20 unidades, portanto, pode abrigar aproximadamente 20 jogadores individualmente, ou mais caso existam casais ocupando as mesmas unidades.

7. Efeito do imóvel na QoL

O imóvel é um dos componentes da QoL Base do jogador.

O bônus depende do tipo de imóvel.

Exemplo:

Baixa densidade simples → +0.
Alta densidade simples → +0,1.
Baixa densidade luxo → +0,3.
Alta densidade luxo → +0,4.

A QoL final do jogador continua sendo influenciada por outros sistemas, como roupas, alimentação, lazer, saúde e condições territoriais.

O imóvel não representa sozinho a qualidade de vida total.

8. Compra de imóveis

Imóveis construídos podem ser vendidos pelo proprietário.

A compra transfere:

Dinheiro → vendedor
Propriedade → comprador

O imóvel passa a pertencer ao novo proprietário.

O preço de venda é determinado pelo proprietário dentro das regras gerais do mercado imobiliário.

Não existe preço fixo obrigatório para imóveis privados.

9. Imóveis para aluguel

O proprietário pode disponibilizar uma unidade residencial para aluguel.

O fluxo básico é:

Proprietário → anúncio → jogador interessado → contrato → pagamento do aluguel → ocupação

O jogador que aluga o imóvel não se torna proprietário.

O aluguel é uma forma permanente de utilização da propriedade enquanto o contrato estiver válido.

O valor do aluguel é definido pelo proprietário, sujeito às leis municipais aplicáveis.

10. Contrato de aluguel

O contrato deve registrar pelo menos:

Proprietário.
Inquilino.
Imóvel/unidade.
Valor do aluguel.
Periodicidade.
Data de início.
Estado do contrato.
Eventuais regras legais aplicáveis.

O sistema deve permitir o acompanhamento do contrato sem depender de informações mantidas somente na interface.

11. Pagamento do aluguel

O aluguel é cobrado automaticamente de acordo com sua periodicidade.

O pagamento é enviado ao proprietário.

Caso o jogador não possua dinheiro suficiente, o pagamento é considerado inadimplente.

A inadimplência gera uma dívida utilizando o sistema geral de dívidas do jogo.

Não existe um sistema financeiro especial exclusivamente para aluguel.

A dívida registra:

Origem.
Credor.
Devedor.
Principal.
Saldo restante.
Regras de retenção.
Histórico de pagamentos.
12. Inadimplência

A inadimplência não deve simplesmente apagar o contrato imediatamente.

O sistema deve permitir:

período de atraso;
acúmulo da dívida;
pagamento posterior;
aplicação das consequências legais;
eventual encerramento da ocupação.

Os detalhes numéricos de tolerância e despejo são parâmetros ajustáveis.

A retenção de renda e demais mecanismos de cobrança reutilizam o sistema geral de dívidas.

13. Venda de imóvel alugado

Um imóvel que esteja alugado pode ser vendido pelo proprietário.

A venda não deve apagar automaticamente o contrato existente.

O contrato de aluguel continua vinculado à unidade e passa para o novo proprietário.

Assim:

Proprietário A → vende imóvel → Proprietário B

O inquilino continua ocupando a unidade e pagando aluguel, mas os pagamentos futuros passam a ser destinados ao novo proprietário.

Essa regra evita que um jogador seja despejado arbitrariamente apenas porque o proprietário decidiu vender a propriedade.

As condições de término antecipado do contrato, quando existirem, devem ser determinadas pelo contrato e pelas leis aplicáveis.

14. Ocupação

O jogador precisa possuir ou alugar uma unidade residencial para possuir uma moradia ativa.

A residência ativa é utilizada pelos sistemas que dependem do local de moradia.

A localização da residência também influencia sistemas como deslocamento para o trabalho e outras interações geográficas.

15. Propriedade ativa

Um jogador pode possuir múltiplos imóveis, mas apenas uma residência pode estar definida como residência ativa.

A residência ativa é aquela utilizada pelo sistema para:

moradia;
QoL;
deslocamento;
localização principal do jogador;
outros efeitos territoriais.

Isso segue o mesmo conceito geral de item/propriedade ativa utilizado em outros sistemas do jogo.

Possuir um imóvel não implica automaticamente morar nele.

16. Imóveis comerciais

Imóveis comerciais são utilizados por empresas que exigem localização comercial.

A estrela da empresa determina o nível de imóvel comercial que ela pode ocupar.

Isso se aplica especialmente ao Varejo.

A empresa precisa atender simultaneamente:

requisitos de localização;
requisitos de tipo de imóvel;
requisitos de estrela;
requisitos de atividade.

As regras específicas de funcionamento da empresa continuam pertencendo ao 02 — Empresas.

17. Imóveis industriais

Imóveis industriais são destinados a empresas que realizam atividades industriais.

A empresa precisa possuir uma localização compatível com seu tipo de atividade.

As receitas que podem ser produzidas são definidas pelo 22 — Receitas-Produção.

A capacidade produtiva da empresa continua sendo determinada principalmente por funcionários, skills, especialização e demais regras do sistema empresarial.

18. Imóveis institucionais

Imóveis institucionais pertencem principalmente ao governo quando destinados a serviços públicos.

Exemplos incluem:

escolas públicas;
hospitais públicos;
prédios administrativos;
outras estruturas públicas.

A lista exata de instituições públicas poderá crescer com o desenvolvimento do jogo.

19. Construção para o governo

O governo pode contratar Construtoras para produzir imóveis institucionais.

O fluxo é:

Governo → disponibiliza lote/projeto → Construtora realiza construção → imóvel concluído → governo compra imóvel pronto

O modelo foi criado deliberadamente como uma oportunidade de entrada para construtoras menores.

Características dos contratos públicos

O contrato possui:

imóvel definido;
requisitos de construção;
valor de venda previamente definido;
condições de conclusão.

A Construtora recebe um lucro previsível ao concluir o projeto.

Isso reduz:

risco de mercado;
necessidade de encontrar comprador privado;
risco de estoque imobiliário parado.

Em contrapartida, contratos públicos possuem margem limitada.

Construtoras mais eficientes tendem naturalmente a preferir o mercado privado quando o potencial de lucro compensar o risco adicional.

20. Construção e compra pelo governo

O governo não precisa comprar um imóvel público antecipadamente.

O lote pode ser destinado à construção, e a Construtora realiza o projeto.

Após a conclusão:

Construtora → imóvel concluído → governo

O governo paga o preço definido no contrato.

Após a aquisição, o imóvel passa a ser propriedade pública.

21. Mudança de finalidade

Um imóvel pode mudar de finalidade, desde que o governo aprove a alteração.

Exemplos:

Comercial → Residencial.
Residencial → Comercial.
Industrial → outro uso permitido.
Outras mudanças previstas pela legislação.

A mudança não é realizada livremente pelo proprietário.

O pedido deve ser analisado de acordo com:

zoneamento vigente;
leis municipais;
possíveis restrições do lote;
projetos ou regras especiais.

A alteração pode modificar quais atividades podem utilizar aquele imóvel.

22. Zoneamento e imóveis

O zoneamento determina quais tipos de utilização são permitidos.

O imóvel deve ser compatível com o zoneamento de seu lote.

As regras de zoneamento padrão são definidas no 08 — Geografia e Imóveis.

Leis e projetos públicos podem alterar essas permissões posteriormente.

O sistema imobiliário não deve duplicar essas regras.

Ele deve consultar o sistema de zoneamento para determinar se uma operação é válida.

23. Demolição e reconstrução

A demolição não faz parte do sistema inicial de Bot Test.

Da mesma forma, reconstrução direta e reforma profunda não fazem parte da primeira versão.

O imóvel existente permanece com sua configuração enquanto não houver uma mecânica específica para alteração estrutural.

Esses sistemas podem ser adicionados futuramente caso exista necessidade econômica ou gameplay.

24. Manutenção e depreciação

Não haverá manutenção periódica nem depreciação automática dos imóveis no Bot Test.

Um imóvel não perde qualidade simplesmente com o passar do tempo.

A introdução dessas mecânicas deverá ocorrer apenas em revisão futura do sistema.

25. Valor do imóvel

O valor de um imóvel pode ser influenciado por:

tipo;
qualidade;
localização;
características do bairro;
características do lote;
mercado;
oferta e demanda;
infraestrutura;
leis;
outros efeitos sistêmicos.

Não haverá uma fórmula única obrigatória de preço de mercado no Bot Test.

O preço de venda privado é determinado pelo proprietário, enquanto o valor econômico do imóvel pode ser utilizado por outros sistemas para cálculos e referências.

26. Impostos sobre imóveis

Impostos imobiliários pertencem ao sistema de Leis Paramétricas.

O documento 11 pode definir parâmetros como:

IPTU;
limites de posse;
controle de aluguel;
regras adicionais de propriedade.

Este documento apenas fornece os ativos e operações necessários para que essas leis funcionem.

27. Limite de propriedades

Não existe um limite universal permanente de propriedades no sistema base.

Um jogador ou empresa pode possuir múltiplos imóveis enquanto as regras vigentes permitirem.

Leis municipais poderão posteriormente estabelecer limites de posse.

28. Relação com a Construtora

A Construtora é responsável pela transformação do lote em imóvel.

O fluxo privado padrão é:

Governo → leilão → proprietário → Construtora → imóvel concluído → venda/aluguel/uso

A Construtora não recebe automaticamente a propriedade do imóvel que construiu.

Ela é prestadora da construção, salvo quando for também proprietária do lote.

29. Relação com o sistema de empresas

O documento 02 define:

tipos de empresas;
funcionários;
produção;
estrelas;
especializações;
operação.

O documento 10 define:

onde a empresa pode operar;
qual imóvel ela ocupa;
aquisição e ocupação do imóvel;
relação entre estrela e imóvel comercial;
propriedade imobiliária da empresa.
30. Relação com QoL

O imóvel fornece parte da QoL Base do jogador.

Outros sistemas continuam contribuindo para a QoL, como:

alimentação;
roupas;
transporte;
lazer;
saúde;
política;
condições territoriais.

O objetivo é que o imóvel seja uma das principais fontes de diferenciação social/econômica sem transformar o bairro em uma classificação fixa de riqueza.

31. Princípios de implementação
1. Lote e imóvel são conceitos diferentes

Lote = terreno físico.

Imóvel = estrutura/propriedade construída naquele terreno.

2. Zoneamento não é imóvel

Zoneamento determina o que pode existir naquele território.

O imóvel representa o que efetivamente foi construído.

3. Governo inicia como proprietário dos lotes

Os lotes vazios são disponibilizados por leilão.

4. Construção é realizada por Construtora

O proprietário do lote contrata uma empresa adequada.

5. Propriedade pode pertencer a jogador ou empresa

Instituições públicas permanecem sob propriedade governamental.

6. Aluguel gera relação entre proprietário e inquilino

A inadimplência utiliza o sistema genérico de dívidas.

7. Venda não encerra automaticamente aluguel

O contrato acompanha a unidade e passa ao novo proprietário.

8. Uma unidade residencial pertence a um único jogador

Casamento permite compartilhamento por dois jogadores.

9. Imóvel não possui manutenção/depreciação no Bot Test
10. Regras políticas devem permanecer externas ao modelo imobiliário

Leis alteram parâmetros e permissões sem exigir reconstrução do sistema.

32. Fora do escopo imediato

Não fazem parte do Bot Test:

manutenção;
depreciação;
reforma detalhada;
demolição;
mercado hipotecário;
financiamento imobiliário;
construção simultânea de múltiplos imóveis pela mesma Construtora;
especulação imobiliária avançada;
seguros imobiliários;
sistema detalhado de condomínio;
tributação imobiliária própria além do suporte necessário às leis;
sistema completo de estradas e transporte.

Esses sistemas poderão utilizar os dados imobiliários posteriormente.

33. Dependências

08 — Geografia e Imóveis
Define lotes, localização, capacidade territorial e zoneamento.

02 — Empresas
Define Construtoras, Varejo, Serviços e demais empresas.

09 — Orçamento Público
Define os recursos utilizados pelo governo em contratos e infraestrutura.

11 — Leis Paramétricas
Define impostos, controle de aluguel, limites de posse e alterações de zoneamento.

04 — Dia a Dia
Utiliza a residência para efeitos de QoL e deslocamento.

05 — Inventário
Pode utilizar propriedade ativa e outros bens associados ao jogador.

34. Fluxos principais
Imóvel residencial privado

Lote vazio
→ Leilão
→ Jogador arremata lote
→ Contrata Construtora
→ Construtora constrói
→ Imóvel concluído
→ Jogador mora / vende / aluga

Imóvel comercial privado

Lote vazio
→ Leilão
→ Empresa ou jogador adquire
→ Construtora constrói
→ Empresa ocupa o imóvel
→ Operação empresarial

Imóvel público

Governo disponibiliza lote/projeto
→ Contrato com Construtora
→ Construção
→ Governo compra imóvel pronto
→ Imóvel público entra em operação

35. Status final

FINAL — BOT TEST
