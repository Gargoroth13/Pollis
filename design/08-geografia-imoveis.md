## 10. Imóveis e zonas ✅ (mantém, com um ajuste)

Mantém a tabela de zonas/tipos que já tínhamos. Ajuste: reforçar que a
estrela da empresa de Varejo (e não só da Construtora) determina qual
imóvel comercial ela pode ocupar.

### 10.1 Imóveis residenciais em detalhe 🆕 (faltava, proposta)

| Tipo | Capacidade | Estrela mínima da Construtora | Efeito na QoL base do morador |
|---|---|---|---|
| Baixa densidade simples | 1 família por lote | 1★ | +0 (linha de base) |
| Baixa densidade luxo | 1 família por lote | 3★ | +0.3 |
| Alta densidade simples | ~20 unidades por prédio | 2★ | +0.1 |
| Alta densidade luxo | ~20 unidades por prédio | 4★ | +0.4 |

Isso é o que vai alimentar o "bens do jogador" que a seção 5.2 menciona
como base da QoL (junto com carro, roupas etc, que ainda não têm
sistema próprio).

---


---

## Revisão grande de hoje: lotes, distância, moradia

### Hierarquia com lotes individuais

```
Estado → Cidade → Bairro → Lote
```

Hoje `Bairro` é só um registro com QoL/faixa de renda — não existe
`Lote` (o pedacinho de terra onde uma casa/empresa realmente fica).
Clicar num Estado mostra as Cidades, clicar numa Cidade mostra os
Bairros, clicar num Bairro mostra os Lotes dele.

### Capacidades

| Nível | Capacidade |
|---|---|
| Estado | até 25 Cidades |
| Cidade | até 25 Bairros |
| Bairro residencial | 50 lotes |
| Bairro comercial | 30 lotes (Especial soma nesse pool) |
| Bairro industrial | 20 lotes (Rural soma nesse pool) |
| Qualquer bairro | +5 lotes institucionais fixos |

### Distância da capital

Cada Cidade ganha um "endereço": capital = 0, outras cidades em
múltiplos de 20 (20, 40, 60...). Define posição no mapa, tempo de
viagem, e o boost de QoL de um emprego (quanto mais longe, menor —
✅ **zero se for em outro estado**, dentro do mesmo estado usa
`boost = boost_base × (1 − distância / maior_distância_do_estado)`).

### Seed inicial (bem menor que o atual)

1 Estado, 3 Cidades (uma luxo, uma média, uma pobre), 3 Bairros no
total (um residencial, um comercial, um industrial — não é por
cidade, é espalhado entre as 3). O `seed_geography` atual (1 estado, 1
cidade, 8 bairros) precisa ser reescrito do zero.

## Moradia (sistema novo)

- Jogo começa com todo mundo num **albergue** — sem buff de QoL, por
  no máximo 3 meses
- Depois de 3 meses sem moradia própria: **debuff de -0.5 de QoL**
  (placeholder grande de propósito, balancear depois)
- Encontrar onde morar (compra ou **aluguel**) dá um buff de QoL, maior
  quanto mais luxuoso o imóvel

### Aluguel

Dono do imóvel define valor e duração livremente. Inadimplente é
despejado, e o valor devido vira dívida registrada num **Banco
Central**.

⚠️ **Pendência**: "Banco Central" é conceito novo — ainda não existe em
lugar nenhum do design. É uma entidade sempre presente desde o início
do jogo (não fundada por ninguém), controlada por um cargo político,
ou outra coisa? Também pode ser a mesma coisa mencionada antes sobre
"banco central controlado por jogadores" na falência de Financeira
(02-empresas.md / seção da Financeira).
