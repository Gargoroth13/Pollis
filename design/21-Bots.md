## 21. Bots para testes de beta 🆕 (metodologia de teste, não mecânica de jogo)

Não é conteúdo do jogo final — é ferramenta de validação antes do
lançamento:

- Criar usuários-bot progressivamente (proposta: 1 por hora), jogando
  sob as **mesmas regras** dos jogadores reais (sem trapacear limite
  de energia etc)
- Comportamento simples (regras básicas tipo "se energia > 50%,
  trabalha; se dinheiro > X, tenta abrir empresa"), não precisa de IA
  sofisticada
- Registrar o comportamento pra achar problema estrutural antes de
  gente de verdade jogar: gargalo de produção, concentração de
  emprego, empresa quebrando em cadeia, falta de produto, distribuição
  de riqueza anormal

Isso é plano de teste, não roadmap de feature — vale um `TESTING.md`
próprio quando chegar perto do lançamento, não uma fase no roadmap
principal.

---