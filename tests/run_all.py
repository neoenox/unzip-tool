"""Fail immediately if any unit, format, or real Tk integration suite fails."""
import os
import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    environment = dict(os.environ, PYTHONUTF8='1')
    for suite in ('test_safety.py', 'test_jobs.py', 'test_ui.py', 'test_7z.py',
                  'test_rar.py', 'test_e2e.py', 'test_xproc_dnd.py'):
        print(f'Running {suite}', flush=True)
        subprocess.run([sys.executable, str(root / 'tests' / suite)],
                       cwd=root, env=environment, check=True, timeout=120)


if __name__ == '__main__':
    main()
