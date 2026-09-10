# Development Task Queue

Fila oficial de desenvolvimento do Polis.
Estado de referencia: commit 72b008c (2026-09-10).

Regras:
- Uma task em Current por vez. So ela pode receber codigo.
- Um agente implementa a Current. Outro agente pode revisar, nao implementar em paralelo.
- Task pequena, testavel, um commit. Descobriu trabalho extra: entra na fila, nao no commit atual.
- Numeros nao mudam depois de atribuidos. Concluida sai de Current e ganha Status: DONE (nao apagar o id).

Esta ordem NAO e a lista antiga do TASK.md (custo -> Dono -> producao -> especializacao).
O Tech Lead inseriu caixa da empresa + salario honesto ANTES do cargo Dono, porque hoje o salario e dinheiro impresso no Perfil e a empresa nao tem tesouraria.

---

## Current

- Task 001 — Custo de fundacao por tipo
  Status: IN PROGRESS
  Detalhe: TASK.md
  Por que: fundar e trivial; o design quer objetivo de medio/fim de jogo.
  Escopo: CUSTO_DE_FUNDACAO_POR_TIPO + custo_de_fundacao() em empresas/models.py; validar saldo e descontar em criar_empresa; mostrar custo no template se for simples; smoke test via Django test Client.
  Fora: cargo Dono, producao, especializacao, diploma (Escola nao existe), caixa da empresa.
  Depende de: nada.

---

## Next

Nao iniciar enquanto 001 nao estiver commitada.

### A. Economia da empresa deixar de imprimir dinheiro

Hoje Empresa nao tem caixa (so financeira.DadosFinanceiros.caixa). trabalhar_no_emprego faz perfil.dinheiro += cargo.salario sem debitar ninguem. Upar e (em breve) fundar saem do bolso pessoal. Sem tesouraria, teto salarial e cargo Dono so aceleram o exploit.

- Task 002 — Campo caixa em Empresa + capitalizar/sacar
  Status: TODO
  Escopo: Empresa.caixa (Decimal, default 0) + migration; dono deposita/saca entre perfil.dinheiro e empresa.caixa; nao misturar com DadosFinanceiros.caixa (esse continua sendo reserva de depositos).
  Fora: mudar quem paga salario ou compra B2B.
  Depende de: 001 (pra nao conflitar em criar_empresa).

- Task 003 — Compra entre empresas e upar usam empresa.caixa
  Status: TODO
  Escopo: comprar_de_empresa debita caixa da compradora e credita caixa da vendedora; upar debita caixa (nao mais so o bolso do dono), ou falha com mensagem clara.
  Depende de: 002.

- Task 004 — Venda no Mercado credita empresa.caixa
  Status: TODO
  Escopo: comprar_do_mercado continua debitando o comprador pessoa fisica; o valor vai pra caixa da empresa vendedora, nao pro perfil do dono.
  Depende de: 002.

- Task 005 — Salario sai da caixa da empresa
  Status: TODO
  Escopo: trabalhar_no_emprego so paga se empresa.caixa >= salario; debita caixa, credita funcionario; mensagem se a empresa nao tem fundo.
  Fora: teto diario (006) e unificar com produzir (010).
  Depende de: 002.

- Task 006 — Teto salarial diario por skill
  Status: TODO
  Escopo: salario maximo/dia = 1.5 x nivel da skill relevante; acumulador ganho_hoje + data; se estourar, paga so o que cabe no teto (nao bloqueia o clique).
  Design: design/01-skills.md secao 1.3.
  Depende de: 005 (senao o teto so limita quanto se imprime).

### B. Loop de trabalho da empresa (plano antigo, depois da tesouraria)

- Task 007 — Cargo Dono automatico ao fundar
  Status: TODO
  Escopo: ao criar empresa, cria Cargo titulo Dono, ocupante = fundador, salario editavel pelo dono. Esse cargo NAO conta no limite de 1 emprego contratado — o jogador pode ser dono aqui e funcionario em outra.
  Fora: diploma; unificar produzir+salario (010).
  Depende de: 001, 006 (senao o dono se paga um salario absurdo no dia 1).

- Task 008 — Campo produto_em_producao na Empresa
  Status: TODO
  Escopo: FK opcional pra Produto; so o dono altera; validar que o produto e permitido pro tipo/terreno/industria da empresa.
  Fora: mudar as views de produzir/fabricar ainda.
  Depende de: 001 nao estar em voo.

- Task 009 — Funcionario nao escolhe o que produzir
  Status: TODO
  Escopo: produzir/fabricar usam empresa.produto_em_producao; se vazio, recusam; remover escolha de produto do POST do nao-dono.
  Depende de: 008.

- Task 010 — Um clique de trabalho: salario + contribuicao de producao
  Status: TODO
  Escopo: o clique principal (emprego) gasta energia uma vez, paga salario (005/006) e, se a empresa e Matriz/Industrial com produto_em_producao, contribui pra producao. Evita o dono clicar trabalhar e produzir no mesmo ciclo (50 de energia, dois ganhos).
  Depende de: 007, 009, 005.

- Task 011 — Especializacao mais lenta (2 -> 1)
  Status: TODO
  Escopo: GANHO_DE_ESPECIALIZACAO_POR_ACAO = 1 em empresas/models.py. So isso.
  Depende de: 010 preferencialmente (pra nao treinar em dois cliques paralelos).

