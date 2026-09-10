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