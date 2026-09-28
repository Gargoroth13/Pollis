# 14 — Rankings

**Status:** FINAL — BOT TEST  
**Escopo:** Rankings públicos do jogo  
**Versão:** Bot Test

---

## 14.1. Objetivo

O sistema de Rankings apresenta comparações objetivas entre jogadores, empresas e organizações com base em dados reais já produzidos pelos sistemas do jogo.

Existem dois grupos principais:

- **Rankings ao vivo:** representam a situação atual ou uma janela recente de dados.
- **Rankings históricos:** registram recordes que já foram alcançados e não são apagados quando o desempenho cai posteriormente.

Os rankings não criam recursos, bônus econômicos ou vantagens diretas. Eles são uma camada de apresentação e competição social baseada nos dados existentes.

---

## 14.2. Princípios gerais

O ranking deve sempre utilizar dados que já existam no jogo. Não deve ser criado um sistema paralelo de pontuação apenas para produzir uma posição no ranking.

Quando a métrica possuir uma janela temporal, apenas os dados efetivamente ocorridos dentro daquela janela são considerados.

Quando dois participantes possuem exatamente o mesmo valor da métrica, eles podem ocupar a mesma posição. Um critério de desempate só deve ser utilizado quando estiver explicitamente definido neste documento.

O sistema deve distinguir claramente entre:

- valor atual;
- valor acumulado em uma janela temporal;
- recorde histórico.

Rankings ao vivo podem mudar constantemente. Rankings históricos representam máximos efetivamente atingidos.

---

# 14.3. Rankings ao vivo

## 14.3.1. Maior patrimônio líquido

Mede o patrimônio líquido atual do jogador.

O valor deve considerar os componentes de patrimônio já reconhecidos pelo sistema financeiro/econômico do jogo, descontando os passivos que compõem o patrimônio líquido.

O ranking deve ser recalculado quando uma alteração relevante de patrimônio ocorrer.

---

## 14.3.2. Maior empresa

Representa a maior empresa entre as empresas existentes no momento.

Critério principal:

1. maior quantidade de estrelas;
2. em caso de empate, maior quantidade de funcionários.

O ranking não utiliza um valor monetário estimado da empresa no Bot Test.

---

## 14.3.3. Maior produção

Representa a maior produção efetivamente realizada por um jogador/empresa dentro dos **últimos 14 dias**.

A janela de 14 dias foi escolhida para reduzir oscilações excessivas de uma janela muito curta e produzir um indicador mais estável.

A métrica deve utilizar produção efetivamente registrada pelo sistema, e não apenas capacidade produtiva, energia disponível ou produção potencial.

A unidade de comparação deve seguir a métrica de produção definida pelo sistema produtivo. O ranking não deve somar produtos diferentes de maneira arbitrária; a implementação deve definir uma unidade agregável compatível com os dados produtivos existentes.

---

## 14.3.4. Melhor QoL pessoal

Representa o jogador com o maior valor de **Qualidade de Vida (QoL)** atual.

O ranking utiliza o valor efetivamente calculado pelo sistema de Dia a Dia.

Não existe bônus ou multiplicador específico criado pelo ranking.

---

## 14.3.5. Maior influência política

Este ranking permanece definido como conceito, mas está **fora do escopo do Bot Test**.

A implementação só deve ocorrer quando existir uma métrica objetiva e documentada de influência política.

Não deve ser criado um índice arbitrário apenas para preencher o ranking.

---

## 14.3.6. Maior empregador

Representa o jogador ou empresa que possui a maior quantidade de funcionários atualmente empregados.

A métrica utiliza funcionários efetivamente vinculados às empresas no momento da consulta/recalculo.

---

## 14.3.7. Maior contribuinte

Representa o jogador ou entidade que pagou o maior valor em impostos dentro dos **últimos 30 dias**.

São considerados impostos efetivamente pagos, e não apenas valores calculados, devidos ou previstos.

A janela de 30 dias acompanha o objetivo de medir contribuição econômica recente sem depender exclusivamente de um único ciclo imediato.

---

## 14.3.8. Melhor escola/universidade

Representa a instituição de ensino com a maior **qualidade atual**.

A métrica utiliza diretamente a qualidade calculada pelo sistema de Escolas/Universidades.

Não deve existir pontuação paralela específica para o ranking.

---

## 14.3.9. Maior organização

Representa a maior organização do jogo segundo a quantidade atual de membros.

