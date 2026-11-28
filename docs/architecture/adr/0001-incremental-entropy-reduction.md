# ADR 0001 — Incremental, verifiable entropy reduction

- Status: Accepted
- Date: 2026-11-28
- Baseline: `origin/main` @ `fab7d5a` (v1.2.13)

## Context

The codebase is a small Windows desktop app with a long history of incremental fixes. Several rules are encoded in more than one place, UI state and domain state share one object, and the release layer re-parses data that Python already owns. A big-bang rewrite would risk the safety, packaging, and update contracts that are only covered by integration tests.

## Decision

1. Work in an isolated git worktree (`refactor/architecture`), never on `main`.
2. Each round completes the full loop: scan → rank → baseline → migrate every caller → delete the replaced implementation → independent review → verify → add regression guard → commit → record.
3. No new abstraction, directory or interface without migrating all callers and removing the old path in the same round.
4. Use the Deletion Test: keep a layer only if removing it pushes complexity into callers instead of deleting it.
5. Prefer deletion over addition; never combine semantically different concepts to reduce line count.
6. Mechanical constraints (tests, CI, AST/text checks) are added only for norms already agreed here.
7. Product decisions, behaviour changes and unsafe gate relaxations are recorded as deferred, not improvised.

## Consequences

- Each commit is independently revertable and must leave the full suite green.
- Test suites that pin exact strings or file layout are constraints, not obstacles; update them only when the contract intentionally changes.
- Full-suite runs are slow (~9 min on this host because of GUI/cross-process tests), so each round uses targeted tests first and the full suite at the round boundary.
