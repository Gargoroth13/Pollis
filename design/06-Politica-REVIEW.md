# 06 — Política

**Status: REVIEW**

## 06.0. Objetivo do sistema

O sistema político é a principal estrutura institucional do Polis para transformar decisões e interesses dos jogadores em decisões de governo.

A política deve dar aos jogadores poder real para administrar o país, Estados e cidades, mas sem transformar os cargos em uma fonte de poder absoluto. O sistema utiliza eleições, Câmara dos Deputados, limites constitucionais, transparência e sucessão para distribuir e limitar esse poder.

A filosofia geral é manter o máximo de agency possível para os jogadores. O sistema fornece as instituições e regras; os jogadores formam alianças, fazem campanha, escolhem candidatos, propõem mudanças e avaliam o desempenho dos governantes.

O sistema político também deve permanecer conectado aos demais sistemas do jogo. Governo administra orçamento, nomeia diretores, executa projetos públicos, influencia leis e administra estruturas públicas. Decisões políticas podem produzir consequências econômicas, sociais e militares, mas essas consequências são detalhadas nos documentos correspondentes.

---

# 06.1. Estrutura política

O Polis possui três cargos executivos:

| Cargo | Quantidade | Eleitores | Mandato |
|---|---:|---|---:|
| Presidente | 1 | Todos os jogadores residentes no país | 6 meses |
| Governador | 1 por Estado | Jogadores residentes no Estado | 6 meses |
| Prefeito | 1 por cidade | Jogadores residentes na cidade | 4 meses |

O Legislativo nacional é formado pela **Câmara dos Deputados**.

O primeiro Bot Test não possui STF, tribunais políticos ou outra estrutura judicial eleitoral. A fiscalização política é feita principalmente por transparência, registros públicos, Câmara, eleições e mecanismos de contestação dos jogadores.

---

# 06.2. Cargos políticos

Cada jogador pode possuir **no máximo um cargo político simultaneamente**.

Cargos políticos são posições institucionais diferentes dos empregos comuns. O ocupante recebe remuneração própria e exerce suas funções por meio de ações administrativas relacionadas ao cargo.

O jogador não precisa abandonar sua vida social, propriedades ou participação política para ocupar o cargo, mas existem restrições específicas de trabalho e conflito de interesses descritas nas seções correspondentes.

---

# 06.3. Elegibilidade para cargos executivos

## Prefeito

Qualquer jogador pode se candidatar a Prefeito desde que cumpra os requisitos gerais de candidatura.

O candidato deve:

- possuir o tempo mínimo de conta definido pelo sistema;
- possuir o nível mínimo de Carisma definido pelo sistema;
- residir na cidade para a qual está se candidatando;
- não estar concorrendo simultaneamente a outro cargo político.

Não é necessário possuir experiência política ou diploma universitário para se candidatar a Prefeito.

## Governador

Para se candidatar a Governador, o jogador deve ter exercido anteriormente o cargo de Prefeito e cumprir os requisitos gerais de candidatura.

O candidato deve residir no Estado para o qual está se candidatando.

## Presidente

Para se candidatar a Presidente, o jogador deve:

- ter exercido anteriormente o cargo de Governador;
- possuir um dos três diplomas universitários principais: Engenharia, Direito ou Medicina;
- possuir o tempo mínimo de conta definido pelo sistema;
- possuir o nível mínimo de Carisma definido pelo sistema;
- residir no país;
- não estar concorrendo simultaneamente a outro cargo político.

Os requisitos de experiência política, diploma, Carisma e tempo mínimo de conta podem ser alterados por leis paramétricas quando esses parâmetros forem disponibilizados para alteração.

---

# 06.4. Elegibilidade para Deputado

Qualquer jogador pode se candidatar a Deputado desde que cumpra os requisitos gerais de candidatura:

- tempo mínimo de conta;
- Carisma mínimo;
- residência no país;
- candidatura única.

Não é necessário ter exercido outro cargo político e não é necessário possuir diploma universitário para ser Deputado.

---

# 06.5. Inscrição de candidatura

O jogador se candidata presencialmente dentro do sistema político do jogo, utilizando qualquer prédio governamental disponível para inscrição de candidatura.

A inscrição registra:

