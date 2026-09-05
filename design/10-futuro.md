## 12. Histórico do mundo (crônica do servidor) 🆕

Registro cronológico e permanente dos eventos mais importantes do jogo,
numa página pública ("História de Nova Polis"). Cada entrada: data
(ano/mês do jogo), descrição curta, categoria (política/economia/
conflito/marco).

Dispara registro automático em: primeira eleição de cada cargo,
fundação da primeira empresa de cada tipo, primeira construção
institucional, mudanças de lei com trade-off grande, mobilização de
milícia (seção 19), renúncia/deposição de presidente, falência de
empresa grande (acima de X★), eventos aleatórios (seção 13).

Tecnicamente barato — um model `EventoHistorico` (data, categoria,
descrição), preenchido automaticamente pelos outros sistemas quando
disparam — mas o valor de jogo é enorme — dá identidade única a cada
servidor.

---


## 13. Sistema de eventos aleatórios 🆕

Princípio central, direto da sua ideia: **evento nunca aplica um
modificador solto tipo "+20%"** — sempre altera uma condição real que
já existe no sistema, e deixa a cadeia de causa-efeito que a gente já
desenhou (produção → estoque → preço → custo → QoL) reagir sozinha.
Evento não precisa de lógica de efeito própria, só precisa mexer nos
números que os sistemas já leem.

| Evento | O que altera de verdade | Efeito em cascata natural |
|---|---|---|
| Acidente em mina | Zera/reduz o estoque de uma Matriz de Mineração específica | Matéria-prima escassa → Industrial não fabrica → preço sobe |
| Desastre natural | Reduz QoL de um bairro/cidade direto, pode destruir % do estoque das empresas de lá | QoL baixa → menos eficiência de trabalho/skill (seção 1.2) → governo precisa agir |
| Pandemia | Sobe a chance de decaimento de Saúde (seção 5.3) numa região | Mais gente internada → menos gente trabalhando → produção cai |
| Descoberta de recurso | Abre uma Matriz "vaga" numa zona Rural nova, ou aumenta o teto de produção de uma existente | Mais oferta → preço cai |
| Quebra de empresa importante | Força falência de uma empresa grande (acima de X★) | Funcionários desempregados, estoque some do mercado |
| Boom econômico | Aumenta temporariamente a demanda numa região | Preço sobe organicamente, sem mexer no preço base |
| Escassez | Reduz o estoque global de um Produto específico | Preço sobe, empresas competem pelo pouco que sobra |
| Migração | Muda a população de NPC (seção 7.2) de uma cidade de uma vez | Muda a faixa de população e a QoL da tabela (seção 7) |
| Crise bancária | Reduz o rating de solvência de todas as Financeiras de uma vez (seção 2.8) | Pode disparar intervenção do governo em cascata |

⚠️ Isso é claramente conteúdo de depois que a base estiver rodando —
marcar como fase tardia no roadmap, não prioridade de curto prazo.

---


## 14. Rankings 🆕

Dois tipos: **ao vivo** (situação atual, muda a qualquer momento) e
**histórico** (recorde já alcançado, nunca é apagado mesmo que a
pessoa perca a posição depois).

**Ao vivo:** maior patrimônio, maior empresa (por estrela, funcionários
como desempate), maior produção, melhor QoL pessoal, maior influência
política, maior empregador, maior contribuinte (imposto pago), melhor
universidade/escola, maior organização (maior milícia, seção 19),
**tempo de conta ativa** ✅ (era "expectativa de vida", renomeado — mede
há quanto tempo o jogador tem a mesma conta ativa, não morte de
personagem).

**Histórico:** maior patrimônio já alcançado, maior empresa da
história, presidente com maior aprovação.

⚠️ **Pendência:** "maior expectativa de vida" não tem um equivalente
literal claro hoje, já que não existe morte de personagem no design —
só internação (seção 5.3) e prisão (seções 6.3/8). Você quis dizer
tempo de conta ativa sem interrupção, ou tinha outra métrica em mente?

---


## 15. Jornal / feed de notícias 🆕

Feed gerado automaticamente pelos próprios sistemas — sem geração de
texto livre por IA, só templates preenchidos com dado real:

- Produto varia X% de preço em 24h → "Mercado do {produto} registra {alta/queda} de {X}%"
- Nova zona aberta → "Prefeitura de {cidade} anuncia nova zona {tipo}"
- Empresa grande falindo → "{Empresa} entra em falência"
- Lei aprovada → "{Cargo} aprova {nome da lei}"
- Mobilização de milícia → "{Milícia} convoca nova mobilização"
- QoL nacional caindo 3 meses seguidos → "QoL nacional cai pelo terceiro mês consecutivo"