No Bot Test, a aplicação prática do ranking é principalmente sobre **milícias**, utilizando a quantidade de membros da organização.

---

## 14.3.10. Conta mais antiga

Representa a conta com maior tempo desde sua criação.

A métrica é simples:

> `data atual - data de criação da conta`

O ranking não exige atividade contínua para permanecer elegível.

Uma conta criada há mais tempo permanece mais antiga mesmo que fique períodos sem jogar.

---

## 14.3.11. Maior tempo ativo

Representa o maior período de atividade contínua de uma conta.

A atividade é medida por ações válidas registradas pelo jogo, e não simplesmente por login, permanência conectado ou abertura de páginas.

Para manter a sequência ativa, o intervalo entre duas ações válidas consecutivas deve ser **inferior a 3 dias (72 horas)**.

Se existir um intervalo de **3 dias ou mais**, a sequência é encerrada e uma nova sequência começa na próxima ação válida.

Exemplo:

- ação na segunda-feira às 10:00;
- ação na quarta-feira às 09:00 → sequência continua;
- próxima ação no sábado às 10:00 → intervalo de 73 horas; a sequência anterior termina;
- a ação de sábado inicia uma nova sequência.

O ranking deve armazenar o maior período de atividade contínua já alcançado pela conta.

A atividade válida deve ser baseada em ações reais de gameplay. Login, chat e simples navegação de páginas não devem reiniciar a sequência isoladamente.

---

# 14.4. Rankings históricos

Rankings históricos registram o maior valor que um participante já alcançou.

Quando um novo recorde é atingido, o registro anterior é substituído pelo novo recorde. Quando o desempenho atual cai, o recorde histórico permanece.

O sistema deve armazenar a data em que o recorde foi estabelecido e a entidade responsável pelo recorde.

---

## 14.4.1. Maior patrimônio líquido já alcançado

Registra o maior patrimônio líquido que um jogador já atingiu.

A queda posterior do patrimônio não apaga o recorde.

---

## 14.4.2. Maior empresa já alcançada

Registra o maior nível de estrela já alcançado por uma empresa.

Critério principal:

1. maior quantidade de estrelas alcançada;
2. em caso de empate histórico, maior pico de funcionários.

O recorde permanece associado à empresa que efetivamente atingiu aquele nível.

---

## 14.4.3. Maior tempo ativo já alcançado

Registra o maior período contínuo de atividade já alcançado por uma conta segundo as regras do ranking **Maior tempo ativo**.

Uma sequência encerrada posteriormente continua registrada como recorde histórico caso tenha sido a maior já alcançada.

---

## 14.4.4. Presidente com maior percentual de votos

Este ranking substitui a interpretação de "maior aprovação" por uma métrica eleitoral objetiva: o maior percentual de votos obtido em uma eleição presidencial.

A classificação considera o percentual efetivamente registrado no resultado da eleição.

Exemplo:

| Presidente | Votos obtidos | Total de votos | Percentual |
|---|---:|---:|---:|
| A | 7.000 | 10.000 | 70% |
| B | 6.000 | 10.000 | 60% |
| C | 5.500 | 10.000 | 55% |

Neste exemplo, o recorde de maior percentual é 70%.

O histórico deve armazenar, além do percentual:

- presidente;
- eleição correspondente;
- quantidade de votos obtidos;
- total de votos contabilizados;
- percentual registrado;
- data da eleição.

Isso mantém o recorde auditável mesmo quando a quantidade total de eleitores mudar ao longo da história do servidor.

O ranking mede o **resultado daquela eleição específica**. Não representa aprovação contínua durante o mandato.

---

# 14.5. Armazenamento dos recordes

Para rankings históricos, não é necessário manter uma tabela com todos os estados antigos do ranking apenas para exibição.

O sistema pode manter diretamente o recorde atual de cada categoria, junto dos metadados necessários para auditoria.

Estrutura conceitual mínima:

```text
RankingHistorico
- categoria
- entidade_tipo
- entidade_id
- valor_recorde
- data_recorde
- metadados_do_recorde
```

Os metadados variam de acordo com a categoria.

Exemplos:

```text
Maior patrimônio
→ valor patrimonial registrado

Maior empresa
→ estrelas + pico de funcionários

Maior tempo ativo
→ início e fim da sequência recordista

Maior percentual presidencial
→ votos + total + percentual + eleição
```

A implementação não deve criar estruturas específicas para cada ranking quando uma estrutura histórica genérica puder armazenar o recorde com segurança.

