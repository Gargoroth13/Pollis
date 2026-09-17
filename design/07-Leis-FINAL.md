# 07 — Leis

**Status:** FINAL — BOT TEST

## 07.1. Função do sistema

O sistema de Leis define como regras permanentes do Polis são propostas, discutidas, votadas, aprovadas, sancionadas, vetadas, alteradas, revogadas e aplicadas.

Uma lei é uma regra persistente que altera o funcionamento de um ou mais sistemas do jogo.

O sistema legislativo deve permitir que jogadores influenciem diretamente as regras nacionais por meio de seus representantes, sem exigir microgerenciamento excessivo.

No primeiro Bot Test existe uma única estrutura legislativa nacional: a Câmara dos Deputados. As leis são federais. Uma lei pode produzir efeitos sobre cidades, estados, empresas, imóveis ou outras estruturas específicas, mas isso é escopo de efeito da lei e não cria uma nova Câmara ou um novo processo legislativo local.

---

## 07.2. Tipos de lei

Existem dois conceitos gerais de lei:

### Lei estrutural

Altera a própria estrutura ou funcionamento de um sistema.

### Lei paramétrica

Altera um valor dentro de limites técnicos definidos pelo jogo.

No Bot Test, os jogadores não inventam livremente novos tipos de lei nem novos efeitos sistêmicos. As leis que podem ser propostas são definidas previamente pelo catálogo de `11 — Leis Paramétricas` e pelas demais regras legislativas/constitucionais definidas pelo design.

Para uma lei paramétrica, os únicos valores ajustáveis pelo jogador são os parâmetros `X` definidos pelo catálogo. Texto descritivo ou outros elementos da mecânica não podem ser alterados livremente pelo proponente.

---

## 07.3. Quem pode propor uma lei

Podem formalizar uma proposta legislativa:

- Presidente;
- Deputados federais.

Governadores e Prefeitos não formalizam diretamente uma lei federal. Eles podem enviar sugestões ao Presidente, que decide se transforma a sugestão em uma proposta formal.

Qualquer jogador pode participar politicamente da discussão, campanha ou pressão pública em torno de uma proposta, mas isso não cria uma proposta legislativa automaticamente.

---

## 07.4. Criação da proposta

Ao criar uma proposta, o proponente deve escolher uma lei existente no catálogo permitido e definir seus parâmetros `X` dentro dos limites técnicos estabelecidos para aquela lei.

A proposta registra pelo menos:

- autor;
- lei escolhida;
- parâmetros escolhidos;
- descrição da proposta;
- data e hora de criação;
- versão da proposta.

Uma proposta não pode alterar simultaneamente dois parâmetros independentes de leis diferentes, salvo quando o próprio catálogo definir explicitamente que os parâmetros pertencem à mesma lei.

---

## 07.5. Discussão pública

Toda proposta passa por um período de discussão antes de poder ser votada.

A discussão dura **3 dias de calendário**, no mínimo.

Durante a discussão:

- a proposta permanece pública;
- jogadores podem consultar seu conteúdo e seus efeitos estimados;
- o autor pode alterar os parâmetros `X` da proposta;
- o autor pode retirar a proposta.

Somente mudanças nos parâmetros `X` configuráveis pela lei são consideradas alterações da proposta.

Depois que a votação começa, a proposta fica congelada e não pode mais ser editada ou retirada pelo autor.

---

## 07.6. Calendário semanal de votação

As votações da Câmara acontecem em uma janela semanal fixa.

Toda **segunda-feira**, o sistema identifica as propostas que:

1. ainda estão válidas;
2. concluíram o período mínimo de discussão de 3 dias;
3. não estão bloqueadas por conflito com outra proposta;
4. estão aptas a entrar em votação.

Essas propostas iniciam a votação da Câmara na segunda-feira.

Isso significa, por exemplo, que uma proposta enviada na sexta-feira pode entrar na votação da segunda-feira seguinte.

Uma proposta enviada depois do limite necessário para completar os 3 dias de discussão espera a próxima janela semanal de votação.

O calendário utiliza o **horário oficial do servidor**, com a mudança semanal ocorrendo às **00:00 de segunda-feira**.

---

## 07.7. Início da votação

Quando uma proposta entra na janela de votação:

- sua versão é congelada;
- seus parâmetros `X` ficam imutáveis;
- a composição da Câmara utilizada para aquela votação é registrada;
- começa o prazo de votação de 3 dias.

O número de cadeiras e a composição considerados para aquela proposta ficam congelados durante toda a votação.

Uma mudança posterior na composição da Câmara não altera retroativamente o quórum daquela proposta.

---

## 07.8. Votação da Câmara