Reaproveita o mesmo `EventoHistorico` da seção 12 — a diferença é só de
apresentação: histórico é a página completa e permanente, jornal é o
feed recente com cara de manchete. Podem ser a mesma tabela, com um
campo `eh_manchete`.

---


## 16. Empresas com múltiplos donos (sociedade / ações) 🆕 — mudança estrutural grande

Hoje `Empresa.dono` é um jogador único (FK direta). Pra sociedade,
precisa virar uma relação N-pra-N com percentual:

```
Empresa
  ↳ Participacao (empresa, jogador, percentual)
```

- Fundador começa com 100%, pode vender parte da participação pra
  outro jogador (conecta com Contratos, seção 18)
- Quem decide o quê: dono majoritário (>50%) mantém controle sozinho,
  igual hoje. Sem maioria clara, precisa de votação entre os sócios
  proporcional à participação — mesma lógica de aprovação de leis, só
  que dentro da empresa
- **É o pré-requisito estrutural da Bolsa de Valores** (seção 2.8): uma
  ação nada mais é que um pedaço pequeno e padronizado de
  `Participacao`, negociado livremente. Faz sentido reaproveitar o
  mesmo modelo em vez de criar dois sistemas parecidos.

⚠️ Mudança estrutural grande — todo o código atual assume dono único
(upar, criar cargo, receber pagamento de venda). Vale tratar como fase
própria, não ajuste pontual.

---


## 17. Transparência de mercado 🆕

Mercado (e a página de cada Produto) passam a mostrar estatística
agregada, não só "compre aqui":

```
Café
Preço médio: R$ 42       Menor preço: R$ 31       Maior preço: R$ 68
Estoque total: 14.200     Produção diária: 11.800   Consumo diário: 13.500
Tendência: ⬆️ +8% (últimos 7 dias)
```

E a página da empresa ganha um resumo de causa-efeito nos custos:

> Seus custos aumentaram 14% nos últimos 7 dias. Principal causa: alta de 21% no preço do Aço.

Tecnicamente é "só" leitura agregada do que já existe — mas expõe uma
lacuna real: hoje o preço de venda é sempre o `preco_base` fixo do
catálogo (a seção 2.12 já previa isso mudando por qualidade). Pra
"tendência" e "preço médio" fazerem sentido, precisa existir um
histórico de preço por transação de verdade, não só o preço "oficial".

---


## 18. Contratos entre jogadores 🆕

Diferente de compra avulsa (que já existe): contrato é um **acordo
recorrente ou de prazo**, registrado no sistema, entre duas partes:

| Tipo | Exemplo |
|---|---|
| Fornecimento | "Fornecer 10.000 unidades de Aço por mês, a R$ 12/unidade" |
| Trabalho | Como um Cargo, mas negociado fora dos termos padrão (ex: salário combinado à parte) |
| Empréstimo entre jogadores | Fora da Financeira — direto entre duas pessoas, prazo e juros combinados |
| Aluguel | De imóvel, entre dono e morador/empresa |
| Governamental | Generaliza o leilão de contrato de construção (seção 11.4) pra outros tipos de contrato com o governo |

Precisa de aceite das duas partes, prazo/recorrência, e uma consequência
real pra quebra de contrato (multa combinada, ou reputação — que ainda
não existe como sistema, faria sentido nascer junto com isso). Sem
nenhum enforcement, contrato é só um "combinado de boca" que já dá pra
fazer sem sistema nenhum — o valor está em ter consequência de verdade.

---


## 19. Militares e Milícias 🆕 — sistema novo e grande

Primeiro sistema do jogo com conflito direto entre jogadores — tudo o
resto até aqui é econômico/político sem "combate". Esse é o design com
mais peça móvel em aberto de todos até agora.

### 19.1 Exército

- Governo contrata jogadores como militares — funcionário público,
  análogo a um Cargo, mas com exclusividade: **militar não pode ter
  outro emprego nem ser dono de empresa**
- Treinamento gasta energia, sobe Físico; cargos de comando (Capitão,
  General, Marechal) também exigem Inteligência
- Nível de investimento do governo (orçamento, seção 9) afeta a
  eficiência do treinamento

### 19.2 Milícias

