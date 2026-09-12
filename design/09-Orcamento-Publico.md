09 — ORÇAMENTO PÚBLICO

Status: FINAL — BOT TEST

1. Objetivo

O sistema de Orçamento Público representa o dinheiro disponível aos governos e transforma decisões políticas em consequências econômicas reais.

O orçamento deve funcionar com dinheiro existente dentro da economia do jogo, evitando ao máximo a criação de dinheiro novo.

O sistema deve permitir:

arrecadação de impostos;
redistribuição entre níveis de governo;
definição de prioridades;
financiamento de serviços públicos;
financiamento de projetos;
contratação de Construtoras;
pagamento de funcionários públicos;
financiamento militar;
concessão de subsídios;
acumulação de reservas;
emissão de dívida pública;
ocorrência de crises fiscais.

O orçamento é uma das principais pontes entre Política, Economia, Empresas, QoL e Infraestrutura.

2. Hierarquia orçamentária

Existem três níveis de governo:

Federal → Estados → Municípios

Cada nível possui seu próprio orçamento.

Entretanto, a origem principal da arrecadação tributária é centralizada.

O fluxo padrão é:

Jogadores/Empresas → impostos → caixa federal → Estados → Municípios

A redistribuição é determinada politicamente.

3. Caixa federal

O governo federal recebe o recolhimento dos impostos definidos como federais.

O Presidente administra esse caixa.

Parte dos recursos pode permanecer no orçamento federal para financiar despesas nacionais e parte pode ser redistribuída aos Estados.

A redistribuição não deve ser automática por uma fórmula fixa no Bot Test.

O Presidente decide quanto cada Estado recebe, dentro das regras e limitações vigentes.

Isso permite que decisões como investimento regional, favoritismo político, combate à desigualdade e concentração de recursos tenham consequências reais.

4. Caixa estadual

Cada Estado recebe recursos do governo federal.

O Governador administra o orçamento estadual.

Após receber os recursos, o Governador decide quanto será:

mantido no orçamento estadual;
repassado a cada Município;
utilizado diretamente pelo Estado.

O repasse aos Municípios é uma decisão política.

Não existe obrigação de distribuir o dinheiro igualmente entre eles.

5. Caixa municipal

Cada Município recebe recursos provenientes do Estado.

O Prefeito administra o orçamento municipal.

O Prefeito decide como distribuir os recursos recebidos entre as diferentes áreas de governo.

Exemplos:

Educação;
Saúde;
Infraestrutura;
Segurança/Defesa local, quando aplicável;
Administração;
programas sociais;
outros projetos públicos.

Isso transforma o orçamento municipal em uma ferramenta de governo real, e não apenas em uma estatística.

6. Impostos e arrecadação

Os impostos são definidos pelo sistema de leis.

O orçamento apenas registra e movimenta os valores arrecadados.

Exemplos de bases tributárias:

Tipo	Base
Imposto sobre vendas	Transações do Mercado e transações empresariais
Imposto de renda	Salários pagos
Imposto sobre lucro	Lucro das empresas
Outros impostos	Conforme leis futuras

As alíquotas pertencem ao sistema de Leis Paramétricas.

O dinheiro arrecadado entra no caixa federal quando o imposto possuir escopo federal.

O sistema não deve criar dinheiro novo para realizar a arrecadação.

7. Princípio de circulação monetária

O objetivo econômico é manter o dinheiro circulando dentro da economia.

Quando possível:

Jogador/Empresa paga imposto → Governo recebe → Governo gasta → Dinheiro retorna à economia

Da mesma forma:

Jogador compra título público → Governo recebe dinheiro existente → Governo gasta → Dinheiro volta à economia

O sistema deve evitar utilizar criação monetária como solução padrão para déficits.

8. Período orçamentário

O ciclo orçamentário padrão será de 30 dias.

Ao longo de cada período:

receitas são arrecadadas;
despesas são realizadas;
projetos são executados;
compromissos são criados;
dívidas são pagas;
o governo pode acumular superávit ou déficit.

Ao final do período é produzido um balanço público.

O saldo restante permanece para o próximo período.

9. Saldo público

Cada governo possui um saldo financeiro.

A fórmula conceitual é:

Saldo final = saldo inicial + receitas − despesas efetivamente pagas

O saldo não é zerado ao final do período.

Um governo pode acumular dinheiro por vários períodos para financiar projetos futuros.