- jogador candidato;
- cargo pretendido;
- território da eleição, quando aplicável;
- data e horário da candidatura.

Uma mesma pessoa não pode estar inscrita simultaneamente para mais de um cargo.

A candidatura por si só não encerra o cargo político atual do jogador. Um ocupante que esteja legalmente apto a buscar outro cargo pode concorrer, mas só poderá ocupar um cargo após a posse.

---

# 06.6. Calendário eleitoral

Ao final de cada mandato é aberto um período eleitoral de **7 dias**, dividido em duas fases:

### Dias 1 a 3 — Candidaturas

Jogadores elegíveis podem registrar suas candidaturas.

Ao final do terceiro dia, novas candidaturas não podem ser adicionadas à eleição.

### Dias 4 a 7 — Votação

Os jogadores elegíveis podem votar nos candidatos oficialmente inscritos.

A votação permanece aberta durante quatro dias.

Os votos são contabilizados conforme são registrados, permitindo acompanhar a apuração durante a eleição.

Ao final do período de votação, o candidato com mais votos vence.

Caso exista apenas um candidato ao final do período de candidatura, ele é eleito automaticamente e a votação não precisa ser realizada.

---

# 06.7. Direito de voto

Todo jogador possui **um voto** em cada eleição para a qual tenha direito de votar.

O voto é individual e não pode ser transferido para outro jogador.

O jogador pode votar no próprio nome quando for candidato.

### Eleição presidencial

Todos os jogadores residentes no país podem votar.

### Eleição para Governador

Somente jogadores residentes no Estado correspondente podem votar.

### Eleição para Prefeito

Somente jogadores residentes na cidade correspondente podem votar.

### Eleição para Deputados

Todos os jogadores residentes no país podem votar.

Cada jogador possui um voto para a eleição da Câmara.

---

# 06.8. Apuração e empate

A apuração ocorre continuamente conforme os votos são registrados.

Para Prefeito, Governador e Deputado, o candidato com maior número de votos vence.

Não existe segundo turno para esses cargos.

## Empate para Presidente

Somente a eleição presidencial possui uma regra especial de desempate.

Caso dois ou mais candidatos terminem empatados em primeiro lugar, é realizada uma nova votação exclusivamente entre os candidatos empatados.

O segundo turno possui a mesma estrutura básica de votação, utilizando os mesmos eleitores da eleição presidencial.

Caso ocorra novo empate, a votação entre os candidatos empatados é repetida até que exista um vencedor.

---

# 06.9. Reeleição

Um jogador pode ser reeleito para o mesmo cargo no máximo uma vez consecutivamente.

Assim, o padrão inicial permite até dois mandatos consecutivos no mesmo cargo:

1. primeiro mandato;
2. uma reeleição.

O limite de reeleição é um parâmetro que pode ser alterado por lei paramétrica.

A regra aplica-se aos cargos executivos e aos Deputados.

A eleição para outro cargo não constitui reeleição. Por exemplo, um Prefeito que posteriormente concorre a Governador está iniciando outro cargo, desde que cumpra os requisitos exigidos.

---

# 06.10. Mandatos

### Prefeito

Mandato de 4 meses.

### Governador

Mandato de 6 meses.

### Presidente

Mandato de 6 meses.

### Deputados

Mandato de 6 meses.

O encerramento normal do mandato abre o período eleitoral correspondente.

A perda de um cargo durante o mandato não transforma automaticamente a sucessão em uma nova eleição. O procedimento depende da forma pela qual o cargo foi perdido, conforme a seção de sucessão.

---

# 06.11. Remuneração dos cargos políticos

A remuneração política é independente da quantidade de ações administrativas realizadas pelo ocupante.

O político recebe salário periódico enquanto estiver no cargo.

O valor dos cargos políticos é calculado a partir do salário mínimo nacional:

```text
salário do cargo = salário mínimo nacional × multiplicador do cargo
```

Cada cargo possui seu próprio multiplicador.

Os multiplicadores são parâmetros políticos e podem ser alterados pelo sistema de leis paramétricas.

Como o salário mínimo também é uma lei federal paramétrica, mudanças no salário mínimo afetam simultaneamente a remuneração dos cargos políticos e os pisos salariais aplicáveis ao restante da economia.