- Múltiplas milícias independentes podem existir ao mesmo tempo
- Jogador (não-militar) se filia à milícia alinhada com seus interesses políticos
- **Membro ≠ mobilizado**: liderança convoca mobilizações específicas;
  só uma parte dos membros participa de cada confronto
- Líder da milícia vencedora assume a Presidência — condição
  **propositalmente muito difícil** de acontecer

### 19.3 Força e prontidão

| Lado | Força depende de |
|---|---|
| Exército | Quantidade de militares, skill média, treinamento/investimento, prontidão atual |
| Milícia | Quantidade de membros mobilizados, skill média, e um multiplicador ligado à QoL global — **quanto menor a QoL nacional, maior a capacidade de mobilização das milícias** |

Militar é individualmente mais eficiente, mas milícia muito numerosa
pode superar Exército profissional só pelo número. Prontidão do
Exército desgasta com confronto/mobilização, recupera com
investimento/treino/descanso.

### 19.4 Regras do confronto

- **Vitória por atrito**: milícia não precisa ganhar um confronto —
  perder repetidamente já desgasta o Exército financeira e
  operacionalmente até a repressão deixar de valer a pena pro governo
- **Derrota da milícia não é punição pesada**: só fracassa aquela
  mobilização específica, pode tentar de novo
- **Custo da repressão**: manter o Exército mobilizado gera custo pro
  orçamento — campanha prolongada pode ficar insustentável
- **Renúncia pacífica**: presidente pode sair voluntariamente antes de
  uma derrota total, evitando queda violenta
- **Vitória da milícia**: líder assume a Presidência e pode indicar
  novos membros do STF

✅ **Cooldown entre Exército e Milícia** (regra sua, confirmada): quem
sai de uma milícia só pode entrar no Exército depois de **3 meses**.
Quem sai do Exército só pode entrar numa milícia depois de **3 meses**
também. Evita troca oportunista de lado no meio de um conflito.

✅ **Trava constitucional sobrevive a uma tomada de poder** — confirmado:
mesmo com o líder da milícia assumindo a Presidência, as garantias de
moradia/educação (seção 11.6) continuam valendo. O novo presidente
herda a mesma trava, não começa "zerado".

🆕 **Propostas pro resto (ainda sem sua confirmação):**

- **Quantidade de milícias**: sem mínimo nem máximo teórico — qualquer
  jogador pode fundar uma. Proponho só um piso de **5 membros** pra uma
  milícia ser "oficial" (aparecer no ranking, poder mobilizar) — abaixo
  disso é só um grupo informal sem efeito mecânico.
- **Fórmula de força:**
  ```
  Força do Exército = nº de militares × skill Físico médio × prontidão (0 a 1)
  Força da Milícia  = nº de membros mobilizados × skill Físico médio × multiplicador de QoL nacional
  ```
  onde o multiplicador de QoL só ativa abaixo do ideal: `multiplicador = 1 + (1 − QoL_nacional)` se QoL < 1, senão `1`. Isso implementa direto a regra que você já tinha dado (QoL baixa = milícia mais forte).
- **Exército após deposição**: proponho que o Exército seja **dissolvido**
  — todo militar vira civil livre pra escolher novo emprego, e o novo
  presidente (ex-líder de milícia) começa um Exército do zero. Isso
  evita que vencer uma vez vire vantagem militar permanente, reforçando
  o "deve ser muito difícil de alcançar" que você já tinha pedido.
- A trava constitucional (seção 11.6, moradia/educação) continua valendo depois de uma tomada de poder, ou é reiniciada?

---


## 21. Bots para testes de beta 🆕 (metodologia de teste, não mecânica de jogo)

Não é conteúdo do jogo final — é ferramenta de validação antes do
lançamento:

- Criar usuários-bot progressivamente (proposta: 1 por hora), jogando
  sob as **mesmas regras** dos jogadores reais (sem trapacear limite
  de energia etc)
- Comportamento simples (regras básicas tipo "se energia > 50%,
  trabalha; se dinheiro > X, tenta abrir empresa"), não precisa de IA
  sofisticada
- Registrar o comportamento pra achar problema estrutural antes de
  gente de verdade jogar: gargalo de produção, concentração de
  emprego, empresa quebrando em cadeia, falta de produto, distribuição
  de riqueza anormal

Isso é plano de teste, não roadmap de feature — vale um `TESTING.md`
próprio quando chegar perto do lançamento, não uma fase no roadmap
principal.

---