10. Orçamento comprometido

Além do saldo atual, cada governo possui um valor de orçamento comprometido.

Orçamento comprometido representa dinheiro que já foi destinado a despesas futuras.

Exemplo:

Saldo atual: R$ 1.000.000
Comprometido com projetos: R$ 600.000
Saldo disponível: R$ 400.000

O governo não pode considerar os R$ 600.000 comprometidos como dinheiro livre para novas decisões.

11. Comprometimentos superiores ao saldo

Um governo não pode assumir novos compromissos que não consiga financiar através de seus mecanismos permitidos.

Caso obrigações existentes ultrapassem o saldo disponível, o governo entra em pressão fiscal.

O sistema deverá priorizar as obrigações já assumidas.

Novas despesas discricionárias podem ser bloqueadas ou reduzidas.

O governo poderá utilizar:

receitas futuras;
reservas existentes;
emissão de dívida pública, caso ainda esteja dentro dos limites;
redução/cancelamento de despesas que ainda não foram executadas, quando juridicamente possível.

O sistema não deve simplesmente permitir que o valor negativo cresça indefinidamente.

12. Categorias de despesas

As principais categorias de despesa pública são:

Educação

Inclui:

escolas públicas;
universidades públicas;
salários;
materiais;
programas educacionais;
bolsas;
infraestrutura educacional.
Saúde

Inclui:

hospitais públicos;
médicos;
funcionários;
materiais hospitalares;
tratamentos subsidiados;
infraestrutura de saúde.
Infraestrutura

Inclui:

construção de prédios públicos;
projetos de infraestrutura;
contratos com Construtoras;
expansão territorial;
outras obras públicas.
Administração

Inclui:

salários de funcionários públicos;
funcionamento da administração;
estruturas administrativas;
outros custos governamentais.
Militar

Inclui as despesas previstas pelo sistema militar, como:

pessoal;
equipamentos;
manutenção;
operações;
infraestrutura;
demais custos definidos pelo 19 — Militar.

O orçamento deve permitir que o sistema militar solicite e consuma recursos sem precisar criar um mecanismo financeiro separado.

Programas sociais

Incluem políticas de apoio financiadas pelo governo.

Exemplos:

bolsas;
subsídios;
programas de saúde;
programas educacionais;
outros programas definidos por lei.
13. Despesas discricionárias e obrigatórias

As despesas devem ser classificadas conforme sua natureza.

Despesas obrigatórias

São despesas que o governo precisa pagar enquanto determinada obrigação existir.

Exemplos:

salários de servidores;
parcelas de dívida;
contratos já firmados;
determinadas despesas definidas constitucionalmente.
Despesas discricionárias

São aquelas que podem ser modificadas pelo governo.

Exemplos:

novos projetos;
novos subsídios;
investimentos adicionais;
campanhas temporárias;
expansão voluntária de determinadas áreas.

Essa distinção é necessária para que uma crise fiscal tenha consequências concretas.

14. Projetos públicos

Projetos são gastos planejados com objetivo específico.

Cada projeto registra:

governo responsável;
objetivo;
território;
custo;
duração;
valor já gasto;
valor restante;
orçamento comprometido;
estado de execução.

Exemplos:

construir escola;
construir hospital;
construir prédio público;
realizar obra de infraestrutura;
financiar campanha temporária.
15. Contratos com Construtoras

Projetos que dependam de construção podem utilizar uma Construtora.

Fluxo:

Governo → projeto → orçamento reservado → contrato → construção → pagamento → conclusão

O valor do contrato deve ser conhecido antes da execução.

Isso permite que o governo saiba exatamente quanto de seu orçamento ficará comprometido.

O sistema de construção pertence ao 10 — Imóveis e Zonas e ao 02 — Empresas.

16. Despesas recorrentes

Despesas recorrentes são cobradas enquanto determinado serviço ou programa estiver ativo.

Exemplos:

salários;
funcionamento de escolas;
funcionamento de hospitais;
programas permanentes;
subsídios permanentes;
despesas militares recorrentes.

Uma decisão política que cria uma nova despesa recorrente deve afetar os períodos seguintes.

Isso impede que um político analise apenas o custo inicial de uma decisão.

17. Superávit

Quando:

Receita > Despesas

o governo possui superávit.

O valor excedente permanece no caixa.

O governo poderá posteriormente:

investir;
criar novos projetos;
aumentar serviços;
reduzir impostos;
subsidiar setores;
acumular reservas;
pagar dívida pública.
18. Déficit

Quando:

Despesas > Receitas

o governo possui déficit.

O déficit deve ser financiado por recursos existentes ou por mecanismos de dívida autorizados.

O governo não pode simplesmente criar dinheiro para cobrir o déficit.

19. Dívida pública

O governo pode financiar parte de seus déficits através da emissão de títulos da dívida pública.

Esses títulos podem ser comprados por jogadores e demais agentes financeiros autorizados pelo sistema.

Fluxo:

Jogador → compra título público → Governo recebe dinheiro

Posteriormente:

Governo → paga principal + juros → comprador do título

A dívida pública, portanto, representa uma transferência de recursos existentes do setor privado para o governo naquele momento, com obrigação futura de pagamento.

20. Títulos públicos

Cada emissão de dívida registra:

governo emissor;
comprador;
valor principal;
taxa de juros;
data de vencimento;
valor total devido;
situação do título.

Os títulos são ativos para o comprador e passivos para o governo.

O dinheiro recebido no momento da emissão entra no caixa do governo.

21. Pagamento da dívida

No vencimento, o governo deve pagar o valor devido.

O pagamento reduz o caixa público e transfere dinheiro ao detentor do título.

Caso o título tenha pagamentos periódicos de juros, esses pagamentos também representam despesas públicas.

A estrutura exata de prazo e juros poderá ser parametrizada para o Bot Test.

22. Inadimplência da dívida pública

O governo não pode simplesmente ignorar títulos vencidos.

Caso não possua dinheiro suficiente:

pagamentos podem entrar em atraso;
novas emissões podem sofrer restrições;
o custo de financiamento pode aumentar;
determinadas despesas discricionárias podem ser bloqueadas;
a confiança no governo pode cair;
a situação pode gerar crise política;
mecanismos constitucionais de responsabilização podem ser acionados.

O sistema não deve criar dinheiro automaticamente para impedir a inadimplência.

23. Limite de endividamento

O governo possui um limite de endividamento.

O limite deve impedir que o governo simplesmente acumule dívida indefinidamente.

O teto pode ser definido em relação à capacidade fiscal do governo, utilizando parâmetros como:

receita;
dívida existente;
compromissos futuros;
capacidade de pagamento;
regras legais vigentes.

O limite exato é parametrizável.

24. Bloqueio fiscal

Quando um governo se aproxima ou ultrapassa determinados níveis de endividamento, novas despesas podem sofrer restrições.

Exemplo conceitual:

Situação saudável

Novos projetos permitidos.

Endividamento elevado

Novos projetos passam a exigir maior justificativa ou podem sofrer limitações.

Limite atingido

Novos projetos discricionários ficam bloqueados.

Situação crítica

O governo precisa reduzir despesas, aumentar receitas ou refinanciar obrigações.

Insolvência

O governo não consegue cumprir suas obrigações normalmente e entra em crise fiscal.

Os limites exatos são parâmetros de balanceamento.

25. Superação do limite e consequências políticas

Uma crise fiscal grave pode gerar consequências políticas.

Dependendo das regras do sistema político, podem ocorrer:

perda de apoio político;
queda de aprovação;
bloqueios legislativos;
investigações;
processos;
impeachment;
novas eleições;
outras medidas constitucionais.

O orçamento não realiza o impeachment diretamente.

Ele fornece os indicadores fiscais que podem alimentar os mecanismos definidos pelo sistema político.

26. Déficit e QoL

O déficit não reduz QoL automaticamente.

As consequências devem surgir por meio de seus efeitos econômicos.

Exemplo:

Déficit elevado → dívida → juros → menos dinheiro disponível → cortes de serviços/investimentos → pior infraestrutura/serviços → pior QoL

Isso torna o efeito do déficit sistêmico em vez de uma penalidade arbitrária.

O documento de política já previa que desequilíbrios fiscais prolongados deveriam gerar pressão sobre a QoL e a satisfação da população.

27. Distribuição política do orçamento

A distribuição dos recursos é uma das principais funções dos cargos executivos.

Presidente

Decide quanto dos recursos federais será destinado a cada Estado e quanto permanecerá no orçamento federal.

Governador

Decide quanto dos recursos estaduais será destinado a cada Município e quanto permanecerá no orçamento estadual.

Prefeito

