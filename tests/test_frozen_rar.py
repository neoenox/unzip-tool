"""Use the shipped application's multiprocessing entry point, not Python workers."""
import argparse
import multiprocessing
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jobs import BackgroundTask


def finish(task):
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            for kind, payload in task.poll():
                if kind in ('done', 'error', 'password'):
                    return kind, payload
            time.sleep(.02)
        raise AssertionError('Frozen worker timed out')
    finally:
        task.cancel()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', required=True)
    parser.add_argument('--unrar')
    args = parser.parse_args()
    executable = Path(args.exe).resolve()
    assert executable.is_file()
    multiprocessing.set_executable(str(executable))
    vendor = Path(__file__).parent / 'vendor'
    with tempfile.TemporaryDirectory(prefix='kantan-frozen-rar-') as directory:
        base = Path(directory)
        # sys.frozen makes the launcher use --multiprocessing-fork, which the
        # actual KantanKaiko.exe handles through freeze_support().
        missing = {'PATH': '', 'ProgramFiles': str(base), 'ProgramFiles(x86)': str(base),
                   'KANTAN_UNRAR': str(base / 'missing.exe')}
        with patch.object(sys, 'frozen', True, create=True), patch.dict(os.environ, missing):
            task = BackgroundTask('list', vendor / 'testfile.rar5.rar')
        kind, message = finish(task)
        assert kind == 'error' and 'UnRAR' in message, (kind, message)
        print('PASS shipped exe: Japanese guidance without UnRAR')
        if args.unrar:
            tool = Path(args.unrar).resolve()
            assert tool.is_file()
            for name in ('testfile.rar3.rar', 'testfile.rar5.rar'):
                with patch.object(sys, 'frozen', True, create=True), patch.dict(os.environ, {'KANTAN_UNRAR': str(tool)}):
                    task = BackgroundTask('extract', vendor / name, dest=base / name)
                kind, payload = finish(task)
                assert kind == 'done', (kind, payload)
                assert (Path(payload) / 'testfile.txt').read_text() == 'Testing 123\n'
                print(f'PASS shipped exe: {name} with UnRAR')


if __name__ == '__main__':
    main()
