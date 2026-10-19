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

## 2026-10-18 v1.2.0 installed-build checks (the automatable part of the manual checklist)

The checklist in [manual-explorer-qa.md](manual-explorer-qa.md) was run against the published `v1.2.0` installer on this machine, using the installed build rather than the source tree. Items that can be evidenced without a human were executed and are listed as PASS; items that need Explorer itself, a real pointer, or real typing remain 未実施 and are listed separately. This supersedes the earlier note that settings persistence had only been verified by automated Tk tests.

How the installed GUI was driven: keyboard messages (`WM_KEYDOWN`/`WM_CHAR`) with scan codes attached, window-only screenshots via `PrintWindow(PW_RENDERFULLCONTENT)` (the desktop was never captured), and `KANTAN_SETTINGS_DIR` to keep the real `%APPDATA%\KantanKaiko\settings.json` out of the destructive cases.

Installer used: `KantanKaiko-Setup-1.2.0.exe`, SHA256 `b061891c57e9813c41edb1b4e22c842cc7bc9c33b0cf76b835b0b480ecfb9deb`, which matches the Release asset digest.

PASS with evidence:

- **1 installer** — a silent run (`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART`) exited 0. The uninstall entry reports `DisplayVersion 1.2.0`, `InstallDate 20261018`; files are placed in `%LOCALAPPDATA%\Programs\KantanKaiko`, and the Start Menu shortcut `…\Programs\かんたん解凍\かんたん解凍.lnk` exists.
- **2 version and icon** — the installed `KantanKaiko.exe` is 14,674,094 bytes, SHA256 `bbf37cef261fa46903f2d29d729eef3b7e6314aa8a9f13e9b3cb966cb2299842`, byte-identical to the Release asset. A window-only screenshot of the installed build shows the window icon and the header `ZIP・7z・RAR・TAR / v1.2.0`.
- **3 Open With (the app side of it)** — `HKCU\Software\Classes\KantanKaiko.Archive\shell\open\command` is `"…\KantanKaiko.exe" "%1"`, and `KantanKaiko.Archive` is listed under `OpenWithProgids` for `.zip`, `.7z`, `.rar`, `.tar`, `.gz`, `.tgz`. Existing defaults were left alone: WinRAR stayed the default for `.zip`/`.7z`/`.rar`. Launching the installed executable with `日本語 テスト 1.zip` — exactly what the registered command does — added one card, with the Japanese name and its space rendered correctly and a green `解凍できます` badge.
- **5 password archive, display half** — launching with `secret.zip` shows the orange `PW必要` badge, the Japanese prompt `パスワードを入力してください。`, the password row with its `表示` checkbox, and the `再試行` / `パスワードを入力` buttons.
- **6 extraction, Japanese names** — driving the installed build with the Return key extracted `日本語 テスト 1.zip`. The output folder holds exactly `readme.txt`, `notes/メモ 1.txt`, and `notes/deep/さらに深い.txt`: the same names and bytes as the archive entries, and the Japanese body text reads back correctly, so nothing was mangled.
- **7 re-extraction numbering** — extracting the same archive a second time produced `plain` and `plain (2)` (and `日本語 テスト 1` / `(2)`) with identical contents, leaving the first folder's file untouched.
- **9 settings persist and restore** — closing the window created `%APPDATA%\KantanKaiko\settings.json` where no file existed before. Given a settings file with `geometry = 900x700+300+200` and `last_dest` pointing at the QA output folder, the installed build opened at `[300, 200]` with that destination shown in the UI, and closing kept both values.
- **10 off-screen geometry is ignored** — with `geometry = 900x700+9000+9000` the installed build opened on screen at the default placement (`+234+234`) and rewrote `settings.json` to `780x760+234+234`.
- **11 uninstall** — running the generated uninstaller silently exited 0. Afterwards the executable, the Start Menu shortcut, the `KantanKaiko.Archive` ProgID, the `.zip` `OpenWithProgids` entry, and the uninstall entry were all gone, while a file created by hand in the install directory, `tools\UnRAR.exe` (565,032 bytes; not shipped by the installer), and `%APPDATA%\KantanKaiko\settings.json` survived. Re-running the published installer restored `1.2.0` with SHA256 `bbf37cef…299842` and all of the registrations above.
- **12 `Delete`** — pressing `Delete` on a one-card list removed the card and left the archive file on disk.

Not verified for this release (no evidence, do not treat as passing):