---

# 14.6. Atualização dos rankings

Rankings ao vivo podem ser recalculados quando os dados que alimentam suas métricas forem alterados.

Não é necessário executar um processamento completo do servidor a cada acesso à página se o valor puder ser mantido de forma incremental ou calculado a partir de agregados existentes.

Para métricas temporais, o sistema deve possuir registros suficientes para remover da janela os eventos que ficaram fora do período.

Exemplo:

```text
Produção — 14 dias

Dia -13 → entra na janela
Dia -14 → entra na janela
Dia -15 → sai da janela
```

A janela deve ser definida de maneira consistente pelo servidor, evitando diferenças causadas pelo horário em que cada jogador abre a página.

---

# 14.7. Rankings e histórico de dados

Os rankings não devem apagar os eventos econômicos, políticos ou produtivos que os alimentam.

A retenção de dados segue as regras dos sistemas de origem.

Para rankings históricos, o objetivo é apenas manter o recorde necessário para exibição rápida, enquanto os dados de origem continuam disponíveis para auditoria e ferramentas administrativas conforme suas próprias regras.

---

# 14.8. Página de Rankings

A página pública de Rankings deve separar visualmente:

### Rankings ao vivo

Mostra a posição atual dos participantes e o valor que determina sua posição.

### Rankings históricos

Mostra o recorde já alcançado, quem o possui e, quando aplicável, quando o recorde foi estabelecido.

A interface deve deixar clara a diferença entre:

> **"está em primeiro agora"**

 e

> **"já alcançou o maior valor registrado"**.

---

# 14.9. Auditoria e integridade

Toda métrica deve ser derivada de dados reais do jogo e possuir uma origem identificável.

O sistema administrativo/Dev deve conseguir identificar:

- qual dado alimentou o ranking;
- período utilizado, quando houver;
- valor calculado;
- entidade que ocupou a posição;
- momento da atualização.

Isso é especialmente importante para rankings que dependem de janelas temporais e para o recorde eleitoral presidencial.

---

# 14.10. Escopo do Bot Test

### Implementar no Bot Test

- Maior patrimônio líquido;
- Maior empresa;
- Maior produção, últimos 14 dias;
- Melhor QoL pessoal;
- Maior empregador;
- Maior contribuinte, últimos 30 dias;
- Melhor escola/universidade;
- Maior organização;
- Conta mais antiga;
- Maior tempo ativo;
- Maior patrimônio líquido histórico;
- Maior empresa histórica;
- Maior tempo ativo histórico;
- Presidente com maior percentual de votos histórico.

### Fora do Bot Test

- Maior influência política, até existir métrica objetiva documentada.

---

# 14.11. Regras que não pertencem ao sistema de Rankings

O ranking não deve:

- conceder dinheiro;
- conceder energia;
- conceder bônus de produção;
- alterar QoL;
- alterar impostos;
- alterar chances eleitorais;
- criar reputação oculta;
- criar NPCs ou população artificial;
- criar uma pontuação genérica que substitua as métricas reais.

Rankings são somente uma camada de comparação e visualização dos resultados produzidos pelo restante do jogo.

---

# 14.12. Decisões consolidadas

1. A janela de **Maior produção** é de **14 dias**.
2. A janela de **Maior contribuinte** é de **30 dias**.
3. **Maior influência política** fica fora do Bot Test até existir métrica objetiva.
4. **Melhor escola/universidade** usa a qualidade atual da instituição.
5. **Conta mais antiga** mede tempo desde a criação da conta, independentemente de atividade contínua.
6. **Maior tempo ativo** mede uma sequência de atividade com intervalo entre ações válidas sempre inferior a **72 horas**.
7. O antigo conceito de **"Presidente com maior aprovação"** passa a ser **"Presidente com maior percentual de votos"**, usando o resultado efetivo da eleição presidencial.

---

# 14.13. Critério de conclusão

O documento é considerado pronto para implementação no Bot Test quando:

- as métricas ao vivo estiverem conectadas aos dados reais dos sistemas de origem;
- as janelas temporais estiverem sendo calculadas corretamente;
- os recordes históricos persistirem após a queda do valor atual;
- o ranking de tempo ativo respeitar o intervalo máximo de 72 horas;
- o ranking eleitoral utilizar o percentual efetivamente registrado na eleição;
- a página separar claramente rankings ao vivo de rankings históricos;
- o sistema administrativo conseguir verificar a origem dos valores apresentados.