Isso cria um trade-off político real: um governante pode defender aumento do salário mínimo, beneficiando trabalhadores e aumentando sua própria remuneração, mas também elevando os custos de empresas e podendo gerar efeitos econômicos negativos.

---

# 06.12. Trabalho do político

Não existe um botão de trabalho separado para cada ação política.

O jogador acessa a área de ações do seu cargo e executa diretamente a decisão desejada.

Cada ação administrativa relevante possui um custo de Energia definido para aquela ação.

Exemplos de ações administrativas incluem:

- distribuir ou alocar orçamento sob responsabilidade do cargo;
- executar transferências determinadas pela estrutura orçamentária;
- nomear diretores;
- iniciar ou autorizar ações administrativas dentro das competências do cargo;
- apresentar propostas legislativas;
- encaminhar propostas políticas;
- sancionar ou vetar leis quando essa competência existir.

A ação administrativa é o próprio trabalho do cargo. Não existe remuneração adicional por clique.

O custo de Energia de cada ação e outras limitações operacionais são parâmetros do sistema e podem ser ajustados durante o balanceamento.

---

# 06.13. Desenvolvimento de Skills por cargos políticos

O exercício dos cargos políticos desenvolve **Inteligência e Carisma**.

Os três cargos executivos possuem ganho diário de ambas as Skills:

| Cargo | Inteligência | Carisma |
|---|---|---|
| Prefeito | ganho diário menor | ganho diário menor |
| Governador | ganho diário intermediário | ganho diário intermediário |
| Presidente | ganho diário maior | ganho diário maior |

Os valores exatos são parâmetros de balanceamento.

O ganho é diário e não depende da quantidade de ações administrativas realizadas durante o dia. Isso evita incentivar o jogador a repetir ações apenas para farmar Skill.

Físico não é desenvolvido diretamente pelo exercício de cargos políticos.

Os Deputados também podem possuir ganho diário de Inteligência e Carisma, com valores próprios do cargo, caso essa remuneração de progressão seja mantida na configuração final. O valor deve ser parametrizado junto dos demais ganhos políticos.

---

# 06.14. Competências do Presidente

O Presidente é a autoridade executiva nacional.

Entre suas responsabilidades estão:

### Orçamento federal

O Presidente administra a parcela do orçamento federal que permanece sob responsabilidade da União e decide a distribuição da arrecadação federal destinada aos Estados conforme as regras do sistema orçamentário.

A mecânica detalhada de arrecadação e distribuição está em `09 — Orçamento Público`.

### Projetos e construções públicas federais

O Presidente pode direcionar recursos para construções e projetos públicos de competência federal.

A execução física das obras ocorre de acordo com as regras de `09 — Orçamento Público` e `10 — Imóveis e Zonas`.

### Administração federal

O Presidente executa as decisões administrativas que pertencem ao nível federal.

### Instituições

Quando uma instituição pública federal possuir direção política direta, o Presidente realiza as nomeações correspondentes.

Nas instituições em que exista Diretor, o Diretor administra a operação cotidiana e contrata os demais funcionários.

### Legislação

O Presidente pode apresentar propostas de lei, receber propostas provenientes dos governos estaduais e municipais e participar do processo legislativo através de sanção ou veto.

### Exército

O Presidente escolhe o Marechal do Exército.

As regras específicas de pessoal, hierarquia, mobilização e combate estão em `19 — Militar`.

---

# 06.15. Competências do Governador

O Governador é a autoridade executiva do Estado.

Entre suas responsabilidades estão:

### Distribuição do orçamento estadual

O Governador distribui os recursos recebidos pelo Estado entre os municípios sob sua administração, conforme as regras orçamentárias.

### Orçamento militar estadual

O Governador define a distribuição do orçamento militar destinado à estrutura militar do Estado, respeitando as regras gerais do orçamento público e os parâmetros aplicáveis.

### Administração estadual

O Governador executa as decisões administrativas pertencentes ao Estado.

### Projetos

O Governador pode administrar e encaminhar projetos de competência estadual.

### Propostas legislativas

O Governador pode apresentar ao Presidente propostas de leis que considere importantes para seu Estado.

O envio de uma proposta não significa aprovação automática. O Presidente decide se a proposta será formalmente encaminhada ao processo legislativo federal.

---

# 06.16. Competências do Prefeito