Decide como o orçamento municipal será distribuído entre suas áreas e projetos.

Essas decisões devem ser registradas e publicamente visíveis.

28. Investimento regional

Não haverá uma fórmula automática de equalização entre Estados ou Municípios.

Um território com baixo investimento poderá melhorar através de decisão política de investimento.

Isso significa que o sistema não força igualdade econômica.

Ele fornece aos governantes as ferramentas necessárias para promovê-la caso desejem.

Da mesma forma, governos podem deliberadamente concentrar investimentos em determinadas regiões.

29. Subsídios

Subsídios são despesas públicas destinadas a reduzir o custo de determinada atividade, produto ou setor.

Exemplo:

Subsídio agrícola

→ governo assume parte do custo
→ preço efetivo do produto diminui
→ consumidor ou empresa paga menos
→ governo registra uma despesa.

O sistema de subsídios é controlado por leis ou programas públicos específicos.

30. Transferências governamentais

A transferência entre níveis de governo segue a hierarquia:

Federal → Estados → Municípios

Essas transferências são decididas pelo governante responsável.

Não haverá, no sistema base, uma redistribuição automática obrigatória entre Estados.

O principal instrumento de correção de regiões com baixo investimento será a própria decisão política de aumentar o repasse ou investimento naquela região.

31. Orçamento comprometido e novas decisões

Antes de aprovar uma nova despesa, o governo deve considerar:

Saldo disponível + receitas projetadas permitidas − compromissos existentes

Uma proposta que ultrapasse a capacidade financeira disponível deve ser:

rejeitada;
reduzida;
adiada;
financiada por dívida, caso permitido;
ou alterada para compensar a despesa.

Isso impede que o governo aprove projetos infinitos simplesmente porque ainda possui saldo contábil positivo.

32. Reserva pública

Um governo pode manter parte de seu caixa como reserva.

A reserva não é uma despesa.

É dinheiro disponível para:

emergências;
projetos futuros;
crises;
pagamento de dívidas;
estabilidade fiscal.

A decisão de manter uma reserva ou gastar imediatamente é política.

33. Transparência

Os dados fiscais são públicos.

Qualquer jogador pode consultar o orçamento do governo através da instituição administrativa correspondente, como a Prefeitura no caso municipal.

Devem estar disponíveis:

Receitas
impostos;
transferências recebidas;
outras receitas.
Despesas
educação;
saúde;
infraestrutura;
militar;
administração;
programas sociais;
subsídios;
projetos;
pagamentos de dívida.
Situação financeira
saldo;
orçamento comprometido;
saldo disponível;
receita do período;
despesa do período;
superávit/déficit;
dívida;
compromissos futuros.
34. Log financeiro

Toda movimentação financeira pública deve gerar um registro no log geral do servidor.

O registro deve conter, conforme aplicável:

data/hora;
governo;
origem;
destino;
valor;
categoria;
operação;
referência da lei/projeto/contrato;
saldo antes;
saldo depois.

O log deve ser auditável e não depender apenas do estado atual da conta.

Isso também permite análise econômica e debugging.

35. Relação com as Leis Paramétricas

O orçamento executa os efeitos financeiros das leis.

Exemplo:

Lei: imposto sobre vendas = 5%

→ transação ocorre
→ imposto é recolhido
→ valor entra no caixa federal.

Exemplo:

Lei: subsídio agrícola = 10%

→ produto elegível recebe redução
→ governo financia a diferença
→ despesa é registrada.

As leis não devem conter uma cópia da lógica de orçamento.

O orçamento é responsável pela movimentação financeira resultante.

36. Relação com campanhas e projetos temporários

Projetos temporários e campanhas públicas possuem custo definido e retiram recursos do orçamento correspondente.

O sistema deve reservar o valor necessário enquanto a campanha estiver ativa.

Campanhas devem respeitar:

orçamento disponível;
compromissos existentes;
limites legais;
limite de endividamento.

O conceito de campanhas temporárias já previsto no design utiliza orçamento do governo como fonte de financiamento.

37. Bot Test — Governos

O Bot Test deve incluir agentes capazes de iniciar o teste já ocupando cargos governamentais.

Devem existir, no mínimo:

Bot Presidente;
Bot Governador;
Bot Prefeito.

O bot não começa necessariamente como um jogador comum que precisa conquistar o cargo.

Ele pode começar diretamente na posição que está sendo testada.

