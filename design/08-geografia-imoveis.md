08 — GEOGRAFIA E IMÓVEIS

Status: FINAL — BOT TEST

1. Objetivo

O sistema de geografia define a estrutura espacial do país e serve como base para imóveis, empresas, transporte, recursos naturais, zoneamento, instituições e futuras mecânicas políticas e econômicas.

A estrutura territorial segue:

Estado → Cidade → Bairro → Lote

A geografia deve ser suficientemente estruturada para funcionar no jogo atual e, futuramente, permitir a geração procedural de mapas visuais.

2. Estado

O Estado é a maior divisão territorial utilizada pelo jogo.

Cada Estado possui:

Uma posição geográfica dentro do país.
Uma capital estadual.
Uma ou mais cidades.
Administração própria.
Regras e características políticas definidas pelo sistema político.

O Estado não deve possuir uma mecânica própria de distância em relação à capital nacional. Distâncias relevantes devem ser calculadas diretamente através das coordenadas geográficas.

3. Cidade

A Cidade é a principal unidade urbana e administrativa intermediária entre Estado e Bairro.

Cada cidade possui:

Coordenadas X/Y no mapa.
Um conjunto de bairros.
Administração municipal.
Infraestrutura.
Estrutura econômica e territorial própria.
3.1 Bairros por cidade

A cidade possuirá inicialmente 25 bairros.

Os bairros não serão simplesmente numerados e posicionados aleatoriamente. Sua posição espacial deverá formar uma estrutura coerente de cidade, utilizando uma distribuição concentrada ao redor de uma região central.

A organização deve permitir posteriormente representar visualmente:

centro urbano;
regiões intermediárias;
periferia;
áreas de expansão;
regiões rurais ou especiais.

A distribuição exata dos bairros poderá utilizar uma geração procedural baseada em coordenadas, mantendo uma tendência de concentração semelhante a uma distribuição gaussiana/espiral, em vez de uma grade perfeitamente uniforme.

O objetivo é que a estrutura espacial pareça uma cidade real e possa futuramente ser convertida diretamente em um mapa visual procedural.

4. Bairro

O Bairro é a principal unidade espacial para regras locais.

Cada bairro possui:

Coordenadas X/Y.
Tipo predominante de zoneamento.
Conjunto de lotes.
Capacidade residencial.
Capacidade comercial.
Capacidade industrial.
Capacidade institucional.
Capacidade especial, quando aplicável.
Características espaciais e de infraestrutura.

A classificação econômica de um bairro como rico, médio ou pobre não será uma característica permanente do bairro.

A condição econômica do jogador dependerá principalmente de seus imóveis, recursos, emprego, renda, QoL e das condições sistêmicas daquele momento.

5. Lote

O Lote é a menor unidade territorial física do sistema.

É o espaço onde uma residência, empresa, instituição ou outra estrutura pode existir.

Cada lote pertence a um único bairro e possui:

Coordenadas espaciais.
Categoria de uso.
Estado de ocupação.
Eventuais recursos naturais.
Regras de zoneamento aplicáveis.

As categorias principais de lotes são:

Residencial
Comercial
Industrial
Institucional
Especial
Rural
6. Capacidade dos bairros

A quantidade de lotes disponíveis depende do tipo de uso.

Valores base:

Tipo de lote	Capacidade
Residencial	50
Comercial	30
Industrial	20
Institucional	5
Especial	10
Rural	Definida pela estrutura territorial

As capacidades são parâmetros do sistema e poderão ser utilizadas pelos testes com bots.

7. Lotes Residenciais

Lotes residenciais permitem a construção/ocupação de imóveis destinados à moradia dos jogadores.

O imóvel ocupado pelo jogador possui seus próprios atributos e efeitos, incluindo seu impacto sobre QoL.

A qualidade do bairro não será usada como substituto da qualidade do imóvel.

8. Lotes Comerciais

Lotes comerciais permitem a instalação de empresas e atividades comerciais compatíveis com o zoneamento do local.

Empresas de varejo e serviços utilizarão esses lotes quando sua atividade exigir localização comercial.

As permissões específicas de cada empresa continuam sendo definidas pelo sistema de empresas e pelo catálogo de produtos/receitas.

9. Lotes Industriais

Lotes industriais permitem atividades de transformação, fabricação e outras atividades produtivas compatíveis com o zoneamento industrial.

Empresas industriais devem utilizar esses lotes para suas operações.

O tipo de produto que uma empresa pode produzir não é determinado somente pelo lote, mas pelas regras de produção definidas em:

22 — Receitas-Produção

10. Lotes Institucionais

Lotes institucionais são destinados a estruturas como:

