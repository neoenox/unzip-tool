"""Fail immediately if any unit, format, or real Tk integration suite fails."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    # 実ユーザーの設定ファイルを触らないようにする (#24)。
    settings_dir = tempfile.mkdtemp(prefix='kantan-settings-')
    environment = dict(os.environ, PYTHONUTF8='1', UNZIPTOOL_NO_BELL='1',
                       KANTAN_SETTINGS_DIR=settings_dir)
    for suite in ('test_safety.py', 'test_settings.py', 'test_unrar_policy.py', 'test_updates.py',
                  'test_jobs.py', 'test_ui.py', 'test_password.py', 'test_listing_debounce.py',
                  'test_7z.py', 'test_rar.py', 'test_e2e.py', 'test_xproc_dnd.py'):
        print(f'Running {suite}', flush=True)
        subprocess.run([sys.executable, str(root / 'tests' / suite)],
                       cwd=root, env=environment, check=True, timeout=120)


if __name__ == '__main__':
    main()
