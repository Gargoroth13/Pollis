# 12 — Histórico do Mundo

**Status: FINAL — BOT TEST**

## 12.0. Objetivo

O sistema de Histórico do Mundo funciona como uma mistura de uma **fonte de notícias do servidor** com uma **crônica permanente dos acontecimentos importantes de Nova Polis**.

A interface deve dar ao jogador a sensação de que o mundo continua acontecendo mesmo quando ele não está realizando uma ação diretamente.

As notícias são geradas automaticamente pelos sistemas do jogo e escritas em formato curto, semelhante a uma manchete e uma pequena nota jornalística.

Exemplos:

> **Preço médio do aço sobe 8%**  
> O preço médio nacional do aço aumentou 8% nos últimos 7 dias.

> **Empresa Atlas declara falência!**  
> A empresa Industrial Atlas, de 5★, encerrou suas operações após não conseguir manter suas obrigações financeiras.

> **Novo presidente eleito**  
> João foi eleito Presidente com 53,4% dos votos.

O sistema não deve funcionar como um log técnico. A informação apresentada ao jogador precisa ser compreensível, relevante e contextualizada.

---

# 12.1. Página pública

A interface principal deve ser apresentada como uma página de **Notícias de Nova Polis**.

A página exibe as notícias mais recentes primeiro.

Filtros iniciais:

- Todas
- Política
- Economia
- Conflito
- Sociedade
- Marco

A notícia possui, no mínimo:

| Campo | Conteúdo |
|---|---|
| Data/hora | Quando o acontecimento ocorreu |
| Categoria | Categoria da notícia |
| Manchete | Título curto gerado pelo sistema |
| Texto | Pequeno resumo do acontecimento |
| Referência | Objeto relacionado, quando existir |

A referência pode levar o jogador diretamente para a página correspondente, quando houver uma página para aquele objeto.

Exemplos:

- notícia de empresa → página da empresa;
- notícia de produto → página do Produto;
- notícia eleitoral → página da eleição/cargo;
- notícia de lei → página da lei;
- notícia de conflito → página da ação correspondente.

---

# 12.2. Notícias automáticas

As notícias são disparadas automaticamente pelos sistemas responsáveis pelo acontecimento.

O `12` não deve possuir lógica própria para descobrir acontecimentos em outros sistemas. Cada sistema registra ou solicita a criação da notícia quando um evento relevante ocorre.

Exemplos de fontes:

- `06 — Política` → eleições, leis e mudanças de governo;
- `07 — Leis` → aprovação, veto e entrada em vigor de leis relevantes;
- `09 — Orçamento Público` → acontecimentos fiscais relevantes;
- `02 — Empresas` → fundações e falências relevantes;
- `17 — Transparência de Mercado` → mudanças relevantes em preços e indicadores;
- `19 — Militar` → mobilizações e conflitos;
- `13 — Eventos` → eventos aleatórios marcados como noticiáveis.

---

# 12.3. Linguagem das notícias

A notícia deve ser escrita automaticamente a partir de dados estruturados do acontecimento.

O sistema deve utilizar modelos de texto com variações suficientes para não produzir sempre exatamente a mesma frase.

A estrutura básica é:

```text
manchete + contexto curto + dados relevantes
```

Exemplo econômico:

> **Preço médio do aço sobe 8%**  
> O preço médio nacional do aço aumentou 8% nos últimos 7 dias.

Exemplo político:

> **Novo Presidente eleito**  
> João venceu a eleição presidencial com 53,4% dos votos.

Exemplo empresarial:

> **Empresa Atlas declara falência!**  
> A Industrial Atlas, de 5★, encerrou suas operações após entrar em processo de falência.

A descrição deve informar o fato sem inventar motivos que o sistema não conhece.

---

# 12.4. Economia

Notícias econômicas podem ser geradas a partir dos indicadores já calculados pelo sistema de transparência de mercado.

O sistema pode noticiar alterações relevantes em:

- preço médio;
- estoque disponível;
- produção;
- consumo;
- volume negociado;
- outras métricas econômicas futuras marcadas como noticiáveis.

### Tendência de preço

Uma das notícias padrão é a mudança do preço médio de um Produto nos últimos 7 dias.

