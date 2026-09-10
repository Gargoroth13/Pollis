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