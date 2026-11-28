# ADR 0004 — Decisions awaiting confirmation or a product decision

- Status: Open (do not act without explicit approval)
- Date: 2026-11-28

| ID | Issue | Why deferred | What would unblock it |
|---|---|---|---|
| D1 | `ThreadTask.cancel` only sets `finished`; the thread keeps running, unlike `BackgroundTask.cancel` | There is no cooperative cancellation point inside `_extract_into`; adding one changes worker semantics and needs product approval | Decide whether the fallback must stop mid-extraction; then add tests and a shared cancellation contract |
| D2 | `settings.MIN_* = 640x560` vs `app.minsize(700,680)`; PowerShell QA uses a stricter geometry regex | Aligning changes visible window behaviour and release QA; not purely mechanical | Product decision on the supported minimum and one shared validator used by both Python and QA |
| D3 | `App` is a ~1,350-line object mixing domain state and 25+ widget handles | Splitting needs a stable contract for job state and a large migration; risky without a UI refactor goal | Approve a dedicated round with contract tests for `ArchiveJob` state transitions |
| D4 | `dnd.py` / `dnd_ole.py` keep module-level hwnd-keyed maps | Tests deliberately poke those privates; encapsulation changes the test contract | Approve test migration plus a single drop-state owner |
| D5 | Three PowerShell version regex parsers and README version literals | Parsers resolved in round 4 via `scripts/get-version.ps1` (no Python needed on QA hosts); README literals remain test-pinned | Product decision only if README examples should also be generated |
| D6 | Distinct full failure messages inside `updates.py` | Only two byte-identical messages were consolidated (round 7); the remaining wording expresses different failures and must stay distinct | Product/UX decision if those messages should be rewritten; no action needed for entropy reduction |

Deferred items are recorded here and in `task-pool.md`; work continues on independent tasks.
