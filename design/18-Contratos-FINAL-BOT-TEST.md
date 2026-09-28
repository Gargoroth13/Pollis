# 18 — Contratos entre Jogadores e Empresas

**Status: FINAL — BOT TEST**

## 18.0. Objetivo

Contratos formalizam acordos de prazo ou recorrentes entre duas partes, permitindo que o jogo registre as obrigações, execute as transações automaticamente e aplique consequências quando uma parte não cumprir o combinado.

O contrato é uma camada de formalização e execução. As regras específicas de cada atividade continuam nos documentos do sistema correspondente.

---

## 18.1. Partes do contrato

As partes podem ser **jogadores ou empresas**, conforme o tipo de contrato.

Cada contrato possui duas partes identificadas pelo sistema e pode envolver, por exemplo:

- jogador ↔ jogador;
- jogador ↔ empresa;
- empresa ↔ empresa;
- empresa ↔ governo, quando aplicável ao tipo de contrato governamental.

O sistema registra a identidade real das partes para execução, auditoria e aplicação de penalidades.

---

## 18.2. Tipos de contrato no Bot Test

Entram no primeiro Bot Test:

| Tipo | Exemplo |
|---|---|
| Fornecimento | Empresa A fornece 10.000 unidades de Aço por mês à Empresa B por R$ 12/unidade |
| Empréstimo entre jogadores | Jogador A empresta R$ 100.000 ao Jogador B por 90 dias a 2% de juros |
| Aluguel | Proprietário fornece o uso de um imóvel a um jogador ou empresa mediante pagamento periódico |
| Governamental | Governo contrata uma empresa para executar uma obra ou outro serviço previsto pelo sistema |

**Contrato de trabalho não faz parte do sistema.** Emprego continua sendo tratado pelas regras normais de trabalho das empresas.

---

## 18.3. Informações armazenadas

Todo contrato deve registrar, no mínimo:

| Campo | Descrição |
|---|---|
| Partes | Jogadores e/ou empresas envolvidos |
| Tipo | Categoria do contrato |
| Objeto | Produto, dinheiro, imóvel, obra ou outra obrigação definida pelo tipo |
| Quantidade | Quando aplicável |
| Valor | Preço, parcela, juros ou outra obrigação financeira |
| Frequência | Única, diária, semanal, mensal ou outra frequência suportada pelo tipo |
| Prazo | Data de início e encerramento |
| Condições | Regras específicas permitidas pelo tipo de contrato |
| Multa | Valor da penalidade por quebra, quando prevista |
| Status | Ativo, inadimplente, encerrado ou quebrado |
| Histórico | Eventos relevantes de execução, pagamentos, entregas e encerramento |

Cada tipo de contrato pode possuir campos adicionais próprios de sua mecânica.

---

## 18.4. Aceite

O contrato só entra em vigor depois que **as duas partes aceitarem** os termos apresentados.

Depois do aceite, os termos do contrato ficam congelados para aquela obrigação. Qualquer alteração relevante exige encerramento do contrato atual e criação de um novo contrato, salvo mecanismo específico definido futuramente.

---

## 18.5. Execução automática

Um contrato ativo deve ser executado automaticamente nas datas definidas por seus termos.

Exemplo:

> Empresa A deve fornecer 10.000 unidades de Aço à Empresa B no primeiro dia de cada mês por seis meses.

Na data prevista, o sistema verifica as condições necessárias e tenta executar a entrega e o pagamento conforme o contrato.

A execução deve produzir registros auditáveis de sucesso ou falha.

---

## 18.6. Inadimplência

Quando uma obrigação não puder ser cumprida no prazo, o contrato entra em **inadimplência**.

A inadimplência não significa automaticamente que todo o contrato foi cancelado.

O sistema registra:

- qual obrigação falhou;
- qual parte era responsável;
- data da falha;
- valores ou quantidades pendentes;
- penalidade aplicável, quando houver.

O comportamento posterior depende das condições previstas no contrato e das regras específicas do tipo de contrato.

---

## 18.7. Quebra voluntária

Qualquer parte pode solicitar o encerramento antecipado de um contrato.

Se o contrato possuir uma multa de quebra, a parte responsável pelo encerramento paga a penalidade prevista à outra parte.

Depois da resolução da obrigação e da multa aplicável, o contrato passa para **encerrado/quebrado**, conforme o motivo registrado.

---

## 18.8. Multa

A multa é definida no momento da criação do contrato dentro dos limites permitidos pelo tipo de contrato.

Quando aplicada, a multa é uma transferência de dinheiro da parte responsável para a outra parte.

A multa **não cria dinheiro novo na economia**.

---

## 18.9. Encerramento normal

Quando todas as obrigações forem cumpridas e o prazo terminar, o contrato é encerrado normalmente.

O histórico permanece disponível mesmo depois do encerramento.

---

## 18.10. Relação com outros sistemas

O contrato não substitui as regras dos sistemas que ele formaliza.

### `10 — Imóveis e Zonas`

Define as regras dos imóveis e do aluguel. `18` define a formalização, execução e encerramento do contrato de aluguel.

### `02 — Empresas`

Define empresas, produtos, produção, compras, vendas e relações de trabalho. `18` permite formalizar acordos comerciais recorrentes entre empresas e/ou jogadores.

### `09 — Orçamento Público`

Define orçamento e execução financeira do governo. Contratos governamentais utilizam essas regras para pagamento e comprometimento de recursos públicos.

### `16 — Sociedades e Ações`

Futuramente, contratos poderão participar da negociação e transferência de participações, mas o sistema de ações está fora do primeiro Bot Test.

---

## 18.11. Transparência e auditoria

Todo contrato deve possuir histórico de eventos suficiente para reconstruir sua execução.

Devem ser registrados, quando aplicável:

- criação;
- aceite de cada parte;
- alterações permitidas;
- pagamentos;
- entregas;
- falhas;
- aplicação de multas;
- encerramento;
- quebra antecipada.

O registro deve identificar as partes e manter as informações necessárias para auditoria.

---

## 18.12. Regras fora do primeiro Bot Test

Não fazem parte da primeira versão:

- reputação de contratos;
- avaliação automática de confiabilidade das partes;
- contratos de trabalho como categoria própria;
- sistemas avançados de arbitragem;
- mercado secundário específico para contratos;
- cláusulas livres criadas pelos jogadores fora dos campos suportados pelo sistema.

Esses mecanismos podem ser adicionados posteriormente sem alterar a estrutura básica de contratos.

---

## 18.13. Bot Test

O Bot Test deve verificar, no mínimo:

1. criação de contratos entre jogador e jogador, jogador e empresa e empresa e empresa;
2. aceite das duas partes;
3. execução automática de fornecimento recorrente;
4. execução e pagamento de empréstimo;
5. execução de aluguel;
6. execução de contrato governamental;
7. falha por falta de dinheiro ou estoque;
8. entrada em inadimplência;
9. aplicação correta de multa;
10. encerramento normal;
11. quebra antecipada;
12. preservação do histórico após encerramento.
