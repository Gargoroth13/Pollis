# Polis — TASK Atual

**Status:** EM EXECUÇÃO  
**Fase:** Transição de Design para Implementação  
**Responsável:** Claude (Dev)  
**Direção:** Game Director

---

# Objetivo atual

Preparar o repositório para iniciar a implementação do **primeiro Bot Test**, preservando as decisões de design consolidadas e evitando que o desenvolvimento avance sobre especificações ainda ambíguas.

O projeto já possui o núcleo de design amplamente consolidado. A prioridade agora é transformar as decisões estáveis em código incrementalmente testável.

---

# Situação dos documentos

## FINAL — BOT TEST

- `01 — Skills`
- `02 — Empresas`
- `03 — Escolas`
- `07 — Leis`
- `08 — Geografia`
- `09 — Orçamento Público`
- `10 — Imóveis e Zonas`
- `12 — Histórico do Mundo`
- `14 — Rankings`
- `17 — Transparência de Mercado`
- `18 — Contratos`
- `20 — Filosofia de Feedback ao Jogador`
- `21 — Bots para Testes de Beta`

## REVIEW / consolidação necessária

- `06 — Política`
- `11 — Leis Paramétricas`
- `19 — Militar`
- `SITEMAP-REVIEW.md`

## FUTURO / não bloquear o núcleo

- `13 — Eventos Aleatórios`
- `15 — Jornalismo`
- `16 — Sociedades e Ações`

## Catálogo central

- `22 — Receitas-Produção`

O catálogo de `22` deve ser tratado como fonte central de Produtos e Receitas e revisado quanto à consistência antes de depender dele em larga escala.

---

# Correções conhecidas que não podem ser perdidas

## Política

- três cargos executivos: Presidente, Governador e Prefeito;
- Deputados na Câmara nacional;
- um cargo político por jogador;
- mandatos parametrizáveis; padrões: Presidente 6 meses, Governador 6 meses, Prefeito 4 meses, Deputado 6 meses;
- candidatura depende de requisitos definidos em `06` e `11`;
- Governador exige experiência anterior como Prefeito;
- Presidente exige experiência anterior como Governador e diploma de Engenharia, Direito ou Medicina;
- um jogador vota uma vez por eleição aplicável e pode votar em si mesmo;
- empate presidencial somente gera segundo turno entre empatados;
- leis nacionais no primeiro Bot Test;
- Governadores e Prefeitos podem encaminhar sugestões ao Presidente;
- político pode possuir empresa privada, mas empresa de político não pode receber contrato público;
- político não pode ser empregado de outra empresa enquanto ocupar cargo político;
- salário político é derivado do salário mínimo × multiplicador definido por lei;
- trabalho político real consome Energia e gera ganhos de skill próprios do cargo;
- deposição presidencial por milícia encerra a Câmara e gera nova eleição da Câmara;
- Governadores e Prefeitos permanecem após deposição presidencial;
- Constituição sobrevive a troca/deposição presidencial.

## Leis

- discussão: 3 dias;
- votação da Câmara: 3 dias;
- janela semanal fixa; propostas que entram fora da janela aguardam o próximo ciclo;
- aprovação por maioria absoluta da composição congelada;
- veto presidencial;
- derrubada de veto por 2/3 da Câmara;
- mudança de Presidente durante sanção/veto devolve a proposta à Câmara para nova votação;
- entrada em vigor no próximo weekly tick;
- leis não retroativas;
- propostas sobre o mesmo parâmetro não podem conflitar enquanto uma estiver ativa/em trânsito;
- histórico de versões e votos deve ser auditável.

## Leis Paramétricas