### C. Loop do jogador, ainda sem geografia nova

- Task 012 — Mural publico de vagas
  Status: TODO
  Escopo: pagina listando Cargo vagos; candidatura; dono aprova (reusa contratar, sem o dono digitar username).
  Depende de: 007 ajuda (vaga Dono nao entra no mural).

- Task 013 — Freelance sem escolha de skill e com ganho minimo
  Status: TODO
  Escopo: core/views.py deixa de aceitar skill no POST; skill sobe a de menor nivel ou um default fixo; dinheiro/XP no piso (abaixo do emprego formal). Design: design/01-skills.md correcao de hoje.
  Depende de: nada.

- Task 014 — Qualidade (estrela) afeta nutricao/QoL ao consumir
  Status: TODO
  Escopo: efeito efetivo = efeito_base * (1 + (estrela - 1) * 0.2) na hora de comer. Preco ja usa preco_com_qualidade. Estoque ainda nao carrega lote/proveniencia — documentar a simplificacao (estrela de quem vendeu no Mercado, nao do fabricante original) se for essa a regra.
  Depende de: nada. Inventario e comer() ja existem.

- Task 015 — Higiene de design desatualizado
  Status: TODO
  Escopo: marcar como implementado o que o codigo ja faz: inventario (design/05-inventario.md ainda diz que nao existe), energia 25 (04-dia-a-dia.md), catalogo/Industrial->Industrial/estrela_minima (implicacoes-tecnicas.md). Nao reescrever o design.
  Depende de: nada. Esperar 001 pra manter um Current so.

---

## Future

Depois de A-C. Geografia e a proxima fundacao (moradia, escola, politica dependem de lote).

### D. Geografia com lotes

- Task 016 — Model Lote (bairro, indice, tipo de uso)
- Task 017 — Tipo de bairro (residencial/comercial/industrial) + capacidades
- Task 018 — Distancia da capital em Cidade
- Task 019 — Reescrever seed_geography (1 estado, 3 cidades, 3 bairros espalhados)
- Task 020 — Navegacao Estado -> Cidade -> Bairro -> Lote
- Task 021 — Empresa ocupa um Lote (fundacao exige lote vago do tipo certo)

### E. Construtora e moradia

- Task 022 — Model Imovel
- Task 023 — Construtora consome Materiais de Construcao + Moveis e cria Imovel no lote
- Task 024 — Cadastro coloca o jogador em albergue (sem buff de QoL)
- Task 025 — Compra de imovel pelo jogador
- Task 026 — Aluguel (valor/duracao pelo dono; despejo por inadimplencia; divida no Perfil ate existir Banco Central)
- Task 027 — qol_base calculada a partir da moradia
- Task 028 — Debuff apos 3 meses so em albergue

### F. Escola

- Task 029 — Model Escola ligada ao bairro
- Task 030 — Matricula automatica no cadastro (2 meses)
- Task 031 — Acao estudar no lugar de trabalhar durante a matricula
- Task 032 — Formatura automatica
- Task 033 — Diploma (catalogo minimo) — so depois disto o pre-requisito de Administracao Empresarial na fundacao entra na fila

### G. Servicos que hoje sao so enum

- Task 034 — Transporte: ticket, limite 2/dia, pequeno buff de QoL
- Task 035 — Lazer: buff temporario de QoL
- Task 036 — Publicidade (precisa de metrica de trafego de pagina — nao comecar antes)

### H. Politica e sistemas grandes (nao fatiar agora)

So depois de D-F existirem de verdade: orcamento publico, cargos politicos, leis parametricas, campanhas, populacao NPC de preenchimento, EventoHistorico/jornal, rankings, sociedade/Participacao, contratos, milicias.

Fatiar na hora. Nao sao a proxima fundacao.

---

## Blocked

- Task XXX — Diploma de Administracao Empresarial como pre-requisito pra fundar
  Reason: Escola/diploma nao existem (F).

- Task XXX — Bolsa de valores
  Reason: depende de sociedade/Participacao no lugar de Empresa.dono.

- Task XXX — Intervencao do governo na falencia da Financeira
  Reason: nao existe governo nem orcamento publico.

- Task XXX — Banco Central pra divida de aluguel
  Reason: conceito aberto no design (design/08-geografia-imoveis.md). Task 026 usa divida no Perfil ate isso fechar.

- Task XXX — Veiculo proprio (e excecao de Transporte 5 estrelas)
  Reason: adiado de proposito.

- Task XXX — NPC com IA (comprar/votar)
  Reason: design manda versao enxuta (preenchimento de imovel) primeiro; IA e fase tardia.

- Task XXX — Quantidade/formula/dissolucao de milicias
  Reason: propostas em design/10-futuro.md sem confirmacao; sistema inteiro e tardio.

---

## Fora da fila (higiene, nao e feature)

- DESIGN_1.md na raiz e o monolito antigo. Arquivar ou apontar pra design/ pra parar de confundir agente.
- Novo(a) Documento de Texto.txt nao deveria estar no repo.
- */tests.py hoje sao stubs. Preferir TestCase persistente no app em vez de smoke_test.py na raiz.
