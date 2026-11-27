# AI Continuity Guide — Pollis

> **What this is:** an auxiliary context-and-continuity document for the assistant that works with the Game Director (GD). It records collaboration constraints, working habits, the direction of execution and a dated snapshot of the repository, so a new session does not lose context or repeat resolved discussions.
>
> **What this is not:** it is **subordinate to `CLAUDE.md` and to the `design/` documents**. It is **not a source of gameplay rules**, not a task queue (`TASK.md` / `TASK_QUEUE.md`), and not a decision log (`CHANGELOG_DEV.md`). Whenever this guide mentions a mechanic, it only *points* to where the rule lives; the rule itself is whatever `CLAUDE.md`, the design document or an explicit GD decision says. If this guide ever disagrees with any of them, **they win and this guide must be corrected**.
>
> **Last reconciled:** 2026-11-27 (after the GD's design-25 decisions and the Wave 1 audit). The snapshot in §4 is dated; always recheck the live repository and open PRs before relying on it.

## 1. Order of authority and how to use this guide

Order of authority (it follows `CLAUDE.md` §1; this guide sits **below all of it**):

1. `CLAUDE.md` (permanent development rules);
2. explicit, consolidated decisions of the GD;
3. `design/` documents in `FINAL — BOT TEST` state; then documents in `REVIEW` only when the requested work is explicitly about that document;
4. `CHANGELOG_DEV.md` (consolidated decisions and history);
5. `TASK.md` and `TASK_QUEUE.md` (work priority);
6. existing code, only where no design decision exists yet;
7. **this guide** — context only, never a tie-breaker for a rule.

At the start of a session:

1. Read `CLAUDE.md`, then `TASK.md`, then this guide.
2. Check the live GitHub state (`main`, open PRs, the files in question) instead of trusting the snapshot below.
3. Read the relevant `design/` documents before touching code.
4. Do not turn this guide into a duplicate tracker. Update it only when a durable collaboration decision or the execution direction changes, in a focused documentation change.

If documents conflict with each other (for example a document header and `TASK.md`), do not pick a side silently: record the conflict in `TASK.md` or `CHANGELOG_DEV.md` and let the GD decide (`CLAUDE.md` §1 and §13).

## 2. Collaboration decisions that persist

### 2.1 Bot Test scope is not reduced for implementation convenience

Everything designated for the first Bot Test stays in the first Bot Test, regardless of technical difficulty, dependencies or schedule pressure.

- A technical problem is work to solve, not permission to remove a feature.
- A dependency changes the order of execution, not the commitment.
- Do not relabel included work as `P2`, `FUTURO` or "out of scope". A feature missing from one PR is not outside the Bot Test; it stays assigned to an explicit later step.
- Only exclusions explicitly established for the whole first Bot Test remain excluded (today `13`, `15` and `16`, which are `FUTURO`; recheck `TASK.md`). A limitation of one implementation phase is not a global exclusion.

### 2.2 Resolved decisions are not reopened

Before asking a question or proposing a different rule, read the design and `CHANGELOG_DEV.md`. Do not ask the GD to decide what is already decided or specified. Preserve approved decisions even if implementation becomes awkward.

### 2.3 Progress means working, verified software

Batch related review, code, tests, documentation corrections and PR updates into one coherent delivery instead of cycling through micro-corrections. Report **real evidence only**: exact commands, results and skips. Never claim a test was run when it was only read; never hide a failure.

### 2.4 Decisions requested from the GD go at the end

Genuine questions are collected in a final section titled **"Decisões necessárias do Game Director"**: numbered, each with the precise question, why it matters, clear alternatives, the consequence of each and a recommendation. If none is needed, say so. Design decisions belong to the GD, never to the agent (`CLAUDE.md` §3); do not fill a design gap with a silent choice (`CLAUDE.md` §13). Do not introduce artificial limits automatically: first establish whether a risk is real or already prevented by existing rules, and present alternatives that preserve player freedom.

### 2.5 PRs, merges and history

- **Never merge a PR without explicit GD authorization for that specific PR.** "Looks good", "ready" or green tests are not authorization. Authorization for some PRs does not extend to others.
- No rebase, no force push, and published commits are not altered. Bring a base branch in with a merge commit; retargeting a PR's base is done only when the GD's instructions call for it.
- Do not start new systems (for example P1.04f, P1.05b) while the GD's priority is auditing and consolidating what already exists.

## 3. Execution notes (technical; no gameplay rules)

- **Shared paths.** Humans and Bots use the same Action Registry and validation path (`CLAUDE.md` §5.4). No privileged route for Bots.
- **Monetary values** are integer centavos; transfers move existing money (`CLAUDE.md` §5.2). An unspecified design value is `NULL`, never `0`, and whoever consumes it refuses with `UNSPECIFIED_DESIGN_VALUE`.
- **Explainability.** Composite formulas return the value plus a structured breakdown (`CLAUDE.md` §6).
- **Lazy catch-up trap (lesson from Auto-consumption).** Access hooks run inside `players.services._catch_up()`; a hook must not call a public service that re-enters `sync_player()`. Reuse the business rule on the already-locked player and test the non-recursion explicitly. The rule of Auto-consumption itself lives in `design/04` §16 and is integrated (PR #14).
- **Test clock.** `core.clock.use_clock` stores the clock in a `ContextVar`, so threads must run in a copy of the caller's context. See PR #35 (§4); until it is integrated, tests that cross 30-day budget periods in threads can depend on today's real date.
- **Design 25 is binding where the GD approved it.** `design/25-Insolvencia-Recuperacao-Falencia-REVIEW.md` (PR #34) stays in `REVIEW` for integration details, but its explicitly approved decisions (administrative capacity, financial states, wage protection, creditor priority, bankruptcy, liquidation, ownership transfer, cumulative cooldown; F1–F10) are binding and are not reopened. Its open points are listed in its §25.8 and must be proposed to the GD before the affected parts are implemented. Do not build temporary mechanisms that conflict with it (audit findings A-01 and A-06 wait for it).
- **Locking protocol.** Lock order is player → company → (stock / work) → ledger; PostgreSQL guarantees (`SELECT … FOR UPDATE`) are tested on PostgreSQL, because SQLite serializes writes differently and some tests are PostgreSQL-only.

## 4. Repository snapshot (2026-11-27)

This is a **dated snapshot**, not a substitute for checking GitHub live.

**`main` = `b1ed17a`.** Integrated with GD authorization on 2026-11-27, in order, by merge commit: PR #12 (P1.02 Inventário, `ee185c2`), PR #14 (P1.02a Auto-consumo, `4be2bf6`), PR #32 (P1.15a Rankings, slice 1 of 5, `b1ed17a`). Earlier foundations (#8–#11) were merged before them. Evidence on consolidated `main`: 1287 tests OK on PostgreSQL 16 and on SQLite (SQLite skips the PostgreSQL-only tests), `manage.py check` and `makemigrations --check` clean, migrations applied on fresh databases, integrity audits clean on an empty database.

**Open PRs (none merged; each needs its own GD authorization):**

| PR | Content | Notes |
|---|---|---|
| #13 | this guide | docs only, independent |
| #33 | reconciliation of `TASK.md`, `TASK_QUEUE.md`, `CHANGELOG_DEV.md` with `main` | docs only |
| #35 | `run_together` context propagation | test infrastructure only; fixes thread tests that used the real clock |
| #34 | `design/25` Insolvency, Recovery and Bankruptcy (REVIEW) | docs only; GD-approved decisions are binding; review notes posted on the PR |
| #36 | adversarial economic audit of Wave 1 | tests only; stacked on #19; evidence of A-01..A-06 |
| #37 | Wave 1 fixes A-02..A-05 (A-01/A-06 left to design 25) | stacked on #36; turns the exploit tests into regression tests |
| #15 → #16 → #17 → #18 → #19 | Empresas (core; positions/wages; production/stock; Engineer/Lawyer support; Retail/Construtora) | **Wave 1**, under adversarial audit |
| #20 → #21 → … → #31 | Market transparency, Schools, Contracts, Properties (+ transfer, housing, location, building use), Budget, Legislation, Bot infrastructure, World history | stacked on #19; each branch conflicts with `main` only in `CHANGELOG_DEV.md`, `TASK.md`, `polis/settings.py` |

Known cross-document conflict, registered and unresolved: the headers of `design/01-skills.md` and `design/03-escolas.md` say `REVIEW`, while `TASK.md` lists both as `FINAL — BOT TEST`. Only the GD can decide which one holds.

## 5. Execution direction (strategy, not a second queue)

Current GD priority: **audit and consolidate the existing implementations before starting new systems.** Individual task definitions and acceptance criteria stay in `TASK_QUEUE.md`.

1. Close documentation and test infrastructure (#33, #34, #13, the `run_together` fix) — no merge without GD authorization.
2. Audit the stacked PRs in waves, bottom-up (Wave 1 = Empresas #15–#19). Each audit is adversarial: it tries to break conservation, concurrency and limits, separates real risks from risks already prevented, and classifies findings as BLOCKER / MAJOR / MINOR / DEFERRED with executed evidence.
3. Resolve open design points through GD decisions (section 2.4), then continue the dependency-driven roadmap in `TASK_QUEUE.md` (Market, Schools, real estate, Contracts, budget, politics, feedback, history, remaining Rankings slices, UI shell, military, Bot Test engine/training/monitoring).
4. Do not stop at foundations while committed Bot Test systems remain unimplemented; keep every in-scope system visible until delivered.

## 6. Standard loop for a task

1. Read `CLAUDE.md`, the relevant `design/` sections, dependencies and recorded GD decisions before coding.
2. Implement in small, verifiable steps, with tests for normal path, limits, permissions, invalid states, economic effects, state transitions, idempotency and time cycles (`CLAUDE.md` §10), including concurrency tests where relevant.
3. Run relevant tests and, when appropriate, the full suite on PostgreSQL and SQLite; report exact commands, results and skips.
4. Update `TASK.md`, `TASK_QUEUE.md` and `CHANGELOG_DEV.md` truthfully, with real commits and PR links.
5. Leave the PR open; deliver one consolidated report ending with the decisions section (2.4).

## 7. Practical environment notes

- Tests: `SECRET_KEY=dev python -B manage.py test … --noinput`; SQLite with `DATABASE_URL` unset; PostgreSQL with `DATABASE_URL=postgres://…` and `POLIS_EXPECT_DB=postgresql`. Never run two PostgreSQL suites against the same cluster at once.
- GitHub via REST (`gh api`): comments, base retargeting and merges are API calls; merging is done only on explicit GD authorization.
- Commits end with the `Co-Authored-By` and `Claude-Session` lines; PR descriptions end with the generated-with line and the session URL.

## 8. Handoff template

Adapt to the live state before using:

> Read `CLAUDE.md`, `TASK.md` and `AI_CONTINUITY_GUIDE.md`, then check the live repository. Continue the GD's current priority (audit and consolidation before new systems). Do not merge, rebase or force push without explicit authorization; do not reduce Bot Test scope; do not reopen approved decisions; do not invent mechanics or add artificial limits. Report real evidence, and put genuine questions only in the final section "Decisões necessárias do Game Director".
