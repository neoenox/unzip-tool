# Refactoring progress

## Environment

- Worktree: `C:/vibe/unzip-tool-arch`, branch `refactor/architecture`, base `origin/main` @ `fab7d5a` (v1.2.13).
- Python: 3.11.15 (`C:/vibe/unzip-tool/.venv`), pytest 8.4.2.
- RAR tests need `tools/UnRAR.exe` (git-ignored); copied from the main checkout into the worktree for verification.

## Baseline (2026-11-28)

- First full run without `tools/UnRAR.exe`: 183 passed, 1 failed (`test_password.py::test_rar_password_flow` — missing tool), 1 skipped, 535.9 s.
- After provisioning UnRAR: the failing RAR test plus `test_rar.py` = 6 passed; baseline considered green.
- Slow part: GUI and cross-process DnD tests; use targeted runs during a round, full suite at the boundary.

## Rounds

| Round | Commit | Change | Verification | Review | Notes |
|---|---|---|---|---|---|
| 0 | `f302ab3` | architecture map, ADRs, task pool (no code) | full suite green (baseline) | — | docs-only batch |
| 1 | `64e8efb` | `unzipper.FORMATS` registry derived suffixes/detection/dialog filters/help line; deleted `app.FILTERS` literal | targeted 101 passed; full suite 185 passed, 1 skipped | Round1Review: one gap — dialog test did not cover picker consumer; fixed in same round (test now asserts `askopenfilenames(filetypes=...)`) | no behaviour change; installer suffix literals remain a separate text-test contract |

## Conventions for each row

- `Change`: what was migrated and what old implementation was deleted.
- `Verification`: targeted commands and full-suite result.
- `Review`: independent reviewer outcome, with any follow-up committed in the same round.
