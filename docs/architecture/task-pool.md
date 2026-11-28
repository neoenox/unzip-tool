# Optimization task pool

Ranked by (user-visible drift risk reduced × caller count) / (behaviour change + migration risk).
Status: `ready` = safe now; `candidate` = verified but needs a round; `deferred` = see ADR 0004.

| ID | Task | Authority gained | Risk | Status / acceptance |
|---|---|---|---|---|
| A1 | `unzipper.FORMATS` registry; derive suffixes, detection, dest stripping, dialog filters, help line | One place to add a format | Low: pure derivation, existing callback contracts unchanged | ready — all format tests + new registry contract test green; no stale literals left in Python |
| A2 | Name the repeated domain messages in `unzipper.py` | One authority per message concept | Low: strings unchanged at every site | ready — all sites use constants; tests asserting substrings unchanged |
| A3 | Share terminal-event set between `jobs.py` and `app.py` | One worker protocol definition | Low: same set, no protocol change | candidate — verify no consumer treats a different subset as terminal |
| A4 | Replace 3 PowerShell version regex parsers with one helper | `version.py` is read, not re-parsed | Medium: release-QA host assumptions | candidate — see D5; keep version-consistency test green |
| A5 | Delete test-only `_check_names_safe` adapter | Tests call `_validate_entries` directly | Low: no production caller | candidate — only worthwhile if it removes real indirection, not just lines |
| D1 | Unified cancellation contract for both worker types | Shared worker lifecycle | High: behaviour change | deferred — product decision required |
| D2 | One geometry validator for Python + PowerShell | One minimum-window rule | High: visible resize behaviour | deferred — product decision required |
| D3 | Split `App` domain state from widget state | Stable job-state API | High: ~1,350-line migration | deferred — dedicated round after A1–A3 |
| D4 | Encapsulate DnD hwnd state | Single drop-state owner | Medium: tests poke privates | deferred — test migration required |
| D5 | Consolidate `updates.py` failure messages | One update-message catalog | Medium: pinned substrings | deferred — bundle with update-flow round |
| D6 | Consolidate repeatable test scaffolding (`pump`, fake IDataObject) | One harness | Low value, many test edits | deferred — do only if a new test needs it |

## Done

(no rounds completed yet; see `progress.md`)