O Prefeito é a autoridade executiva municipal.

Entre suas responsabilidades estão:

### Orçamento municipal

O Prefeito distribui e executa o orçamento municipal recebido pela cidade.

### Administração municipal

O Prefeito executa decisões administrativas de competência municipal.

### Instituições públicas

O Prefeito nomeia os Diretores das instituições públicas municipais que estiverem sob sua responsabilidade, incluindo, conforme aplicável:

- escolas;
- universidades;
- hospitais;
- outras instituições públicas futuras.

O Diretor administra a operação cotidiana da instituição e realiza as contratações dos demais funcionários.

### Projetos públicos

O Prefeito administra projetos e gastos municipais dentro dos limites do orçamento.

### Propostas legislativas

O Prefeito pode encaminhar ao Presidente propostas de leis que considere importantes para sua cidade.

A proposta depende do encaminhamento político posterior para entrar no processo legislativo federal.

---

# 06.17. Administração das instituições públicas

O sistema utiliza uma separação entre autoridade política e administração cotidiana.

O político responsável pelo território nomeia o Diretor da instituição.

O Diretor possui responsabilidade operacional e administra os funcionários da instituição.

Exemplo:

> Prefeito → nomeia Diretor da escola → Diretor contrata professores e administra a escola.

O político não realiza a contratação individual de todos os funcionários da instituição.

Essa estrutura reduz microgerenciamento e preserva uma cadeia administrativa clara.

---

# 06.18. Câmara dos Deputados

A Câmara dos Deputados é o Legislativo nacional do Polis.

Sua função principal é impedir que o Presidente consiga transformar unilateralmente suas próprias propostas em leis.

O número de Deputados é calculado por:

```text
número de Deputados = max(5, floor(jogadores residentes no país / 500))
```

A contagem utiliza jogadores residentes no país.

Não existem deputados estaduais ou municipais na primeira versão.

---

# 06.19. Eleição da Câmara

Os Deputados são eleitos diretamente pelos jogadores residentes no país.

A eleição ocorre no mesmo ciclo eleitoral dos cargos executivos nacionais e subnacionais.

Cada jogador possui um voto.

Os candidatos mais votados ocupam as vagas disponíveis na Câmara.

Não existe uma eleição proporcional complexa por Estado ou outro mecanismo intermediário na primeira versão.

O mandato de cada Deputado é de 6 meses.

Os Deputados seguem a regra geral de uma reeleição consecutiva.

---

# 06.20. Processo legislativo

Todas as leis do primeiro sistema do Polis são **leis federais** e possuem aplicação nacional.

Não existe legislação estadual ou municipal independente no Bot Test.

O objetivo dessa estrutura é manter um único sistema legislativo enquanto Governadores e Prefeitos continuam possuindo autonomia administrativa e orçamentária dentro de suas competências.

### Proposição

Podem apresentar propostas legislativas:

- Presidente;
- Deputados.

Governadores e Prefeitos podem encaminhar propostas políticas ao Presidente. O Presidente pode adotá-las e levá-las ao processo legislativo federal.

### Câmara

A proposta é submetida à Câmara dos Deputados para votação.

A Câmara aprova ou rejeita a proposta de acordo com a maioria exigida pela natureza da votação.

### Sanção presidencial

Após aprovação da Câmara, a proposta segue ao Presidente.

O Presidente pode:

- sancionar a lei;
- vetar a lei.

### Veto

O veto pode ser derrubado pela Câmara mediante maioria qualificada de **2/3 dos Deputados**.

Depois de derrubado o veto, a proposta segue para promulgação conforme as regras do sistema legislativo.

Os detalhes de cada tipo de lei, seus parâmetros e seus efeitos pertencem a `07 — Leis` e `11 — Leis Paramétricas`.

---

# 06.21. Competência administrativa não é competência legislativa

O Executivo administra o Estado dentro das regras vigentes.

A Câmara participa da criação das leis.

Isso significa que uma decisão administrativa do Presidente, Governador ou Prefeito não pode simplesmente criar uma nova regra permanente que deveria ser uma lei.

Da mesma forma, uma lei aprovada não significa que o Legislativo passa a executar diretamente o orçamento ou administrar instituições. A execução continua sendo responsabilidade do Executivo correspondente.