escolas;
hospitais;
outras instituições públicas ou privadas;
estruturas institucionais futuras.

A existência e quantidade dessas instituições depende das regras específicas de cada sistema.

11. Lotes Especiais

Lotes especiais formam uma categoria própria.

Um bairro especial possui 10 lotes especiais.

Esses lotes são destinados a estruturas que não se encaixam adequadamente nas categorias Residencial, Comercial, Industrial ou Institucional.

A utilização específica desses lotes poderá ser expandida futuramente sem alterar a estrutura fundamental do sistema.

12. Lotes Rurais

Lotes rurais permitem atividades relacionadas à exploração do território e de seus recursos naturais.

Empresas Matriz rurais podem operar principalmente em três áreas:

Agropecuária

Produção de produtos agropecuários.

A lista de produtos e suas respectivas regras de produção pertence ao:

22 — Receitas-Produção

Extrativismo

Extração de recursos naturais.

Inclui, entre outros recursos, petróleo.

O petróleo pertence exclusivamente à categoria de Extrativismo, e não à Mineração.

Mineração

Extração de recursos minerais.

Os recursos minerais disponíveis não são escolhidos livremente pelo jogador. Eles são definidos pelo sistema geográfico através de geração procedural.

13. Recursos naturais

A disponibilidade de recursos naturais deve possuir distribuição espacial.

Um lote não deve simplesmente realizar uma rolagem completamente independente para determinar se possui um recurso.

Em vez disso, recursos devem formar regiões de maior e menor concentração.

Isso permite a existência de:

áreas ricas em determinado recurso;
áreas pobres;
regiões sem ocorrência;
concentrações locais;
depósitos maiores ou menores;
padrões geográficos coerentes.

Esse sistema deverá ser compatível com uma futura geração procedural visual do território.

14. Distribuição de petróleo

O petróleo é um recurso raro e sua presença deverá ser determinada espacialmente.

A chance de ocorrência de petróleo deve ser influenciada pela distribuição geográfica do recurso, permitindo a formação de regiões com maior probabilidade de ocorrência.

Portanto:

probabilidade global ≠ distribuição uniforme

Uma região pode concentrar grande parte das ocorrências enquanto outras regiões praticamente não possuem petróleo.

Os parâmetros exatos pertencem ao sistema de recursos/produtos e poderão ser ajustados durante os testes.

15. Distribuição de minerais

Os recursos minerais seguem o mesmo princípio de distribuição espacial do petróleo, porém são menos raros em termos gerais.

Cada recurso possui uma raridade própria.

Valores iniciais para Bot Test:

Recurso	Raridade
Ferro	20%
Cobre	10%
Sílica	30%
Carvão	15%
Sal	12%
Lítio	6%
Ouro	2%
Prata	4%
Diamante	1%

Esses valores devem ser tratados como parâmetros de raridade/distribuição, e não necessariamente como uma probabilidade literal independente para cada lote.

A geração geográfica deve combinar:

Raridade do recurso + distribuição espacial

Assim, por exemplo, o Ferro pode ser relativamente comum globalmente, mas ainda formar regiões com concentração muito maior de depósitos.

Os valores acima são parâmetros de teste e poderão ser ajustados posteriormente no sistema de produtos/receitas.

16. Zoneamento

Cada bairro e lote possui regras padrão de uso territorial.

A princípio, os diferentes usos devem permanecer relativamente separados:

Residencial
Comercial
Industrial
Institucional
Especial
Rural

O zoneamento padrão existe para impedir que qualquer empresa ou estrutura seja instalada indiscriminadamente em qualquer local.

Entretanto, o zoneamento não é necessariamente imutável.

Leis, projetos públicos e outras mecânicas políticas poderão posteriormente:

alterar permissões;
liberar determinados usos;
restringir determinados usos;
modificar zoneamentos;
criar exceções territoriais.

Portanto, o zoneamento deve ser implementado de forma parametrizável, evitando regras estruturais impossíveis de alterar posteriormente.

17. Distância e coordenadas

A distância no mundo deve ser derivada das coordenadas X/Y das localidades.

Não haverá uma variável especial de gameplay chamada “distância até a capital”.

As coordenadas são a base geográfica. Cada sistema poderá transformar distância em um efeito diferente.

Exemplos:

tempo de deslocamento;
custo de transporte;
impacto do deslocamento para o trabalho;
logística empresarial;
acesso a serviços;
atração de determinadas atividades;
eventos ou mecânicas futuras.

Assim, a mesma distância geográfica pode produzir efeitos diferentes dependendo do sistema que a utiliza.

18. Deslocamento para trabalho

A distância entre a residência do jogador e o local de trabalho pode afetar sua QoL.

