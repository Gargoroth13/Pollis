# AI Continuity Guide — Pollis

> **Purpose:** persistent working context for the assistant collaborating with the Game Director.
>
> **This is not a task queue, does not replace `TASK.md` or `TASK_QUEUE.md`, and is not the source of truth for gameplay rules.** It records durable collaboration decisions, scope constraints, current execution direction, and the next handoff to Claude so future reviews do not lose context or repeat resolved discussions.
>
> **Last reconciled:** 2026-10-18. Recheck the live repository and open PRs whenever this guide is used; do not assume the snapshot below is still current.

## 1. Authority and how to use this guide

At the start of a Pollis work session, the assistant should:

1. Read this guide.
2. Check the current GitHub state, especially `main`, open PRs, and the relevant files.
3. Use the design document as the authority for game rules, explicit Game Director (GD) decisions as the authority for choices already made, and `TASK_QUEUE.md` as the authority for task ordering/status.
4. Use `CHANGELOG_DEV.md` as the decision history. This guide preserves collaboration constraints and the execution plan; it must not become a duplicate task tracker.
5. When meaningful new decisions are made, update this guide in a focused documentation change/PR. Do not create noise by updating it for every minor code detail.

If this guide conflicts with a newer explicit GD decision or the current design, the newer decision/design wins and this guide must be corrected. If status files contradict the actual GitHub state, reconcile them rather than perpetuating the contradiction.

## 2. Non-negotiable collaboration decisions

### 2.1 Bot Test scope is not negotiable by implementation convenience

The GD's explicit instruction is:

**Everything originally designated for the first Bot Test stays in the first Bot Test, regardless of technical difficulty, architectural complications, dependencies, or schedule pressure.**

- A technical problem is work to investigate and solve, not permission to remove a feature.
- A dependency changes the order of execution, not the overall commitment.
- A true missing design decision must be surfaced to the GD, with impact and a recommendation.
- Do not silently relabel included work as `P2`, `FUTURO`, “out of scope,” or “deferred indefinitely.”
- A feature being outside one PR does **not** mean it is outside the Bot Test. Keep it assigned to a later, explicit implementation step.
- Only exclusions explicitly established before implementation as exclusions from the **first Bot Test** remain excluded. A limitation for one implementation phase is not automatically a global Bot Test exclusion; keep it visible for later integration unless the GD explicitly excluded it from the whole Bot Test.

### 2.2 No reopening resolved decisions

Before asking a question or proposing a different rule, inspect the applicable design and decision history. Do not ask the GD to decide something that has already been approved or that the design already specifies. Preserve approved decisions even if implementation becomes awkward.

### 2.3 Progress must mean working software

The collaboration has spent too long cycling through small corrections without enough task completion. Avoid repeated micro-audits and fragmented prompts when related issues can be handled together.

For each implementation task, batch the relevant review, code changes, tests, documentation/status corrections, and PR update into a coherent delivery. Report real test evidence accurately. Do not hide failures or claim tests were run when they were only reviewed statically. Keep scope intact while resolving blockers.

### 2.4 Decision requests belong at the end

If GD input is genuinely required, collect all such questions in one final section titled **“Decisões necessárias do Game Director”**. For each, state the precise question, why it blocks or affects implementation, the consequence, and a recommendation. Do not scatter questions throughout the status report. If no decision is needed, say so explicitly.

### 2.5 PR and merge authority

The assistant may inspect code, identify problems, draft prompts, and recommend changes. **Do not merge a PR without explicit authorization from the GD.** Do not treat “looks good,” “ready,” or a test pass as permission to merge.

## 3. Durable project decisions relevant to execution

### 3.1 Auto-consumption is in the first Bot Test

The rule is already documented in `design/04-dia-a-dia.md`, §16. It is not a pending gameplay-design decision and must not be described as outside the Bot Test.

The defined behavior is:
- The player can enable Auto-consumption and select a preferred food.
- When Nutrition is below 10, the system tries to consume food during lazy processing of the player's state.
- Priority: preferred food if present in inventory; otherwise, eligible food with the smallest Nutrition gain.
- Repeat while Nutrition remains below 10 and eligible food exists; stop once Nutrition reaches or exceeds 10.
- If no eligible food exists, do nothing.
- Use the same consumption rules as manual consumption. Do not add a special Nutrition bonus for automatic use.
- Do not poll every player continuously just to detect hunger.

**Known implementation trap:** `players.services._catch_up()` runs access hooks. A hook that calls the public `inventory.services.consume()` may re-enter `sync_player()` → `_catch_up()` and recurse. The implementation must reuse the same business rules while operating on the player already locked/processed, without re-entering the lazy catch-up path. Test this explicitly.

The feature may be implemented in a dedicated follow-up after the inventory foundation is accepted; that separation is a task boundary, **not** a scope reduction. Do not claim the tie-break for equal minimum Nutrition gains is specified if the design does not define it. Resolve it deterministically as an implementation detail only if appropriate, and ask the GD only if it materially affects gameplay.

### 3.2 Existing explicit exclusions must be interpreted narrowly

The design/status files already designate some systems (currently `13 — Eventos Aleatórios`, `15 — Jornalismo`, and `16 — Sociedades e Ações`) as FUTURO, subject to rechecking the live source when relevant. Preserve exclusions that were explicitly agreed for the whole first Bot Test.

Conversely, a task-specific limitation must not be stretched into a global exclusion. For example, the prior decision to leave operational materials out of the **first implementation of Empresas** does not by itself authorize deleting all such functionality from the Bot Test plan. Keep deferred work visible and revisit it in its planned integration phase.

