# 01 — Skills

> Status: REVIEW
> Última revisão: 2026-09-10
>
> Este documento está em revisão e ainda não deve ser tratado como
> especificação final para implementação definitiva.

## 1. Skills do jogador (revisão grande)

**Só existem 3 skills, e elas substituem as 8 categorias antigas
(Indústria, Comércio, Tecnologia etc — essas viram classificação de
empresa, não de jogador, ver seção 2):**

- Inteligência
- Físico
- Carisma

Crescem infinitamente. Nascimento no bairro já define o nível inicial
de cada uma (mantém o que já tínhamos de sorteio por faixa de renda).

### 1.1 Como cada skill cresce

| Fonte | Efeito |
|---|---|
| Trabalhar | Cresce, mas menos que estudar. Cada emprego/cargo específico aumenta **uma** skill só (definida pelo cargo) |
| Estudar (escola/universidade) | Cresce mais que trabalhar |
| Atividades de lazer / grupos de estudo | Também aumenta skill, fora da escola/universidade |

### 1.2 Fórmula de ganho de skill ✅ (você confirmou com exemplos)

```
ganho = QoL_base × qualidade_da_escola × ganho_base
```

Exemplos que você deu (batem com essa fórmula):
- QoL 1, escola qualidade 1 → ganho 1 (nas 3 skills)
- QoL 0.5, escola qualidade 1 → ganho 0.5
- QoL 0.5, escola qualidade 0.5 → ganho 0.25

### 1.3 Skills afetam produção e salário

- Skill relevante do funcionário define **quanto** a empresa produz por
  clique de trabalho (Matriz e Industrial)
- Skill relevante também define o **salário máximo** que o cargo pode
  pagar: `salário máximo = 1.5 × nível da skill`. Exemplo: Físico 100
  numa Matriz de mineração → salário máx. R$ 150
- 🆕 Skill alta também vira **requisito de acesso**, não só
  multiplicador — cargos de gestão dentro da empresa, cargos políticos
  e cargos de pesquisa exigem um nível mínimo pra sequer se candidatar,
  igual ao `nivel_minimo` que já existe nos Cargos normais hoje. Ou
  seja, a mesma mecânica de gate que já implementamos passa a valer
  também pra política e pesquisa, não só emprego comum.

⚠️ **Pendência:** seu exemplo fala em salário *diário* máximo, mas hoje
o `Cargo.salario` é pago por clique de "trabalhar", não por dia. Preciso
que você diga se o teto é por dia (daí precisa somar os ganhos do dia)
ou por clique.

✅ **Resolvido: o teto é por dia**, não por clique. Implementação
proposta: um contador simples (`ganho_hoje` + `data_referência`),
que soma cada pagamento e zera quando o dia muda. Se a soma do dia
ultrapassar o teto, o pagamento daquele clique é cortado no que sobrar
até o limite (não bloqueia o trabalho, só limita o quanto entra).

### 1.4 Diminishing returns 🆕 (proposta, você pediu o conceito sem fórmula)

Skill continua crescendo infinitamente, mas a eficiência de ganho cai a
cada 100 pontos:

```
faixa = nível // 100
multiplicador_de_eficiência = 1 / (1 + faixa × 0.2)
```

| Nível | Multiplicador |
|---|---|
| 0–99 | 1.0x (cheio) |
| 100–199 | 0.83x |
| 200–299 | 0.71x |
| 300–399 | 0.63x |
| 400–499 | 0.56x |

Isso multiplica o `ganho` calculado na fórmula da seção 1.2. Continua
sem teto — só fica cada vez mais caro virar especialista de verdade,
o que empurra o jogador a diversificar em vez de empilhar tudo numa
skill só.

---


---

## Correção de hoje: skill não é escolha do jogador

✅ O jogador **não escolhe** qual skill sobe. A fonte define:
- Escola (primeiros 2 meses de conta): sobe as 3 juntas
- Emprego formal: só a skill do `Cargo.skill_relevante`, sem escolha
- Freelance (sem escola, sem emprego): continua existindo, mas dá o
  **mínimo possível** de dinheiro e de skill — rede de segurança, não
  fonte principal de progresso