---

# 06.22. Propostas de governos estaduais e municipais

Governadores e Prefeitos podem identificar necessidades locais e encaminhar propostas ao Presidente.

Essa é uma forma de participação política de baixo para cima sem criar legislativos estaduais e municipais independentes.

Exemplo:

> Prefeito identifica necessidade de uma mudança nacional → apresenta proposta ao Presidente → Presidente decide se a leva ao processo legislativo → Câmara vota → Presidente sanciona ou veta.

A mesma estrutura se aplica a propostas apresentadas por Governadores.

---

# 06.23. Conflito de interesses

O ocupante de cargo político pode possuir empresas privadas, mas existe uma separação entre patrimônio privado e poder público.

Enquanto estiver no cargo, uma empresa de propriedade do político **não pode receber contratos públicos**.

Além disso, o ocupante de cargo político não pode atuar como funcionário de outra empresa privada durante o mandato.

A propriedade da empresa não é automaticamente transferida nem encerrada ao assumir o cargo. A empresa continua pertencendo ao jogador, mas não pode utilizar o cargo político para obter contratos públicos.

A fiscalização dessa regra depende de transparência e registros públicos de contratos.

---

# 06.24. Sucessão normal

Ao assumir um cargo político, o jogador deve indicar previamente um **substituto elegível** para aquele cargo.

O substituto deve possuir todas as qualificações necessárias para ocupar o cargo naquele momento.

A indicação não transfere o cargo imediatamente. O substituto somente assume caso o titular perca o cargo por um motivo que utilize o sistema de sucessão normal.

### Perda normal do cargo

Renúncia, ausência prolongada/AFK ou outro mecanismo normal de perda do cargo:

> titular perde o cargo → substituto assume.

O substituto ocupa **somente o restante do mandato original**.

A sucessão normal não reinicia o período eleitoral.

---

# 06.25. Deposição por milícia

A deposição por milícia é uma forma excepcional de mudança de governo e possui regras próprias.

Quando uma ação de milícia é concluída com sucesso na sede do governo da capital, o Presidente é deposto segundo as regras de `19 — Militar`.

Nesse caso, o substituto previamente indicado pelo Presidente deposto **não assume**.

O líder da milícia vencedora assume a Presidência.

O novo Presidente inicia um **novo mandato completo de 6 meses**, como se tivesse acabado de iniciar um mandato eleitoral.

A deposição presidencial não remove automaticamente Governadores ou Prefeitos.

As leis existentes permanecem vigentes.

O mandato da Câmara dos Deputados é encerrado e uma nova eleição para a Câmara é convocada.

As garantias constitucionais permanecem válidas após a deposição. Uma mudança de governo não apaga as restrições constitucionais existentes.

As consequências específicas sobre o Exército, STF futuro ou outras instituições são tratadas nos documentos correspondentes.

---

# 06.26. Sucessão após o substituto

Se o substituto assumir e também perder o cargo antes do final do mandato, é realizada uma eleição extraordinária para aquele cargo.

A eleição extraordinária utiliza os mesmos critérios territoriais e de elegibilidade do cargo correspondente.

O vencedor assume somente pelo restante do mandato original, exceto no caso especial de tomada de poder por milícia, que possui a regra de novo mandato completo descrita na seção anterior.

---

# 06.27. Inatividade e AFK político

O Polis não deve considerar um governante ativo simplesmente porque ele entrou no jogo ou apertou um botão qualquer.

A atividade política deve ser avaliada pela combinação de:

- ações administrativas relevantes realizadas;
- obrigações administrativas efetivamente cumpridas;
- tempo de atividade real dentro do jogo;
- período desde a última atividade relevante.

Tempo com a página aberta, sem interação real, não deve ser suficiente para caracterizar atividade.

### Ações relevantes

São consideradas relevantes as ações que efetivamente alteram ou executam o estado do governo ou de suas responsabilidades.

Exemplos:

- distribuição de orçamento;
- execução de uma transferência orçamentária;
- nomeação de Diretor;
- decisão administrativa que altera uma instituição;
- execução de uma decisão legislativa dentro da competência do cargo;
- outras ações equivalentes definidas pelo sistema.

Entrar no jogo, abrir menus, conversar por chat ou realizar uma ação sem efeito administrativo não deve reiniciar o período de atividade por si só.

