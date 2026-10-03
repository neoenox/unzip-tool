# Windows release verification

## 2026-10-03 verification

- Installed 1.0.0 into a dedicated test directory, then upgraded it to 1.0.1. The registered version and installed location matched the update.
- In actual Windows Explorer, right-clicked a ZIP with a Japanese name and spaces. The Open With submenu displayed かんたん解凍. Selecting it opened the archive card; clicking 解凍する produced the expected Japanese text file. The executable launched by Explorer matched the published 1.0.1 SHA256.
- Uninstalled the dedicated installation. Its executable and archive handler were removed; a test user file remained. Restored the normal application location using the published 1.0.1 installer and checked its executable hash and quoted archive launch command.
- Expanded a ZIP to approximately 256 MiB using the spawned worker. Verified its output size. Cancelled another extraction after its output file had begun growing; the worker stopped, no result was published, and staging was removed.
- Confirmed corrupted ZIPs produce actionable Japanese guidance and do not prevent the next valid archive from extracting.
- Injected ENOSPC after writing a partial file to reproduce a disk-full write failure without filling the user's disk. Verified no output or staging remained. Tested Japanese guidance for capacity and access failures, including task-start failure in the GUI.
- All local test suites passed; actual RAR3/5 expansion was skipped locally because UnRAR is absent. Windows CI installs UnRAR and covers these formats.

## Before each release

1. Wait for the PR and main Windows checks to pass, then use the reviewed main commit.
2. Create a new annotated `vMAJOR.MINOR.PATCH` tag at that commit and push only that tag.
3. The release workflow rejects commits that are not ancestors of main. It runs all tests, builds the executable and installer, tests installation and removal, and uploads both files to the matching GitHub Release.
4. Verify the release run succeeded and both nonempty assets are uploaded. Keep published tags and older assets unchanged.
5. Repeat Explorer Open With and extraction checks when shell registration or startup changes. Use dedicated archives and preserve existing default applications and user data.
