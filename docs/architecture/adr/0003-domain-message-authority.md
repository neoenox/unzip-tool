# ADR 0003 — User-facing domain messages have one authority

- Status: Accepted (implementation pending)
- Date: 2026-11-28

## Context

`unzipper.py` repeats the same Japanese guidance strings at 4–5 throw sites (missing password, wrong password, wrong/corrupt password, unsupported links). `DISK_FULL_MESSAGE` was already consolidated in PR #107 because the UI compares the exact text to offer recovery. Other messages are asserted only by exception type or substring, so they can be named without changing behaviour.

## Decision

Define named constants in `unzipper.py` for each *distinct* message concept and use them at every throw site. Distinct wording stays distinct (missing vs wrong password vs wrong-or-corrupt): unifying different concepts is out of scope. Keep every existing substring used by tests and UI.

## Consequences

- Copy edits happen once; future UI recovery actions can bind to a name instead of a literal.
- No new message module: these strings belong to the domain that produces the error.