- vendas: 0–50%, padrão 5%;
- renda: 0–50%, padrão 5%;
- salário mínimo: R$0–R$1.000, padrão R$50;
- antitruste: 1–100, padrão 1;
- subsídio setorial: 0–75%, padrão 0;
- teto salarial: mínimo R$50, sem teto máximo político;
- educação: piso legal a ser consolidado na versão FINAL do documento;
- saúde: piso legal 1–30%, padrão 10%;
- infraestrutura: piso legal 1–30%, padrão 10%;
- déficit público: 0–50%, padrão 10%;
- multiplicadores salariais: Presidente 1–50 padrão 10; Governador 1–40 padrão 8; Prefeito 1–35 padrão 7; Deputado 1–35 padrão 7;
- IPTU: 0–50%, padrão 1%;
- teto de posse: 1–50, padrão 10, separado por jogador/empresa;
- controle de aluguel: 0–30%, padrão 10%, aplicado ao reajuste do contrato existente;
- idade mínima da conta para candidatura: 30–300 dias, padrão 90;
- Carisma mínimo: 0–100, padrão 10;
- experiência anterior para Governador e Presidente permanece parametrizável conforme `11`;
- limite de mandatos consecutivos: 1–10, padrão 2;
- duração de mandato: 2–8 meses, com padrões específicos por cargo;
- campanhas temporárias entram no processo legislativo completo e possuem duração/custo/intensidade parametrizados conforme `11`.

## Militar

- não existe cooldown entre Exército e Milícia;
- jogador pode entrar/sair de ambos conforme regras normais;
- Milícia e Exército usam produtos/recursos reais;
- conflito não cria equipamentos ou dinheiro do nada;
- resultado gera hospitalização/desgaste conforme regras do sistema;
- deposição presidencial usa a vitória correspondente conforme `19`.

## Feedback

- fórmulas compostas retornam valor + detalhamento estruturado;
- limites e condições devem aparecer no feedback quando relevantes.

## Bots

- RL híbrido;
- apenas informação que jogador teria;
- Action Registry compartilhado;
- Action Masking;
- recompensa por tipo/objetivo;
- exploração por tipo/perfil;
- memória individual;
- modelo compartilhado versionado;
- população-alvo inicial ≈ 1.000;
- criação padrão ≈ 1 Bot/minuto até a meta, com Population Controller para preencher lacunas;
- ambiente único contínuo;
- relógio padrão ≈ 1 dia de jogo / 10 minutos reais;
- logs e relatório exportáveis;
- dashboards completos;
- identificação automática de lacunas de cobertura.

---

# Tarefa de implementação imediata

## Fase 1 — Fundação do motor do jogo

Implementar ou consolidar as fundações necessárias para que os sistemas FINAL possam evoluir sem duplicação:

1. ciclo temporal e processamento lazy/scheduled;
2. Energia, regeneração, QoL, Saúde e estados básicos do jogador;
3. skills e progressão;
4. geografia Estado → Cidade → Bairro → Lote;
5. Produto, Receita, inventário e estoque empresarial;
6. Action Registry compartilhado;
7. estrutura de auditoria/eventos de domínio;
8. padrão de feedback estruturado definido em `20`;
9. base de testes de integração.

Não implementar ainda os sistemas FUTURO apenas por conveniência.

---

# Critérios de aceitação da fase 1

- o jogador pode ser criado e possui estado inicial consistente;
- tempo do servidor pode avançar de forma determinística;
- Energia/QoL/saúde possuem testes;
- skills podem crescer segundo as regras documentadas;
- geografia básica funciona e possui relacionamentos corretos;
- Produtos/Receitas possuem fonte central;
- inventário/estoque não confundem posse com consumo;
- existe Action Registry reutilizável;
- ações inválidas são bloqueadas pelo mesmo mecanismo para jogador e Bot;
- uma fórmula composta consegue retornar valor + detalhamento;
- eventos importantes deixam registros auditáveis;
- testes automatizados cobrem os fluxos principais.

---

# Regra para o agente

Antes de iniciar qualquer tarefa dessa fase, conferir os documentos de design relacionados.

Se encontrar conflito entre código antigo e design consolidado, adaptar o código ao design documentado.

Se encontrar conflito entre dois documentos de design, não escolher silenciosamente: registrar a pendência em `CHANGELOG_DEV.md` e continuar apenas nas partes não afetadas.