- **1 wizard text** — the install was silent, so the Japanese wizard pages were never displayed.
- **3 Explorer menu appearance** — the registration exists and the registered command works, but Explorer's Open With submenu itself was not opened.
- **4, 5 real drag-and-drop** — the Explorer drop path hands data over through OLE shared memory, so it cannot be synthesized, and no human ran it. The drag-over highlight from #29 is a rendering result for the same reason.
- **8 password retry by typing** — the `PW必要` state and its prompt were captured, but text could not be delivered into the Tk password entry from outside the process: posting `WM_CHAR` to both the client window and the entry's own window left it empty. Passing a wrong value and then `kantan` therefore still needs a human. `tests/test_password.py` covers the logic.
- **12 `F1`, `Esc`, `Ctrl+O`** — a synthetic `F1` does not become Tk's `F1` keysym; the same synthetic key also does nothing against an in-process `python app.py`, so this is a limit of the harness rather than a difference in the product. `tests/test_ui.py` covers the shortcut dispatch, and `Delete` (the one shortcut that could be delivered) was exercised above.
- **13 更新を確認** — needs a human click. `updates.check_latest()` against the published release is already recorded above.
- No clean Windows machine was used; only this development machine.

Observation filed as an issue instead of being fixed here: with a single card in the list, `Delete` removes the card as expected, but the bottom status line keeps the stale text `3 件 / 解凍できます。` while the list is already showing its empty state. `remove_job()` calls `_empty_layout()` without resetting `self.status`, unlike `clear_jobs()`. This is filed as #72; it is display-only and no file is deleted.

## 2026-10-18 v1.2.1 release verification

- The tag `v1.2.1` points at `a853b5d` (`chore: v1.2.1 を準備する`), whose only changes were `version.py` (`1.2.0` → `1.2.1`) and the version references in the README. The workflow's `Verify release commit is on main` and `Verify application version matches release tag` steps passed.
- The release run `39133812043` succeeded and produced no check-run annotations at all. The Node24 action majors moved in #64 — `actions/checkout@v7`, `actions/setup-python@v7`, `actions/upload-artifact@v7`, and `softprops/action-gh-release@v3` — therefore ran at a tag for the first time without the Node20 deprecation warning that the v1.2.0 section left open. `Test installer` and `Verify RAR in distribution executable` passed as before.
- The Release `v1.2.1` is published (neither draft nor pre-release) with two assets:
  - `KantanKaiko.exe` — 14,672,727 bytes, SHA256 `9d288091901b4fabf13323a12f6dc130646c9638af40938e8bbbe16f54de0bbf`
  - `KantanKaiko-Setup-1.2.1.exe` — 16,423,550 bytes, SHA256 `910538414a8abc502b88e83adc588b1a37f6c29dc504d290f40fe66ee4548579`
- The downloaded installer's SHA256 matched the asset digest, and installing it silently registered `DisplayVersion 1.2.1`. The installed `KantanKaiko.exe` was 14,672,727 bytes with SHA256 `9d288091…4de0bbf`, identical to the released asset. `tools\UnRAR.exe`, the Start Menu shortcut, the `KantanKaiko.Archive` Open With registration, and `%APPDATA%\KantanKaiko\settings.json` all survived the upgrade.
- #72 is fixed in the shipped build. Launching the installed 1.2.1 with `plain.zip` showed the header `ZIP・7z・RAR・TAR / v1.2.1` and `3 件 / 解凍できます。`. Pressing `Delete` returned the list to its empty state *and* the bottom line to `ファイルを選んで、解凍するだけ。`, where 1.2.0 left the stale `3 件 / 解凍できます。` behind (see the v1.2.0 section above). A second `Delete` did nothing, and closing the window exited with code 0 and left `settings.json` valid.
- The window-only pixel captures used for this check were deleted after inspection.
- The automatable parts of this record were folded into [`scripts/verify-release.ps1`](../scripts/verify-release.ps1) afterwards; its first run against `v1.2.1` passed 24 checks (published assets and digests, window placement from settings, off-screen rejection, save on close, and the update feed). Visual items — the Explorer menu, real drag-and-drop, and the installer wizard text — remain manual.

## 2026-10-19 installer wizard text (v1.2.1, captured)

The checklist's first item asks for a Japanese installer, and the earlier records left that unverified because every install here was silent. This time the published `v1.2.1` installer was started normally, with no silent flags, and only its own windows were captured with `PrintWindow(PW_RENDERFULLCONTENT)`. No desktop capture was made, and the images were deleted after inspection.