A Câmara vota cada proposta individualmente.

O prazo de votação é de **3 dias de calendário**.

Cada Deputado pode registrar:

- voto favorável;
- voto contrário;
- abstenção.

O Deputado pode alterar seu voto enquanto a votação estiver aberta. Quando o período terminar, somente o último voto registrado é considerado.

A ausência de voto até o encerramento é tratada como participação não realizada e não conta como voto favorável.

As votações são nominais e públicas. O histórico registra o voto individual de cada Deputado.

---

## 07.9. Regra de aprovação

Uma proposta é aprovada quando recebe **maioria absoluta da Câmara**.

Maioria absoluta significa mais da metade de todas as cadeiras consideradas para aquela votação, e não mais da metade apenas dos Deputados que votaram.

Exemplo com 5 cadeiras:

- 3 votos favoráveis → aprovada;
- 2 votos favoráveis → rejeitada;
- 2 favoráveis, 1 contrário e 2 abstenções → rejeitada.

Não existe empate com aprovação automática.

Uma proposta que não alcança a maioria absoluta é rejeitada.

---

## 07.10. Resultado da votação

Ao final dos 3 dias:

### Proposta rejeitada

A proposta é encerrada como rejeitada.

Ela deixa de alterar qualquer sistema e não produz efeitos.

### Proposta aprovada

A proposta passa para a etapa de **sanção presidencial**.

A aprovação da Câmara não coloca a lei em vigor imediatamente.

---

## 07.11. Proposta rejeitada e reapresentação

Uma proposta rejeitada pode ser reapresentada posteriormente.

A reapresentação possui um período de espera (cooldown) definido pelo sistema.

Quando a proposta é reapresentada com alteração real de parâmetro `X`, pode utilizar o cooldown reduzido definido para propostas modificadas.

Uma alteração real significa mudança em um ou mais parâmetros `X` da lei. Alterações apenas de texto, formatação ou apresentação não contam como alteração para redução de cooldown.

Os valores exatos dos cooldowns são parâmetros técnicos de balanceamento e não alteram a estrutura do sistema legislativo.

---

## 07.12. Sanção presidencial

Quando a Câmara aprova uma proposta, o Presidente recebe a proposta para sanção ou veto.

O Presidente possui **3 dias de calendário** para decidir.

Durante esse período, pode:

- sancionar;
- vetar.

A decisão e seu responsável ficam registrados publicamente.

---

## 07.13. Inação do Presidente

Se o Presidente não sancionar nem vetar dentro do prazo de 3 dias, ocorre **sanção automática**.

A ausência de decisão não cancela nem reinicia a proposta.

---

## 07.14. Veto presidencial

Se o Presidente vetar a proposta, ela não entra em vigor imediatamente.

O veto deve registrar:

- Presidente responsável;
- data e hora;
- proposta vetada;
- justificativa pública do veto, quando fornecida.

Depois do veto, a Câmara recebe a possibilidade de derrubá-lo.

---

## 07.15. Derrubada do veto

A Câmara pode derrubar o veto presidencial com **2/3 de todas as cadeiras consideradas para a votação**.

A votação para derrubar o veto também é pública e nominal.

O veto derrubado não retorna ao Presidente para uma segunda decisão.

Quando a Câmara derruba o veto, a proposta passa diretamente para a etapa de entrada em vigor no próximo `weekly tick`.

Se a Câmara não alcançar os 2/3 necessários, o veto permanece válido e a proposta é encerrada sem entrar em vigor.

O prazo e o calendário dessa votação de derrubada seguem a mesma janela legislativa de 3 dias da Câmara.

---

## 07.16. Separação entre aprovação e entrada em vigor

A aprovação política de uma lei e sua aplicação são etapas diferentes.

Uma lei aprovada e sancionada, ou uma lei cujo veto foi derrubado, fica registrada como **aprovada aguardando vigor**.

A lei entra efetivamente em vigor no próximo `weekly tick`.

O `weekly tick` oficial ocorre às **00:00 de segunda-feira**, no horário do servidor.

A aplicação não é retroativa.

Operações realizadas antes do horário de entrada em vigor continuam usando a regra anterior.

---

## 07.17. Propostas conflitantes

Não podem existir simultaneamente propostas legislativas concorrentes para alterar o mesmo parâmetro ou a mesma regra configurável.

Se uma proposta alterar, por exemplo, o salário mínimo, não é possível criar outra proposta de salário mínimo enquanto a primeira estiver em qualquer estágio ativo do processo legislativo.

A segunda proposta somente pode ser criada depois que a primeira tiver terminado seu processo e passado pelo próximo `weekly tick` quando aplicável.

