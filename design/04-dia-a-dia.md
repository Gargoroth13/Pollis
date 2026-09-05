## 5. Dia a dia do jogador — revisão completa

### 5.1 Ações e custo de energia 🤝

| Ação | Custo de energia | Efeito |
|---|---|---|
| Trabalhar | 25 (era 10 no código — precisa mudar) | Ganha dinheiro + skill; contribui pra produção da empresa |
| Estudar (se matriculado) | 25 | Ganha skill (mais que trabalhar) |
| Praticar lazer | 25 | Buff temporário de QoL |

### 5.2 QoL — como funciona de verdade 🤝

- QoL tem uma **base**, definida pelos bens do jogador (casa, carro, roupas etc — sistema de posse ainda não existe)
- QoL decai em direção a essa base com o tempo
- Trabalhar/estudar **também** drena QoL diretamente: ~0.2 por clique
- Praticar lazer sobe QoL temporariamente
- Quanto maior o QoL, maior a **eficácia** de trabalho e estudo (multiplicador de ganho, ver seção 1.2)
- QoL base também define **quanto de energia regenera por tick** (novo vínculo — precisa de fórmula)

✅ **Resolvido — fórmula de energia por QoL:**
```
minutos_por_ponto_de_energia_efetivo = minutos_por_ponto_base / QoL_base
```
QoL 1 (padrão) = regen normal. QoL 0.5 = demora o dobro pra regenerar
cada ponto. QoL 1.2 (ex: cidade com população Ideal) = regen 20% mais
rápido. Mesma lógica pode valer pra saúde depois.

### 5.3 Saúde 🤝

- Chance de **decair por tick**, maior quanto menor o QoL (só quando QoL < 1)
- Se saúde chega num patamar baixo → jogador entra em "depressão", QoL base é **cortada pela metade**
- Se saúde chega a 0 → internado por 3 dias
- Jogador com diploma de Médico pode gastar 25 energia pra reduzir esse tempo de internação de outro jogador

✅ **Resolvido — patamar de depressão:** saúde ≤ 20 (de 100) ativa o
estado de depressão. Sai da depressão voltando a subir a saúde acima
desse patamar (com alguma folga pra não ficar entrando e saindo toda
hora — proponho sair só acima de 30, não exatamente 20, pra evitar
oscilação constante).

### 5.4 Nutrição (esse é o nome que você usou, substitui minha sugestão de "Saciedade") 🤝

- Funciona como a saúde, mas recupera consumindo **itens de alimento do inventário** (novo sistema, ver seção 6)
- Nutrição 0 começa a reduzir a QoL, até um piso de **60% da QoL base**

### 5.5 Viajar 🤝

- Paga uma empresa de Transporte
- Fica 1 dia sem trabalhar/produzir
- Ganha boost na QoL base — limite de **1x por mês**

---


## 20. Filosofia de feedback ao jogador (UI) 🆕

Princípio geral pra todo indicador importante, não só QoL: **nunca
mostrar só o número final, sempre mostrar por que ele é esse número.**
Ao clicar, abre um detalhamento aditivo:

```
QoL: 0.82 → 0.76
  Moradia:                    +0.10
  População acima do ideal:   −0.10
  Nutrição baixa:             −0.04
  Saúde baixa:                −0.02
```

Vale pra qualquer fórmula com múltiplas entradas somando num resultado
(QoL, custo de empresa, força militar, salário...). Tecnicamente,
significa que toda fórmula composta do jogo precisa **retornar o
detalhamento junto com o total**, não só o número final — é uma
convenção de código a manter desde o início dessas fórmulas, não um
retrofit fácil de fazer depois que tudo já retorna só um número.

---

