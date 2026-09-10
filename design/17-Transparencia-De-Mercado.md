## 17. Transparência de mercado 🆕

Mercado (e a página de cada Produto) passam a mostrar estatística
agregada, não só "compre aqui":

```
Café
Preço médio: R$ 42       Menor preço: R$ 31       Maior preço: R$ 68
Estoque total: 14.200     Produção diária: 11.800   Consumo diário: 13.500
Tendência: ⬆️ +8% (últimos 7 dias)
```

E a página da empresa ganha um resumo de causa-efeito nos custos:

> Seus custos aumentaram 14% nos últimos 7 dias. Principal causa: alta de 21% no preço do Aço.

Tecnicamente é "só" leitura agregada do que já existe — mas expõe uma
lacuna real: hoje o preço de venda é sempre o `preco_base` fixo do
catálogo (a seção 2.12 já previa isso mudando por qualidade). Pra
"tendência" e "preço médio" fazerem sentido, precisa existir um
histórico de preço por transação de verdade, não só o preço "oficial".

---