Isso impede que diferentes propostas para o mesmo parâmetro sejam usadas simultaneamente para manipular o calendário legislativo.

---

## 07.18. Mudança do Presidente durante o processo

Uma proposta não pertence ao Presidente que a sanciona ou veta. Ela pertence ao processo legislativo.

Se o Presidente deixar o cargo enquanto uma proposta estiver aguardando sua sanção ou veto:

1. a proposta não é cancelada;
2. ela retorna para uma nova votação completa da Câmara;
3. a nova Câmara realiza uma nova votação de 3 dias;
4. se novamente aprovada, o novo Presidente recebe novo prazo de 3 dias para sancionar ou vetar.

A votação anterior não é parcialmente reaproveitada.

---

## 07.19. Deposição do Presidente

A deposição do Presidente, inclusive por ação do sistema de Milícias, não apaga propostas legislativas existentes.

Propostas que já estejam no processo legislativo permanecem registradas.

Se houver uma proposta aguardando decisão presidencial no momento da deposição, ela retorna para uma nova votação da Câmara.

O novo Presidente recebe a proposta novamente caso a Câmara a aprove.

A deposição também não revoga automaticamente leis que já estejam em vigor.

---

## 07.20. Perda de cargo do autor

Uma proposta não é cancelada porque seu autor deixou de ocupar o cargo político.

A proposta continua seguindo seu ciclo normal.

O histórico preserva o autor original, mesmo que ele deixe de ser Deputado ou outro cargo antes do final do processo.

---

## 07.21. Alteração de uma lei existente

Uma lei em vigor não é editada diretamente.

Para mudar qualquer um de seus parâmetros `X`, é criada uma nova proposta utilizando o mesmo item do catálogo legislativo.

A nova proposta passa pelo processo legislativo completo.

Enquanto a proposta antiga continua em vigor, ela permanece sendo a regra utilizada pelo jogo.

Quando a nova proposta entra em vigor, o parâmetro anterior é substituído pelo novo valor.

---

## 07.22. Revogação de uma lei

Uma lei em vigor não é apagada diretamente.

Para revogá-la, é criada uma proposta de revogação.

A revogação segue o mesmo processo legislativo:

- discussão;
- votação da Câmara;
- sanção ou veto;
- possível derrubada do veto;
- entrada em vigor no próximo `weekly tick`.

O histórico da lei original permanece disponível após sua revogação.

---

## 07.23. Constituição

A Constituição é uma camada superior às leis comuns.

Leis comuns não podem reduzir uma garantia constitucional abaixo do piso protegido.

No primeiro Bot Test, existem garantias constitucionais relacionadas a **moradia e educação**.

Os pisos constitucionais são definidos pelo sistema inicial e não podem ser reduzidos por uma lei comum.

Uma mudança de Presidente, inclusive por deposição, não reinicia nem altera automaticamente a Constituição.

Alterações constitucionais não fazem parte do primeiro Bot Test.

---

## 07.24. Preview de impacto

Antes e durante a discussão, a interface da proposta apresenta os efeitos esperados da mudança.

O preview deve separar claramente:

### Efeitos diretos conhecidos

São consequências que podem ser calculadas diretamente a partir da regra proposta.

Exemplo:

`Imposto sobre vendas: 5% → 8%`

### Efeitos estimados

São projeções calculadas utilizando os dados atuais do servidor.

Podem incluir, quando aplicável:

- alteração estimada da arrecadação;
- alteração estimada da renda líquida;
- alteração estimada de custos;
- alteração estimada de preços;
- alteração estimada de produção;
- outros indicadores derivados disponíveis no sistema.

Estimativas devem ser identificadas explicitamente como **estimativas**. Elas não representam garantia de que o comportamento futuro dos jogadores será igual ao histórico utilizado no cálculo.

---

## 07.25. Histórico e auditoria

Toda proposta legislativa possui histórico permanente.

O histórico deve registrar, no mínimo:

- autor original;
- versões da proposta durante a discussão;
- parâmetros `X` de cada versão;
- datas de criação e alteração;
- início e encerramento da discussão;
- início e encerramento da votação;
- voto individual de cada Deputado;
- resultado da Câmara;
- sanção ou veto presidencial;
- responsável pela sanção ou veto;
- data e hora das decisões;
- resultado de eventual votação de derrubada de veto;
- data de entrada em vigor;
- eventual data de revogação.

Os registros não são apagados quando uma lei deixa de estar em vigor.

---

## 07.26. Transparência

Propostas, votações, decisões presidenciais e alterações legislativas relevantes são públicas.

Qualquer jogador deve conseguir consultar:

- o conteúdo atual da proposta;
- seus parâmetros;
- seus efeitos conhecidos e estimados;
- quem a propôs;
- como cada Deputado votou;
- decisão do Presidente;
- histórico de versões;
- situação atual da lei.

A transparência integra o sistema político e não depende de uma lei específica que precise ser aprovada para existir.

---

## 07.27. Integração com outros sistemas

### `06 — Política`

Define cargos, eleições, elegibilidade, composição da Câmara, mandatos, sucessão, atividade política e relação entre Executivo e Legislativo.

### `09 — Orçamento Público`

Executa os efeitos financeiros das leis sobre arrecadação, gastos, orçamento, dívida e demais estruturas fiscais.

### `11 — Leis Paramétricas`

Contém o catálogo das leis e os limites `mínimo / máximo / padrão` de cada parâmetro disponível.

### `01 — Skills`

Define skills utilizadas por efeitos políticos e econômicos que possam ser alterados por lei.

### `04 — Dia a Dia`

Fornece Energia e demais estados utilizados por ações políticas e pelos sistemas afetados pelas leis.

### `10 — Imóveis e Zonas`

Recebe efeitos de leis relacionadas a imóveis, propriedade e zoneamento quando essas leis estiverem disponíveis no catálogo.

### `19 — Militar`

Pode utilizar leis e orçamento que alterem condições relevantes para Exército, Milícias e ações de deposição.

### `17 — Transparência de Mercado`

Fornece mecanismos de consulta e auditoria dos registros públicos e econômicos utilizados pela transparência do sistema.

---

## 07.28. Fora do primeiro Bot Test

Não fazem parte do primeiro Bot Test, salvo decisão posterior:

- STF e Judiciário político completo;
- Senado;
- Assembleias Legislativas estaduais;
- Câmaras Municipais/Vereadores;
- partidos políticos como entidades mecânicas;
- vice-presidente;
- colégio eleitoral;
- eleição proporcional complexa;
- segundo turno normal, exceto o mecanismo específico de desempate presidencial já definido em `06 — Política`;
- NPCs participando de eleições;
- sistema completo de corrupção;
- sistema judicial completo de impeachment;
- alterações constitucionais;
- criação livre de novos tipos de lei pelos jogadores.

---

## 07.29. Bot Test

O Bot Test deve verificar pelo menos os seguintes cenários:

### Criação e discussão

- Presidente cria uma proposta;
- Deputado cria uma proposta;
- proposta recebe versão nova durante discussão;
- autor retira proposta durante discussão;
- autor tenta alterar proposta depois do início da votação;
- proposta é bloqueada quando conflita com outra proposta ativa;
- proposta continua válida quando o autor perde o cargo.

### Calendário

- proposta enviada na sexta entra na votação da segunda quando cumprir a regra mínima de discussão;
- proposta que não cumprir o período mínimo aguarda a próxima janela;
- votação começa somente na segunda-feira;
- `weekly tick` ocorre na segunda-feira às 00:00 no horário do servidor.

### Câmara

- votação de 3 dias;
- voto nominal;
- alteração do voto durante a votação;
- maioria absoluta calculada sobre todas as cadeiras da votação;
- empate/requisito de maioria não alcançado → rejeição;
- proposta aprovada → etapa presidencial;
- proposta rejeitada → encerramento;
- composição utilizada na votação permanece fixa durante aquela votação.

### Presidente

- sanção dentro do prazo;
- veto dentro do prazo;
- sanção automática por inação;
- proposta retorna para nova votação se o Presidente perder o cargo antes de decidir;
- deposição presidencial não apaga propostas existentes.

### Veto

- veto abre possibilidade de derrubada pela Câmara;
- 2/3 das cadeiras são necessários;
- veto derrubado não retorna ao Presidente;
- lei com veto derrubado entra no próximo `weekly tick`.

### Aplicação

- lei aprovada não altera operações passadas;
- lei entra em vigor somente no `weekly tick` definido;
- alteração de parâmetro usa nova proposta;
- revogação usa nova proposta;
- histórico permanece consultável após revogação.

### Transparência

- cada voto individual é consultável;
- versões da proposta são preservadas;
- sanções, vetos e derrubadas de veto são auditáveis;
- preview diferencia efeitos diretos de estimativas.

---

## 07.30. Regra de implementação

O sistema deve implementar o processo legislativo exatamente conforme definido neste documento.

Valores de balanceamento e limites numéricos específicos pertencem ao catálogo de `11 — Leis Paramétricas` ou aos respectivos documentos de sistema.

Alterações estruturais no fluxo legislativo após o início do Bot Test devem passar por revisão de design antes de implementação.
