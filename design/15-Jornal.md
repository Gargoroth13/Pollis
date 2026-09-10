## 15. Jornal / feed de notícias 🆕

Feed gerado automaticamente pelos próprios sistemas — sem geração de
texto livre por IA, só templates preenchidos com dado real:

- Produto varia X% de preço em 24h → "Mercado do {produto} registra {alta/queda} de {X}%"
- Nova zona aberta → "Prefeitura de {cidade} anuncia nova zona {tipo}"
- Empresa grande falindo → "{Empresa} entra em falência"
- Lei aprovada → "{Cargo} aprova {nome da lei}"
- Mobilização de milícia → "{Milícia} convoca nova mobilização"
- QoL nacional caindo 3 meses seguidos → "QoL nacional cai pelo terceiro mês consecutivo"

Reaproveita o mesmo `EventoHistorico` da seção 12 — a diferença é só de
apresentação: histórico é a página completa e permanente, jornal é o
feed recente com cara de manchete. Podem ser a mesma tabela, com um
campo `eh_manchete`.

---