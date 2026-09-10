## 19. Militares e Milícias 🆕 — sistema novo e grande

Primeiro sistema do jogo com conflito direto entre jogadores — tudo o
resto até aqui é econômico/político sem "combate". Esse é o design com
mais peça móvel em aberto de todos até agora.

### 19.1 Exército

- Governo contrata jogadores como militares — funcionário público,
  análogo a um Cargo, mas com exclusividade: **militar não pode ter
  outro emprego nem ser dono de empresa**
- Treinamento gasta energia, sobe Físico; cargos de comando (Capitão,
  General, Marechal) também exigem Inteligência
- Nível de investimento do governo (orçamento, seção 9) afeta a
  eficiência do treinamento

### 19.2 Milícias

- Múltiplas milícias independentes podem existir ao mesmo tempo
- Jogador (não-militar) se filia à milícia alinhada com seus interesses políticos
- **Membro ≠ mobilizado**: liderança convoca mobilizações específicas;
  só uma parte dos membros participa de cada confronto
- Líder da milícia vencedora assume a Presidência — condição
  **propositalmente muito difícil** de acontecer

### 19.3 Força e prontidão

| Lado | Força depende de |
|---|---|
| Exército | Quantidade de militares, skill média, treinamento/investimento, prontidão atual |
| Milícia | Quantidade de membros mobilizados, skill média, e um multiplicador ligado à QoL global — **quanto menor a QoL nacional, maior a capacidade de mobilização das milícias** |

Militar é individualmente mais eficiente, mas milícia muito numerosa
pode superar Exército profissional só pelo número. Prontidão do
Exército desgasta com confronto/mobilização, recupera com
investimento/treino/descanso.

### 19.4 Regras do confronto

- **Vitória por atrito**: milícia não precisa ganhar um confronto —
  perder repetidamente já desgasta o Exército financeira e
  operacionalmente até a repressão deixar de valer a pena pro governo
- **Derrota da milícia não é punição pesada**: só fracassa aquela
  mobilização específica, pode tentar de novo
- **Custo da repressão**: manter o Exército mobilizado gera custo pro
  orçamento — campanha prolongada pode ficar insustentável
- **Renúncia pacífica**: presidente pode sair voluntariamente antes de
  uma derrota total, evitando queda violenta
- **Vitória da milícia**: líder assume a Presidência e pode indicar
  novos membros do STF

✅ **Cooldown entre Exército e Milícia** (regra sua, confirmada): quem
sai de uma milícia só pode entrar no Exército depois de **3 meses**.
Quem sai do Exército só pode entrar numa milícia depois de **3 meses**
também. Evita troca oportunista de lado no meio de um conflito.

✅ **Trava constitucional sobrevive a uma tomada de poder** — confirmado:
mesmo com o líder da milícia assumindo a Presidência, as garantias de
moradia/educação (seção 11.6) continuam valendo. O novo presidente
herda a mesma trava, não começa "zerado".

🆕 **Propostas pro resto (ainda sem sua confirmação):**

- **Quantidade de milícias**: sem mínimo nem máximo teórico — qualquer
  jogador pode fundar uma. Proponho só um piso de **5 membros** pra uma
  milícia ser "oficial" (aparecer no ranking, poder mobilizar) — abaixo
  disso é só um grupo informal sem efeito mecânico.
- **Fórmula de força:**
  ```
  Força do Exército = nº de militares × skill Físico médio × prontidão (0 a 1)
  Força da Milícia  = nº de membros mobilizados × skill Físico médio × multiplicador de QoL nacional
  ```
  onde o multiplicador de QoL só ativa abaixo do ideal: `multiplicador = 1 + (1 − QoL_nacional)` se QoL < 1, senão `1`. Isso implementa direto a regra que você já tinha dado (QoL baixa = milícia mais forte).
- **Exército após deposição**: proponho que o Exército seja **dissolvido**
  — todo militar vira civil livre pra escolher novo emprego, e o novo
  presidente (ex-líder de milícia) começa um Exército do zero. Isso
  evita que vencer uma vez vire vantagem militar permanente, reforçando
  o "deve ser muito difícil de alcançar" que você já tinha pedido.
- A trava constitucional (seção 11.6, moradia/educação) continua valendo depois de uma tomada de poder, ou é reiniciada?

---