Exemplo:

> **Preço médio do aço sobe 8%**

A comparação utiliza o mesmo cálculo de tendência definido em `17 — Transparência de Mercado`.

Apenas alterações que ultrapassem um **limiar mínimo de relevância** devem gerar notícia, para evitar que pequenas oscilações produzam spam.

O valor desse limiar é parâmetro de balanceamento do sistema.

---

# 12.5. Empresas

A fundação ou expansão de empresas pode gerar notícias quando representar um marco ou acontecimento relevante.

A **falência de empresas de 5★ ou mais** sempre pode gerar notícia.

Exemplo:

> **Empresa Atlas declara falência!**

Falências de empresas abaixo de 5★ não geram notícia global por padrão.

A primeira empresa de cada tipo também pode gerar uma notícia de marco.

Exemplo:

> **Nova Polis inaugura sua primeira empresa Industrial**

A primeira ocorrência de cada tipo é registrada uma única vez como marco do servidor.

---

# 12.6. Política

O sistema deve gerar notícias para acontecimentos políticos relevantes.

Exemplos:

> **Novo Prefeito eleito em Nova Polis**  
> João venceu a eleição com 58,2% dos votos.

> **Câmara aprova aumento do imposto sobre vendas**  
> A proposta foi aprovada pela maioria absoluta dos Deputados.

> **Presidente veta nova lei de salário mínimo**

> **Câmara derruba veto presidencial**

> **Novo Presidente assume o cargo após deposição**

Resultados eleitorais devem utilizar a porcentagem real de votos obtida pelo vencedor.

Mudanças legislativas devem receber notícia quando o próprio catálogo da lei indicar que aquela alteração deve ser tratada como relevante para a imprensa do servidor.

O sistema não deve tentar decidir subjetivamente se uma lei foi "importante". Essa classificação deve vir do próprio sistema de leis/catálogo.

---

# 12.7. Conflitos e Milícias

O sistema de notícias deve registrar acontecimentos relevantes de conflitos sem transformar cada movimentação individual em notícia.

Devem ser noticiados, quando aplicável:

- início de uma ação de conflito relevante;
- resultado da ação;
- deposição presidencial;
- outros acontecimentos extraordinários definidos por `19 — Militar`.

Exemplos:

> **Milícia Aurora inicia ação contra o governo**

> **Milícia Aurora vence confronto na capital**

> **Presidente deposto após ação da Milícia Aurora**

Movimentação individual de membros, deslocamentos internos e ações técnicas de mobilização não devem gerar notícias por padrão.

---

# 12.8. Marcos históricos

Alguns acontecimentos são registrados como marcos únicos do servidor.

Exemplos iniciais:

- primeira eleição presidencial;
- primeira eleição para Governador;
- primeira eleição para Prefeito;
- primeira eleição da Câmara;
- primeira empresa de cada tipo;
- primeira construção institucional relevante;
- outros marcos explicitamente definidos pelos sistemas.

Cada marco desse tipo é registrado apenas uma vez.

A notícia continua disponível no arquivo histórico mesmo anos depois do acontecimento.

---

# 12.9. Eventos aleatórios

`13 — Eventos` pode gerar acontecimentos aleatórios.

Um evento aleatório marcado como **noticiável** gera automaticamente uma notícia no `12`.

O `12` não precisa conhecer as regras do evento aleatório. Ele recebe apenas os dados necessários para publicar a notícia.

---

# 12.10. Permanência e arquivo histórico

Cada notícia publicada é permanente no histórico do servidor.

A página principal pode funcionar como um feed das notícias mais recentes, mas notícias antigas continuam acessíveis em um arquivo histórico.

O objetivo é permitir que um servidor desenvolvido por meses ou anos possua uma narrativa própria.

Exemplo de arquivo:

> **Ano 1, Mês 1** — Primeira eleição presidencial concluída.
>
> **Ano 1, Mês 3** — Primeira Industrial fundada.
>
> **Ano 2, Mês 4** — Preço do aço sobe 12% em uma semana.
>
> **Ano 3, Mês 2** — Empresa Atlas declara falência.
>
> **Ano 3, Mês 5** — Milícia Aurora depõe o Presidente.

