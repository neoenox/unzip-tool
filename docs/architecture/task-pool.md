# Optimization task pool

Ranked by (user-visible drift risk reduced × caller count) / (behaviour change + migration risk).
Status: `ready` = safe now; `candidate` = verified but needs a round; `deferred` = see ADR 0004.

| ID | Task | Authority gained | Risk | Status / acceptance |
|---|---|---|---|---|
| A1 | `unzipper.FORMATS` registry; derive suffixes, detection, dest stripping, dialog filters, help line | One place to add a format | Low: pure derivation, existing callback contracts unchanged | done — round 1; dialog consumer covered by a behavioral test |
| A2 | Name the repeated domain messages in `unzipper.py` | One authority per message concept | Low: strings unchanged at every site | done — round 2; 15 sites migrated, canonical message set asserted in tests |
| A3 | Share terminal-event set between `jobs.py` and `app.py` | One worker protocol definition | Low: same set, no protocol change | done — round 3; all five consumers migrated, unknown-event guard added |
| A4 | Replace 3 PowerShell version regex parsers with one helper | `version.py` is parsed in one shared PowerShell helper | Low with PS-only helper: release-QA hosts need no Python | done — round 4; `scripts/get-version.ps1` is the sole parser, contract test migrated |
| A5 | Delete test-only `_check_names_safe` adapter | Tests call `_safe_join` directly | Low: wrapper only looped over `_safe_join` | done — round 5; no production caller existed, behavior-preserving |
| D1 | Unified cancellation contract for both worker types | Shared worker lifecycle | High: behaviour change | deferred — product decision required |
| D2 | One geometry validator for Python + PowerShell | One minimum-window rule | High: visible resize behaviour | deferred — product decision required |
| D3 | Split `App` domain state from widget state | Stable job-state API | High: ~1,350-line migration | deferred — dedicated round after A1–A3 |
| D4 | Encapsulate DnD hwnd state | Single drop-state owner | Medium: tests poke privates | deferred — test migration required |
| D5 | Consolidate `updates.py` failure messages | One update-message catalog | Medium: pinned substrings | deferred — bundle with update-flow round |
| D6 | Consolidate repeatable test scaffolding (`pump`, fake IDataObject) | One harness | Low value, many test edits | deferred — do only if a new test needs it |

## Done

round 1 (format registry), round 2 (domain messages), round 3 (worker protocol), round 4 (PowerShell version reader), round 5 (test-only adapter deletion); see `progress.md`
