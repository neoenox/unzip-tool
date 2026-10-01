import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jobs import BackgroundTask


class JobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.archive = self.base / 'test.zip'
        with zipfile.ZipFile(self.archive, 'w') as z:
            z.writestr('hello.txt', 'hello')

    def finish(self, task):
        self.addCleanup(task.cancel)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            events = task.poll()
            for kind, payload in events:
                if kind in ('done', 'error', 'password'):
                    return kind, payload
            time.sleep(.02)
        self.fail('worker timeout')

    def test_list_is_background_task(self):
        kind, payload = self.finish(BackgroundTask('list', self.archive))
        self.assertEqual(kind, 'done')
        entries, needs_password = payload
        self.assertEqual(entries[0].name, 'hello.txt')
        self.assertFalse(needs_password)

    def test_extract_publishes_only_after_parent_accepts_result(self):
        dest = self.base / 'out'
        task = BackgroundTask('extract', self.archive, dest=dest)
        self.addCleanup(task.cancel)
        task.process.join(20)
        self.assertFalse(dest.exists())
        kind, payload = self.finish(task)
        self.assertEqual(kind, 'done')
        self.assertEqual((Path(payload) / 'hello.txt').read_text(), 'hello')

    def test_cancel_discards_even_completed_unpublished_result(self):
        dest = self.base / 'out'
        task = BackgroundTask('extract', self.archive, dest=dest)
        task.process.join(20)
        task.cancel()
        self.assertFalse(task.process.is_alive())
        self.assertFalse(dest.exists())
        self.assertFalse(list(self.base.glob('.kantan-*')))
        self.assertEqual(task.poll(), [])


if __name__ == '__main__':
    unittest.main()
