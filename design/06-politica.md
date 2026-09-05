## 7. Política e QoL — efeito da população da cidade 🤝

| Faixa de população | Efeito na QoL |
|---|---|
| Baixa | 0 |
| Ideal | +0.2 |
| Acima | −0.1 |
| Lotada | −0.2 |

(você já avisou que os valores podem mudar pra ter mais impacto — não é definitivo)

### 7.1 Trade-offs explícitos nas decisões políticas 🆕 (novo)

Toda lei com impacto econômico precisa ter um efeito colateral visível,
não só o benefício — senão vira escolha óbvia sem custo político real.
Exemplos que você deu:

- **Aumentar salário mínimo** → sobe QoL dos trabalhadores, mas aumenta
  o custo das empresas e pode gerar desemprego
- **Subsídio agrícola** → melhora o preço dos alimentos pro consumidor,
  mas gera déficit no orçamento público

Isso implica que o sistema de leis (ainda não implementado) precisa
calcular e mostrar os dois lados de cada proposta antes da votação, não
só o efeito pretendido. E implica também que precisa existir um
**orçamento público** de verdade (receita de impostos vs gastos), pra
"gerar déficit" ser uma consequência mensurável, não só flavor text.

### 7.2 População dinâmica (jogadores + NPCs) 🆕 (novo, versão enxuta pra não travar tudo)

Migração de jogadores + IA completa de NPC reagindo à economia é grande
demais pra entrar de uma vez. Proposta de versão inicial, simples o
suficiente pra implementar junto com o resto:

- **NPCs de preenchimento**: população de NPC de um bairro = capacidade
  total dos imóveis residenciais construídos ali **menos** os jogadores
  que já moram lá. Não fazem nada, não têm IA, só contam pra calcular a
  faixa de população (Baixa/Ideal/Acima/Lotada) da seção 7 — assim a
  política já tem efeito mensurável desde o início, sem precisar de
  simulação de verdade
- **Migração de jogador**: nova ação "mudar de bairro/cidade" — paga
  uma taxa + 1 dia parado (mesmo custo de Viajar), transfere o `Perfil`
  pro novo bairro

NPC "reagindo de verdade" às políticas (comprando no Mercado, votando,
etc) fica pra uma fase bem mais adiante — colocar isso agora atrasaria
todo o resto sem necessidade.

---


## 8. Cargos políticos — números completos 🆕

### 8.1 Executivo

| Cargo | Quantos |
|---|---|
| Presidente | 1 (nacional) |
| Governador | 1 por estado |
| Prefeito | 1 por cidade |

### 8.2 Legislativo

| Cargo | Quantos |
|---|---|
| Deputados (Câmara) | 1 a cada 500 jogadores residentes no país, mínimo 5 no total |

### 8.3 Judiciário e fiscalização

| Cargo | Quantos |
|---|---|
| Ministros (STF) | 7, fixo, nacional |
| Juízes (tribunais locais/"ministros menores") | 1 a cada 200 jogadores residentes na cidade, mínimo 1 por cidade |
| Fiscais | 1 a cada 300 jogadores residentes na cidade, mínimo 1 por cidade |

⚠️ "População" aqui hoje só conta jogador de verdade (não temos NPC
ainda — ver seção 7.2/7.3). Quando NPC existir, essas contas passam a
usar população total (jogador + NPC) automaticamente, sem precisar
redesenhar a regra.

---


## 9. Orçamento público 🆕 (sistema novo, pré-requisito pros trade-offs de lei)

Cada nível de governo (cidade, estado, país) tem seu próprio orçamento:

- **Receita**: impostos — % sobre transações do Mercado, % sobre
  salários pagos, % sobre lucro de empresa. As taxas exatas são leis
  paramétricas (ligou com o sistema de leis que já esboçamos
  antes — o político define o %, dentro de limites)
- **Gastos**: infraestrutura (escolas, hospitais, contratos de
  construção), subsídios (ex: agrícola, do exemplo da seção 7.1)
- **Déficit**: se os gastos aprovados passarem da receita acumulada, o
  orçamento fica negativo. Proposta: um orçamento muito tempo no
  vermelho aumenta a insatisfação da população (baixa QoL geral da
  cidade/estado), criando pressão política real — não só um número
  abstrato

⚠️ Isso é pré-requisito técnico pra qualquer trade-off de lei ter efeito
mensurável (seção 7.1). Sem orçamento, "gera déficit público" é só
flavor text.

---

---