### Obrigações com prazo

Algumas funções políticas possuem ações que precisam ser executadas dentro de determinadas janelas.

Exemplo:

> se o cargo possui uma obrigação de distribuição orçamentária dentro de determinada janela e o governante não a executa, isso contribui fortemente para a caracterização de inatividade.

O mesmo princípio pode ser aplicado a nomeações ou outras responsabilidades cuja ausência gere um estado administrativo pendente.

### Avaliação

A perda por AFK ocorre quando o governante ultrapassa a janela de inatividade definida e também não apresenta atividade administrativa suficiente no período de avaliação.

Os valores de:

- janela máxima de inatividade;
- tempo mínimo de atividade;
- quantidade mínima de ações relevantes;
- prazo de obrigações administrativas;

são parâmetros do sistema e podem ser calibrados durante o Bot Test.

---

# 06.28. Constituição e limites do poder

O sistema político possui uma camada constitucional acima das leis ordinárias.

Leis comuns não podem simplesmente ignorar garantias constitucionais protegidas.

As regras específicas sobre quais garantias existem, quais leis são constitucionais e como uma alteração constitucional pode ocorrer pertencem ao sistema de leis.

Uma mudança de Presidente, inclusive por deposição, não reinicia a Constituição.

---

# 06.29. Fiscalização política sem Judiciário no primeiro Bot Test

A primeira versão não possui STF ou estrutura judicial específica para fiscalizar o Executivo.

A fiscalização política utiliza principalmente:

- transparência das contas públicas;
- histórico das decisões administrativas;
- contratos e gastos públicos visíveis;
- atuação da Câmara;
- eleições;
- feedback e pressão dos jogadores;
- mecanismos extraordinários de contestação, incluindo as ações do sistema de Milícias.

A necessidade de um sistema judicial poderá ser reavaliada após o Bot Test. Ele não deve existir apenas por convenção institucional se os demais mecanismos forem suficientes para gerar fiscalização real.

---

# 06.30. Transparência política

As ações relevantes dos governantes devem produzir registros públicos compatíveis com o sistema de transparência do jogo.

Devem ser rastreáveis, quando aplicável:

- decisões orçamentárias;
- transferências de dinheiro público;
- nomeações;
- projetos públicos;
- contratos públicos;
- propostas legislativas;
- sanções e vetos;
- mudanças administrativas relevantes.

A identidade do responsável pela ação deve permanecer associada ao registro para permitir fiscalização posterior.

Os detalhes de apresentação e consulta desses registros pertencem principalmente a `17 — Transparência de Mercado` e aos sistemas de histórico correspondentes.

---

# 06.31. Interações com outros sistemas

### `01 — Skills`

Define Inteligência, Físico e Carisma e as regras gerais de progressão. Política utiliza principalmente Inteligência e Carisma para progressão associada aos cargos.

### `03 — Escolas`

Fornece os diplomas necessários para candidaturas presidenciais.

### `04 — Dia a Dia`

Define Energia, que é consumida pelas ações administrativas dos políticos.

### `07 — Leis`

Define o sistema legislativo detalhado e as regras das leis.

### `09 — Orçamento Público`

Define arrecadação, distribuição, orçamento, gastos, dívida e execução financeira dos governos.

### `10 — Imóveis e Zonas`

Define a infraestrutura física onde funcionam instituições e projetos públicos.

### `11 — Leis Paramétricas`

Define os parâmetros políticos ajustáveis por lei, como salário mínimo, multiplicadores de remuneração, requisitos de candidatura e limite de reeleição quando esses parâmetros forem disponibilizados.

### `17 — Transparência de Mercado`

Fornece mecanismos de consulta e auditoria dos registros públicos relevantes.

### `19 — Militar`

Define ações de milícias, Exército, mobilização e deposição do governo.

### `20 — Feedback dos Jogadores`

Pode utilizar informações políticas e administrativas para apresentação de feedback e indicadores ao jogador.

### `21 — Bots`

Deve criar cenários de governos já em exercício e testar eleições, administração, inatividade, orçamento e comportamento político.

---

# 06.32. Regras fora do primeiro Bot Test

Ficam fora do primeiro Bot Test, salvo decisão posterior:

- STF e Judiciário político completo;
- Senado;
- Assembleias Legislativas estaduais;
- Câmaras Municipais/Vereadores;
- partidos políticos como entidades mecânicas;
- vice-presidente;
- colégio eleitoral;
- eleição proporcional complexa;
- segundo turno normal, exceto desempate presidencial;
- NPCs participando de eleições;
- sistema completo de corrupção;
- sistema judicial completo de impeachment;
- microgerenciamento de funcionários públicos individuais pelo político.

---

# 06.33. Bot Test

O Bot Test deve avaliar se o sistema político produz decisões relevantes sem exigir microgerenciamento excessivo.

Devem ser testados, entre outros, os seguintes cenários:

### Eleição com vários candidatos

Verificar apuração em tempo real, distribuição de votos e escolha do vencedor.

### Eleição com candidato único

Verificar vitória automática após encerramento da candidatura.

### Empate presidencial

Verificar segundo turno exclusivamente entre os empatados.

### Governador e Prefeito

Verificar corretamente o conjunto de eleitores segundo o território de residência.

### Câmara

Verificar geração correta do número de vagas, eleição direta dos Deputados e ocupação dos assentos pelos candidatos mais votados.

### Reeleição

Verificar bloqueio após o limite definido e possibilidade de alteração por parâmetro.

### Sucessão

Verificar substituição por renúncia e AFK sem reiniciar o mandato.

### Deposição

Verificar que a liderança da milícia assume a Presidência, recebe novo mandato completo e que Governadores e Prefeitos permanecem em seus cargos.

### Câmara após deposição

Verificar encerramento do mandato da Câmara e convocação de nova eleição.

### Inatividade

Verificar que acesso superficial ou ações irrelevantes não permitem burlar a regra de AFK.

### Administração

Verificar que os cargos possuem trabalho administrativo real, consumindo Energia e produzindo alterações observáveis no estado do governo.

### Conflito de interesses

Verificar que empresas de propriedade de políticos não conseguem receber contratos públicos enquanto seus proprietários ocupam cargos políticos.

### Integração orçamentária

Verificar que decisões políticas de distribuição e execução alteram corretamente os orçamentos correspondentes.

---

# 06.34. Parâmetros de balanceamento

Os seguintes valores devem permanecer parametrizados para permitir ajuste após Bot Test:

- Carisma mínimo por cargo;
- tempo mínimo de conta;
- exigências adicionais de candidatura;
- duração dos mandatos, caso futuramente parametrizada;
- duração das janelas eleitorais, caso futuramente parametrizada;
- número máximo de reeleições;
- multiplicador salarial de cada cargo;
- custo de Energia das ações administrativas;
- ganho diário de Inteligência por cargo;
- ganho diário de Carisma por cargo;
- janela de AFK;
- tempo mínimo de atividade;
- quantidade mínima de ações relevantes;
- prazos de obrigações administrativas;
- limites de votação e demais parâmetros eleitorais que forem disponibilizados por lei.

Esses parâmetros não devem exigir alteração estrutural do sistema quando forem ajustados.

---

# 06.35. Princípios de design

1. **Agency:** jogadores escolhem candidatos, votam, governam, fazem oposição e podem contestar o governo.
2. **Simplicidade:** eleições utilizam votação direta e o candidato mais votado vence, com segundo turno somente em empate presidencial.
3. **Responsabilidade:** ocupar um cargo implica tomar decisões reais e cumprir responsabilidades administrativas.
4. **Separação de funções:** Executivo administra; Legislativo participa da criação das leis; Constituição limita ambos.
5. **Transparência:** decisões públicas devem poder ser auditadas pelos jogadores.
6. **Continuidade institucional:** mudança de governante não apaga leis, orçamento, cidades ou instituições existentes.
7. **Sucessão:** o sistema evita vácuos de poder sem transformar toda perda de cargo em uma nova eleição.
8. **Contestação:** eleições são o mecanismo normal de mudança; deposição é uma ferramenta extraordinária do sistema de Milícias.
9. **Economia:** remuneração e decisões políticas permanecem conectadas à economia e ao orçamento público.
10. **Parâmetros ajustáveis:** números de balanceamento devem ser ajustáveis sem redesenhar a estrutura do sistema.
