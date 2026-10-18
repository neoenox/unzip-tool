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
2. Bump the version in one place: `version.py`. PR CI and the release workflow read it from there (#61), so the workflow files, the PowerShell scripts, and `KantanKaiko.iss` must not carry a version of their own.
3. Create a new annotated `vMAJOR.MINOR.PATCH` tag at that commit and push only that tag.
4. The release workflow rejects commits that are not ancestors of main and tags that do not match `version.py`. It runs all tests, builds the executable and installer, tests installation and removal, and uploads both files to the matching GitHub Release.
5. Verify the release run succeeded and both nonempty assets are uploaded. Keep published tags and older assets unchanged.
6. Run the manual Explorer checks in [manual-explorer-qa.md](manual-explorer-qa.md) and record the result below. Automated tests cover the app logic, but not Explorer's menu entry, the real OLE drop, or the drag-over highlight.
7. Repeat Explorer Open With and extraction checks whenever shell registration or startup changes. Use dedicated archives and preserve existing default applications and user data.

## 2026-10-18 v1.1.0 release verification

What was actually verified for `v1.1.0` (tag points at `13587ad`, released 2026-10-18T00:22:47Z):

- The PRs included in this release had green Windows CI before merging; main CI was green at each merge commit (`64d66dc`, `13587ad`, `52760c0`, `b872670`).
- The tag-triggered release workflow run `39082412963` (workflow `build-exe`, event `push`, branch `v1.1.0`, commit `13587ad`) completed with `success`. This run is the one that exercised the full test suite, the PyInstaller build, the installer build, and the install/uninstall checks.
- GitHub Release `v1.1.0` is published (not draft, not prerelease) with exactly two uploaded assets:
  - `KantanKaiko.exe` — 14,654,430 bytes
  - `KantanKaiko-Setup-1.1.0.exe` — 16,404,422 bytes
- Local verification used a dedicated settings directory (`KANTAN_SETTINGS_DIR`) so the checks did not touch a real user profile's `%APPDATA%\KantanKaiko\settings.json`.

Not verified for this release (no evidence, do not treat as passing):

- No interactive Explorer check was performed for `v1.1.0`: Open With → かんたん解凍, real drag-and-drop from Explorer, and the drag-over highlight (added in #29, after this tag) were **not** exercised by hand. The real Explorer drop path cannot be synthesized because it uses OLE shared memory.
- The downloaded `v1.1.0` executables were not run on a clean Windows machine as part of this verification; only the CI run and the Release asset metadata above were checked.
- #29's OLE `IDropTarget` drag-over highlight was merged after this tag and is therefore not part of `v1.1.0` at all.

## 2026-10-18 v1.2.0 release verification

What was actually verified for `v1.2.0` (tag points at `9a34a94`, released 2026-10-18T08:34:27Z):

- Included changes: #15/#11 (UnRAR policy docs and list-debounce regression test), #29 (OLE drag-over highlight), #24 (shortcuts, settings persistence, in-app help), #61 (version single source).
- Windows CI was green on the merged main commit `9a34a94` (run `39111824089`) and on the PR branch (`cdf8ec8`, run `39111583699`). The PR run built the installer, exercised install/reinstall/uninstall, and printed `PASS install, shortcut, version, reinstall, uninstall, and preservation of user files` for version `1.2.0`.
- The tag-triggered release workflow run `39111834857` (workflow `build-exe`, event `push`, branch `v1.2.0`, commit `9a34a94`) completed with `success`.
- GitHub Release `v1.2.0` is published (not draft, not prerelease) with exactly two uploaded assets:
  - `KantanKaiko.exe` — 14,674,094 bytes
  - `KantanKaiko-Setup-1.2.0.exe` — 16,425,265 bytes
- Local pre-release checks used a dedicated settings directory (`KANTAN_SETTINGS_DIR`): `python -m pytest -q` → 130 passed, and `python tests/run_all.py` passed every suite.
- Version single-source check on this machine: `./scripts/build-installer.ps1` with no `-Version` produced `dist/KantanKaiko-Setup-1.2.0.exe` from `version.py`, and running Inno Setup without the version defines aborted with `AppVersion is not defined.` instead of silently building an old version. The generated installer was deleted after the check; the machine already had an installation, so `test-installer.ps1` was intentionally not run locally (CI performs it).
- `updates.check_latest()` run against the published release (2026-10-18) returned `{'version': '1.2.0', 'newer': False}` for the current `VERSION` and `newer: True` with the `v1.2.0` URL for `1.1.0`, so 更新の確認 reports `v1.2.0` as the latest release instead of offering a false update.

Not verified for this release (no evidence, do not treat as passing):

- No interactive Explorer check was performed for `v1.2.0`: Open With → かんたん解凍, a real drag-and-drop from Explorer, and the drag-over highlight from #29 were **not** exercised by hand. [manual-explorer-qa.md](manual-explorer-qa.md) defines the steps, but they are still unexecuted. The real Explorer drop path cannot be synthesized because it uses OLE shared memory.
- The downloaded `v1.2.0` executables were not run on a clean Windows machine; only the CI runs and the Release asset metadata above were checked.
- `%APPDATA%\KantanKaiko\settings.json` restoration (window position and last destination) was verified by automated Tk tests, not by restarting a real installed build by hand.

Open item carried to the next release:

- The workflows were moved to Node24-compatible action majors (`actions/checkout@v7`, `actions/setup-python@v7`, `actions/upload-artifact@v7`, `softprops/action-gh-release@v3`) in #64, after this tag. The `v1.2.0` release run used the previous versions, so `action-gh-release@v3` has not run at a tag yet; confirm the Release step and both assets at the next release. PR CI with the new majors was green (run `39113108342`) with no Node20 deprecation annotation.

