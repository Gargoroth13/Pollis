## 22. Implicações técnicas — o que precisa ser refeito no código

Pra você ter clareza do tamanho do refactor antes da gente decidir por
onde começar:

1. ✅ **Sistema de skills** — feito na Fase 1: trocado as 8
   `CategoriaDeHabilidade` por 3 stats fixos (Inteligência/Físico/Carisma),
   usando `TextChoices` em vez de tabela (são fixas, não precisam mais
   de catálogo editável).
2. ✅ **Classificação de empresa** — feito na Fase 1: Matriz tem
   `terreno` (Agropecuária/Extrativismo/Mineração), Industrial tem
   `tipo_industria` (Produção/Alimentícia/Bens de consumo/Tecnológica),
   Serviços tem `especializacao_servico` (Transporte/Publicidade/Lazer/Financeira).
   `Empresa.clean()` garante que só o campo certo pro tipo escolhido é
   preenchido. `setor` como conceito compartilhado com skill não existe mais.
3. **Catálogo de produtos**: Fase 1 trocou os produtos placeholder por
   um recorte pequeno mas real (4 matérias-primas, 3 manufaturados,
   já usando terreno/tipo_industria corretos). Expandir pro catálogo
   completo (~40 itens) fica pra Fase 2.
4. **Produção via funcionário**: `produzir`/`fabricar` deixam de ser
   ação exclusiva do dono; viram progresso acumulado por cliques de
   "trabalhar" de qualquer funcionário.
5. **Inventário do jogador**: model novo, do zero.
6. **QoL pessoal, Saúde, Nutrição**: 3 barras novas no `Perfil`, com
   decaimento/regeneração próprios, além da energia que já existe.
7. **Salário com teto por skill**: validação nova ao definir/pagar salário.
8. **Consumo operacional** (EPIs, uniformes, materiais escolares/hospitalares): mecânica nova de "empresa/instituição gasta estoque pra funcionar".
9. ✅ **Diminishing returns de skill** — feito na Fase 1:
   `HabilidadeDoJogador.ganhar_xp()` já aplica o multiplicador por
   faixa de 100 pontos, testado e confirmado matematicamente correto.
10. **Especialização de funcionário**: model novo ligando jogador + produto + nível de especialização.
11. **Qualidade afetando preço/efeito**: os cálculos de compra (`comprar_de_empresa`, `comprar_do_mercado`) passam a considerar a estrela de quem produziu, não só `preco_base` fixo.
12. **Financeira completa**: reserva obrigatória, rating de solvência, intervenção do governo, juros compostos, limite de crédito calculado — é praticamente um app novo por si só.
13. **Orçamento público**: pré-requisito pra trade-offs de lei terem efeito real (déficit/superávit mensurável).
14. **População dinâmica com NPCs**: sistema de simulação separado, migração de jogadores + IA leve de NPC.
15. **Estrela mínima em toda receita**: `Receita` precisa do campo `estrela_minima` — não é caso especial do Carro, é regra geral de todo o catálogo (1★ a 5★, valores já definidos na seção 2.3).
16. **Compra Industrial→Industrial**: `REGRAS_DE_COMPRA` precisa de uma entrada nova pra Industrial comprar manufaturado de outra Industrial (hoje só existe Industrial comprando de Matriz).
17. **Limite de estoque por funcionário**: Matriz, Industrial e agora Varejo têm capacidade de produzir/comprar proporcional a funcionários ativos — muda a lógica de `produzir`/`fabricar`/`comprar_de_empresa` de "ação isolada do dono" pra "capacidade agregada dos funcionários".
18. **Leis paramétricas**: model `Lei` (nome, escopo, parâmetro atual, quem propôs, status de aprovação) + o motor que aplica o efeito de cada uma nos cálculos existentes (impostos entram em `comprar_de_empresa`/pagamento de salário, teto de posse em `criar_empresa`, etc — cada lei "pluga" num ponto diferente do código já existente).
19. **Leis constitucionais protegidas**: piso mínimo travado + verificação automática de indicador (% sem moradia/escola) disparando elegibilidade de plebiscito.
20. **Campanhas temporárias**: model `Campanha` (tipo, território afetado, buff, data de início/fim), + um job agendado (mesmo padrão dos outros prazos, seção "arquitetura de worker") que desativa a campanha sozinha quando a duração acaba, e os pontos onde o buff precisa ser lido (produção de Matriz/Industrial, qualidade de escola, tempo de internação) passam a somar o bônus de campanha ativa, se houver.
21. **`EventoHistorico`**: model único usado tanto pra Histórico (seção 12) quanto pro Jornal (seção 15) — outros sistemas (leis, falências, milícia) chamam um helper pra registrar evento, em vez de cada view escrever isso na mão.
22. **Eventos aleatórios**: um worker agendado (mesmo padrão de outros jobs) que sorteia e dispara eventos da tabela da seção 13, mexendo direto nos campos que os sistemas já leem (estoque, QoL, rating de solvência) — sem lógica de efeito própria.
23. **Rankings**: queries agregadas (ordenação por patrimônio, produção etc) + uma tabela separada de recordes históricos que só atualiza quando bate um novo máximo, nunca reduz.
24. **Sociedade/ações**: `Participacao` (empresa, jogador, percentual) substitui `Empresa.dono` como FK direta — reescreve toda lógica que hoje assume dono único (upar, criar cargo, receber pagamento).
25. **Histórico de preço por transação**: hoje só existe `preco_base` fixo por produto — precisa de um registro por transação de compra/venda pra "preço médio/tendência" (seção 17) fazerem sentido.
26. **Contratos**: model `Contrato` (tipo, partes, termos, prazo, status) + verificação periódica de cumprimento/quebra.
27. **Militares e Milícias**: sistema novo do zero — `Militar`, `Milicia`, `Mobilizacao`, fórmula de força de combate, e o fluxo de deposição/vitória que muda quem ocupa a Presidência.
28. **Fórmulas com detalhamento**: convenção de código pra toda fórmula composta (QoL, custo, força militar) retornar o breakdown aditivo junto com o total, não só o número final (seção 20) — precisa virar padrão desde as primeiras fórmulas novas escritas, não só nas telas.

**Fase 1 concluída e testada** (itens 1, 2 e 9). Itens 3 (catálogo
completo) e 16 (compra Industrial→Industrial) formam a Fase 2 natural,
já que um depende do outro (o Carro só faz sentido com os dois prontos).

---

