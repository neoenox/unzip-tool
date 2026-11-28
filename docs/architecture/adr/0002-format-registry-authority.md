# ADR 0002 — One format registry in the domain layer

- Status: Accepted (implementation pending)
- Date: 2026-11-28

## Context

Adding or changing an archive format currently requires edits in `unzipper.SUPPORTED_SUFFIXES`, `unzipper.detect_kind`, `unzipper.default_dest_for`, `app.FILTERS`, and `ui.HELP_SECTIONS`. A drift between detection and either the file dialog or the help text is user-visible and only partly covered by `tests/test_ui.py:790`.

## Decision

`unzipper` owns a frozen `FORMATS` registry: `(kind, filter label, suffixes)`. From it derive:

- `SUPPORTED_SUFFIXES` (order preserved for existing behaviour),
- `is_supported`, `detect_kind`, `default_dest_for` suffix stripping,
- `FILTERS` used by the file dialog in `app.py`,
- the supported-formats line in `ui.HELP_SECTIONS`.

Per-format prose (password support, UnRAR requirement) stays in help copy; only the machine-readable suffix list is generated. `app.FORMAT_BADGE` stays separate: a badge label is not a dialog filter group.

## Alternatives rejected

- Generating a Python module from a JSON manifest: adds a build step and a second file to keep in sync.
- Keeping UI constants and adding a consistency test: treats drift as a test failure instead of making it impossible.

## Verification

- Existing tests: `test_7z`, `test_rar`, `test_ui.test_help_matches_supported_suffixes`, `test_safety.default_dest_for`.
- New guard: a test asserts the dialog groups cover exactly the registered suffixes and that each group's label/kind mapping matches the registry.