- The wizard window (class `TWizardForm`) carries the title `かんたん解凍 バージョン 1.2.1 セットアップ` — the Japanese product name and the released version.
- Its first page is `スタートメニューフォルダーの指定`: `プログラムのショートカットを作成する場所を指定してください。`, the lines `セットアップは次のスタートメニューフォルダーにプログラムのショートカットを作成します。` and `続けるには「次へ」をクリックしてください。違うフォルダーを選択するには「参照」をクリックしてください。`, the folder field `かんたん解凍`, and the buttons `次へ(N)` / `キャンセル`. Nothing was garbled.
- No elevation prompt appeared. The installer uses `PrivilegesRequired=lowest` and `consent.exe` never ran, which matches the checklist's "no administrator rights" expectation.
- Closing the wizard shows a fully Japanese confirmation, `セットアップ終了`: `セットアップ作業は完了していません。ここでセットアップを中止するとプログラムはインストールされません。` with `はい(Y)` / `いいえ(N)`.
- Cancelling left the machine as it was: the uninstall entry still reports `1.2.1` and the installed executable is still in place.
- Not driven by hand: the click-through to the end. Inno's buttons did not react to posted key messages, so the wizard was cancelled and the installer processes were stopped. That the install *completes* is evidenced by the silent install (exit 0) and by `scripts/test-installer.ps1` in CI, not by a hand-driven wizard.

## 2026-10-19 remaining manual items

After the captures above, the checklist items that still need a human are the Explorer Open With menu itself, a real Explorer drag-and-drop (the drop path uses OLE shared memory), typing into the password entry, the `F1` / `Esc` / `Ctrl+O` shortcuts, reading the installer wizard pages, and clicking the 更新を確認 button. The rest are covered by `scripts/verify-release.ps1`, `scripts/test-installer.ps1`, and the test suite.

## 2026-10-19 why the local frozen-RAR check failed (WinRAR installed)

`python tests/test_frozen_rar.py --exe dist\KantanKaiko.exe` failed on this machine while CI stayed green:

```
AssertionError: ('done', ([Entry(name='testfile.txt', size=12, is_dir=False)], False))
```

The check wants "no UnRAR at all": it sets `PATH=''`, points `ProgramFiles` / `ProgramFiles(x86)` at an empty temp directory and `KANTAN_UNRAR` at a missing file. The cause was **not** the repository's git-ignored `tools\UnRAR.exe`:

- Windows restores `ProgramFiles` to its real value for child processes, so the frozen worker still saw `C:\Program Files` and picked `C:\Program Files\WinRAR\UnRAR.exe`. Measured with two independent children (a Python child and `cmd /c`):

```
this process: ProgramFiles=C:\Users\...\kk-pf-probe2
child python: ProgramFiles = C:\Program Files                    (not patched)
child python: ProgramFiles(x86) = C:\Users\...\kk-pf-probe2       (patched)
child python: KANTAN_TESTVAR = patched-value                      (patched)
child cmd:    ProgramFiles=C:\Program Files
```

- Deleting or replacing `tools\UnRAR.exe` changed nothing (it is never the candidate that wins), and temporarily logging the search inside the frozen worker showed which path was chosen and what the process saw:

```
chosen='C:\Program Files\WinRAR\UnRAR.exe'
bases=['C:\Users\...\_MEI000058302', 'C:\gemini-desktop\unzip-tool\dist', 'C:\Users\...\_MEI000058302']
env(PF='C:\Program Files' PATH=None KANTAN='C:\...\kantan-frozen-rar-...\missing.exe')
```

`KANTAN_UNRAR` *does* reach the worker, so the fix (#80) makes an explicit `KANTAN_UNRAR` authoritative: when it is set, only that path is used; when it is missing, the guidance names it. The check no longer depends on what the machine has installed, and a mistyped `KANTAN_UNRAR` no longer falls back to a different UnRAR silently.

With the fix in a local build, the whole check passes here (a machine with WinRAR installed):

```
PASS shipped exe: Japanese guidance without UnRAR
PASS shipped exe: testfile.rar3.rar with UnRAR
PASS shipped exe: testfile.rar5.rar with UnRAR
```

The temporary logging was removed before committing; the frozen worker's search order is otherwise unchanged (`tools\UnRAR.exe` next to the exe or the bundle > WinRAR > `PATH`).