Quanto maior o deslocamento, maior poderá ser seu impacto negativo sobre o jogador.

O cálculo exato será definido pelo sistema de transporte e pelo modelo de QoL.

A geografia deve fornecer apenas a base espacial necessária para esse cálculo.

19. Geração inicial para Bot Test

Os mapas utilizados nos testes com bots poderão possuir condições iniciais controladas.

Essas condições podem incluir:

quantidade maior de bairros;
distribuição específica de recursos;
diferentes concentrações populacionais;
diferentes estruturas econômicas;
outras características utilizadas para comparação entre bots.

Esses mapas são cenários de teste.

As condições iniciais utilizadas para Bot Test não devem ser tratadas como regras permanentes do mundo final.

20. Dívidas de aluguel

A inadimplência de aluguel utilizará o sistema genérico de dívidas.

Não será criado um mecanismo especial de cobrança exclusivamente para aluguel.

Uma dívida deverá seguir a mesma estrutura geral utilizada pelo restante do jogo, incluindo seus mecanismos de:

origem;
credor;
valor;
saldo;
retenção de renda;
quitação;
demais regras gerais do sistema financeiro.

Isso mantém o sistema consistente e evita múltiplos mecanismos de dívida com comportamentos diferentes.

21. Relação com outros sistemas

O sistema de geografia deve servir como infraestrutura para outros sistemas do jogo.

Empresas

Define onde uma empresa pode ser estabelecida e quais usos territoriais são permitidos.

Imóveis

Define a localização física de residências e outras propriedades.

Escolas

Define a distribuição das escolas dentro dos bairros e influencia sua capacidade territorial.

Saúde

Define a localização dos hospitais e o acesso geográfico aos serviços médicos.

Transporte

Utiliza coordenadas e distâncias para calcular deslocamento, tempo e custo.

Política

Permite que leis e projetos alterem características territoriais e zoneamento.

Economia

Permite que localização, distância e disponibilidade de recursos influenciem produção e comércio.

Recursos naturais

Determina espacialmente a ocorrência de petróleo e minerais.

QoL

Pode utilizar distância, deslocamento, acesso a serviços e características do imóvel como variáveis.

22. Diretriz para geração procedural futura

A estrutura geográfica deverá ser construída pensando em uma futura representação visual procedural do país.

Portanto, o sistema deve preservar explicitamente:

Posição → Relação espacial → Tipo territorial → Recursos → Ocupação

A geração do mundo não deve depender de atributos artificiais que existam apenas para gameplay imediato quando esses atributos puderem ser derivados de dados espaciais.

O objetivo é que o mesmo conjunto de dados utilizado pelo simulador possa posteriormente alimentar um sistema visual capaz de representar:

país;
estados;
cidades;
bairros;
lotes;
estradas;
concentração urbana;
regiões rurais;
recursos naturais;
expansão territorial.
23. Princípios de implementação

A implementação deve seguir os seguintes princípios:

1. Coordenadas são a base espacial.
Distâncias e relações geográficas devem ser derivadas delas.

2. Recursos naturais possuem distribuição espacial.
Evitar geração puramente independente por lote.

3. Raridade e localização são conceitos diferentes.
A raridade define frequência global; a distribuição espacial define onde os recursos se concentram.

4. Zoneamento deve ser parametrizável.
Leis e projetos poderão alterá-lo futuramente.

5. Não utilizar classe social fixa de bairro.
Condições econômicas e qualidade devem emergir dos sistemas de imóveis, economia, QoL e política.

6. Cenários de Bot Test não são regras do mundo final.

7. A geografia deve ser reutilizável.
O mesmo modelo espacial deverá servir ao simulador atual e à futura visualização procedural.

24. Fora do escopo imediato

Não fazem parte da implementação final deste documento, embora possam utilizar sua estrutura posteriormente:

geração visual 2D/3D do país;
sistema rodoviário detalhado;
trânsito;
transporte público detalhado;
simulação física de relevo;
erosão;
hidrografia detalhada;
clima;
biomas avançados;
simulação geológica de alta fidelidade.

Esses sistemas poderão utilizar as coordenadas, zonas e recursos definidos aqui sem exigir mudanças estruturais no modelo geográfico.

25. Fonte de verdade relacionada

A geografia define onde as coisas existem.

Os demais sistemas continuam responsáveis por definir o que elas fazem.

Em especial:

02 — Empresas → regras de funcionamento das empresas
08 — Geografia e Imóveis → localização, território e zoneamento
09 — Orçamento Público → orçamento e financiamento público
10 — Imóveis e Zonas → regras detalhadas de propriedades e zonas
22 — Receitas-Produção → produtos, recursos, receitas e regras de produção
