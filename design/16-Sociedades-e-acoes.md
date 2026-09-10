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