38. Estados iniciais dos bots governamentais

Os bots governamentais devem receber cenários econômicos diferentes.

Exemplos:

Presidente A — Conservador fiscal
caixa alto;
dívida baixa;
arrecadação moderada;
poucos compromissos.
Presidente B — Investidor
caixa moderado;
baixa dívida;
grandes oportunidades de investimento.
Presidente C — Endividado
caixa baixo;
dívida elevada;
pagamentos próximos;
orçamento comprometido alto.
Presidente D — Crise
caixa muito baixo;
alta dívida;
baixa arrecadação;
forte pressão política.

Os parâmetros exatos dos cenários serão definidos em 21 — Bots.

39. Objetivo dos testes com bots

O objetivo não é descobrir apenas qual bot acumula mais dinheiro.

O sistema deve permitir observar decisões como:

poupar ou investir;
aumentar ou reduzir impostos;
financiar infraestrutura;
subsidiar setores;
assumir dívida;
pagar dívida antecipadamente;
concentrar investimentos;
redistribuir recursos;
cortar despesas;
manter reservas;
priorizar educação;
priorizar saúde;
priorizar militar;
aceitar risco fiscal.

O sistema deve ser avaliado pela qualidade dos trade-offs que produz.

40. Exemplo de fluxo econômico completo

Um fluxo possível:

Empresa vende produto

→ imposto é recolhido
→ dinheiro entra no caixa federal

Presidente decide repassar R$ 500.000 ao Estado A

→ caixa federal −R$ 500.000
→ caixa estadual +R$ 500.000

Governador decide repassar R$ 100.000 ao Município B

→ caixa estadual −R$ 100.000
→ caixa municipal +R$ 100.000

Prefeito decide gastar R$ 60.000 em hospital

→ orçamento comprometido
→ projeto iniciado

Prefeito contrata Construtora

→ obra executada
→ governo paga
→ dinheiro retorna à economia através da empresa e de seus trabalhadores.

O sistema completo transforma arrecadação em atividade econômica real.

41. Princípios de implementação
1. Dinheiro público é dinheiro da economia

O governo deve movimentar dinheiro existente sempre que possível.

2. Arrecadação é centralizada

Os impostos entram no caixa federal conforme sua legislação.

3. Redistribuição é política

Presidente redistribui aos Estados.

Governadores redistribuem aos Municípios.

Prefeitos distribuem o orçamento municipal.

4. Saldo não zera

Superávit permanece disponível.

5. Compromissos importam

Dinheiro já comprometido não deve ser tratado como dinheiro livre.

6. Dívida possui credor real

Jogadores podem comprar títulos públicos.

7. Dívida possui custo real

O governo precisa pagar principal e juros.

8. Não existe dívida infinita

Limites fiscais impedem acumulação ilimitada.

9. Crise fiscal possui consequências reais

Não deve existir simplesmente “saldo negativo infinito”.

10. Tudo é público e auditável

Os jogadores podem acompanhar o dinheiro dos governos.

42. Fora do escopo imediato

Não fazem parte do Bot Test inicial:

política monetária;
criação/destruição complexa de moeda;
banco central independente;
mercado secundário avançado de títulos públicos;
títulos públicos negociáveis em bolsa;
rating detalhado da dívida;
derivativos;
sistema tributário extremamente granular;
contabilidade pública de nível real;
financiamento externo/internacional.

Esses sistemas podem ser adicionados posteriormente sem alterar o princípio fundamental do orçamento.

43. Dependências

02 — Empresas
Fornece empresas, funcionários, produção e Construtoras.

04 — Dia a Dia
Recebe efeitos sobre QoL e condições de vida.

08 — Geografia
Define território, cidades, estados e infraestrutura espacial.

10 — Imóveis e Zonas
Define construção de imóveis e contratos com Construtoras.

11 — Leis Paramétricas
Define impostos, subsídios, limites fiscais e outras regras parametrizáveis.

06 — Política
Define cargos, poder executivo e mecanismos de responsabilização.

07 — Leis
Define processo legislativo.

19 — Militar
Define as necessidades e despesas militares.

21 — Bots
Define os agentes e cenários de teste fiscal.

17 — Transparência de Mercado
Pode utilizar os dados públicos de orçamento.

15 — Jornal
Pode divulgar grandes decisões e eventos fiscais.

44. Status final

FINAL — BOT TEST