### 3.3 Shared player/Bot paths and auditability

Humans and Bots must use the same Action Registry and the same validation/business-service path. Do not invent privileged execution routes for Bots. Preserve the project's established focus on atomicity, idempotency, traceable domain movements, structured refusal codes, explainable calculations, and audit commands. Real concurrency concerns should be reproduced and resolved, not dismissed as test flakiness without evidence.

## 4. Repository snapshot at last reconciliation

This is a **dated snapshot**, not a substitute for checking GitHub live.

- PRs **#8, #9, #10, and #11** were merged in order. The latest reported main base for the inventory work was commit `d0a8e9a938ff91960e7d8a2b102596974ff57658`.
- PR **#12 — P1.02 Inventário** is open against `main`, head branch `dev/p1.02-inventario`, last inspected head `e5278b80b424d2e1f138474a5d87e02a5b561fe6`. **Do not merge without GD authorization.**
- PR #12 implements inventory holdings, immutable movement/shipment history, manual `consume`, mail `send_item`, inventory audit, and provisional mail/food-effect parameters.
- Claude's final PR summary reports 997 tests passing on PostgreSQL and SQLite (13 skips on SQLite), after an earlier intermediate report of one failing PostgreSQL test for crossed simultaneous sends. The code now locks both player rows in ascending primary-key order. Before approval, verify that the final PostgreSQL result was actually obtained against the latest commit after the fix; do not treat the intermediate 55/56 result as final or infer that the final claim was independently rerun by the assistant.
- The current work log/queue contains stale statements that describe auto-consumption as out of scope or awaiting a GD decision even though §16 defines its behavior. Those statements must be corrected in the relevant branch/status files as part of closing this stage.

## 5. Execution plan — strategic stages, not a second task queue

Use `TASK_QUEUE.md` for individual task definitions, acceptance criteria, and detailed ordering. This section preserves the important execution direction only.

### Stage A — Finish P1.02 cleanly

1. Confirm on the current PR head that the PostgreSQL crossed-send concurrency test passes after the locking fix. Confirm the reported full-suite results and `check` / `makemigrations --check` evidence.
2. In the P1.02 working branch, reconcile `TASK.md`, `TASK_QUEUE.md`, `CHANGELOG_DEV.md`, and the PR description with the real state. Remove the false claim that Auto-consumption awaits a gameplay decision or is out of scope of the Bot Test. It may remain a separate follow-up task; it must remain planned.
3. Review the full P1.02 diff once, in a consolidated pass. Fix genuine correctness, concurrency, integrity, or misleading-documentation blockers in a batch. Do not reopen unrelated design or expand P1.02 into other systems without need.
4. Report whether P1.02 is ready for GD approval. Leave the PR open until the GD explicitly authorizes merge.

### Stage B — Implement Auto-consumption as Bot Test work

After the inventory foundation is accepted, implement the behavior already defined in `design/04-dia-a-dia.md`, §16. Include player preference/configuration, lazy-processing integration, safe non-recursive service reuse, and tests for preferred food, fallback selection, repeated consumption, threshold stopping, no eligible food, and inventory/Nutrition/audit consistency.

Do not replace implementation with another design discussion. Bring only genuinely undefined, gameplay-significant choices to the GD.

### Stage C — Continue the dependency-driven Bot Test roadmap

Continue with the next ready implementation in `TASK_QUEUE.md` (the current planned sequence places Empresas at P1.04 after the already integrated Action Registry P1.03), then proceed through Market/transparency, Schools, real estate/zoning, Contracts, public budget, legislative/political systems, structured feedback, world history, rankings, UI shell, military, and the Bot Test engine/training/monitoring work according to the authoritative queue.

Do not stop after foundational services if committed Bot Test systems are still unimplemented. Preserve inter-task dependencies and approved exclusions, but keep every other in-scope system visible until delivered.

## 6. Standard execution loop

For each task, the assistant should ask Claude to:

1. Read the guide, the authoritative design sections, relevant dependencies, and recorded GD decisions before coding.
2. State a concise implementation plan only when useful; then implement, rather than sending repeated status-only updates.
3. Deliver the complete task acceptance criteria, including relevant integration, concurrency/property tests, audit coverage, and documentation updates.
4. Run the relevant tests and the full suite when appropriate; use PostgreSQL for guarantees that depend on PostgreSQL locking. Report exact commands/results and skipped tests.
5. Update the current task/status records truthfully and include the actual commit and PR link.
6. Keep the PR open for GD review; never merge without authorization.

The assistant should then review the delivered diff and evidence, batch corrections into one actionable handoff to Claude, and put genuine GD questions at the end. Do not silently change scope or re-litigate settled decisions.

## 7. Next handoff to Claude

Use this handoff to close the current stage; adapt it to the live PR state before sending:

> Read `AI_CONTINUITY_GUIDE.md` first and follow its scope rule. For PR #12, confirm that the crossed-send concurrency test and full suite pass on the current head after the PostgreSQL deadlock fix, and report the actual final evidence. Correct the misleading Auto-consumption status in `TASK.md`, `TASK_QUEUE.md`, `CHANGELOG_DEV.md`, and the PR text: §16 already defines the behavior, and it remains required for the first Bot Test. Keep it as a visible follow-up after the inventory foundation; do not implement it inside P1.02 unless the task plan calls for that explicitly. Do not cut scope, do not reopen approved design, and do not merge. Complete any related documentation corrections together, then report one consolidated status with tests, commit, PR, blockers, and any genuine GD decisions at the very end.