---

# 12.11. Histórico técnico e informação pública

O sistema mantém os dados necessários para auditoria e geração das notícias.

Entretanto, o jogador não precisa receber o histórico técnico bruto que originou cada notícia.

Por exemplo, uma notícia de mercado pode mostrar:

> **Preço médio do aço sobe 8%**

O servidor pode manter internamente os registros e dados usados para chegar a essa conclusão sem exibir cada transação individual na página de notícias.

O histórico bruto continua disponível para Dev/Admin, debugging e futuras ferramentas de análise.

---

# 12.12. Evitando spam

O feed deve priorizar acontecimentos que tenham relevância para o mundo ou para o jogador.

Regras iniciais:

- pequenas variações de preço não geram notícia;
- cada marco inicial é publicado uma única vez;
- falências abaixo de 5★ não geram notícia global por padrão;
- movimentações técnicas internas não viram notícia;
- notícias repetitivas sobre o mesmo indicador devem possuir um intervalo mínimo entre publicações;
- sistemas podem enviar notícias com prioridade diferente.

Os limiares e intervalos devem permanecer parametrizados para balanceamento após o Bot Test.

---

# 12.13. Prioridade das notícias

As notícias podem possuir uma prioridade interna para ordenar acontecimentos simultâneos.

Sugestão inicial:

1. mudança extraordinária de governo / deposição;
2. grandes conflitos;
3. eleições;
4. falências de empresas 5★+;
5. grandes acontecimentos econômicos;
6. marcos históricos;
7. acontecimentos econômicos menores.

A prioridade não precisa ser mostrada ao jogador.

---

# 12.14. Integrações

### `02 — Empresas`

Envia fundações relevantes e falências de empresas 5★+.

### `06 — Política`

Envia resultados eleitorais, mudanças de governo e acontecimentos políticos relevantes.

### `07 — Leis`

Envia notícias de aprovação, veto, derrubada de veto e entrada em vigor quando a lei estiver marcada como noticiável.

### `09 — Orçamento Público`

Pode gerar notícias para acontecimentos fiscais extraordinários definidos pelo sistema.

### `13 — Eventos`

Pode marcar eventos aleatórios como noticiáveis.

### `17 — Transparência de Mercado`

Fornece os indicadores agregados utilizados pelas notícias econômicas.

### `19 — Militar`

Envia início e resultado de conflitos relevantes e acontecimentos extraordinários relacionados a Milícias e Exército.

---

# 12.15. Bot Test

O Bot Test deve verificar, no mínimo:

### Notícias econômicas

Verificar geração de notícia quando o preço de um Produto ultrapassa o limiar de relevância.

### Falência

Verificar notícia para empresa de 5★ e ausência de notícia global para empresa abaixo desse limite.

### Eleição

Verificar notícia com nome do vencedor e porcentagem correta de votos.

### Leis

Verificar notícias de aprovação, veto, derrubada de veto e entrada em vigor quando aplicável.

### Conflito

Verificar notícia de início e resultado de ação relevante sem gerar spam de movimentações individuais.

### Marcos

Verificar que a primeira ocorrência de cada marco é registrada uma única vez.

### Histórico

Verificar que notícias antigas continuam disponíveis depois que novas notícias são publicadas.

### Performance

Verificar que a página utiliza dados agregados e não precisa percorrer o histórico bruto completo de transações para montar o feed ou gráficos.

---

# 12.16. Princípios de design

1. **Mundo vivo:** o jogador deve perceber que acontecimentos continuam ocorrendo fora das próprias ações.
2. **Informação útil:** notícias devem revelar mudanças relevantes, não gerar ruído.
3. **Narrativa emergente:** cada servidor deve construir sua própria história a partir das ações dos jogadores.
4. **Automação:** outros sistemas geram os acontecimentos; o `12` apenas transforma esses acontecimentos em notícias.
5. **Permanência:** acontecimentos importantes não desaparecem da história do servidor.
6. **Clareza:** o texto deve parecer uma notícia curta, não um log técnico.
7. **Escalabilidade:** a interface pública utiliza dados agregados sempre que possível.
