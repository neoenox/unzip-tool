import sys
import tempfile
import subprocess
import time
import types
import unittest
from unittest import mock
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import jobs
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

    def large_archive(self):
        block = b'large archive test\n' * 58254
        with zipfile.ZipFile(self.archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:
            with z.open('large.bin', 'w') as member:
                for _ in range(256):
                    member.write(block)
        return len(block) * 256

    def test_large_file_streams_to_disk(self):
        size = self.large_archive()
        kind, payload = self.finish(BackgroundTask('extract', self.archive, dest=self.base / 'large'))
        self.assertEqual(kind, 'done')
        self.assertEqual((Path(payload) / 'large.bin').stat().st_size, size)

    def test_cancel_after_large_file_has_started_writing(self):
        self.large_archive()
        task = BackgroundTask('extract', self.archive, dest=self.base / 'large')
        self.addCleanup(task.cancel)
        deadline = time.monotonic() + 20
        partial = task.staging / 'large.bin'
        while time.monotonic() < deadline:
            if partial.exists() and partial.stat().st_size > 0:
                break
            time.sleep(.002)
        self.assertTrue(partial.exists())
        self.assertGreater(partial.stat().st_size, 0)
        self.assertTrue(task.process.is_alive())
        task.cancel()
        self.assertFalse(task.process.is_alive())
        self.assertFalse((self.base / 'large').exists())
        self.assertFalse(list(self.base.glob('.kantan-*')))

    def test_corrupt_archive_returns_actionable_error(self):
        self.archive.write_bytes(b'not a zip file')
        kind, message = self.finish(BackgroundTask('list', self.archive))
        self.assertEqual(kind, 'error')
        self.assertIn('壊れている', message)

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

    def test_live_cancel_stops_process_and_cleans_staging(self):
        task = BackgroundTask('extract', self.archive, dest=self.base / 'out')
        self.assertTrue(task.process.is_alive())
        task.cancel()
        self.assertFalse(task.process.is_alive())
        self.assertFalse(list(self.base.glob('.kantan-*')))
        self.assertFalse((self.base / 'out').exists())

    def test_cancel_cleans_up_when_taskkill_times_out(self):
        self.large_archive()
        task = BackgroundTask('extract', self.archive, dest=self.base / 'large')
        self.addCleanup(task.cancel)
        self.assertTrue(task.process.is_alive())
        timeout = subprocess.TimeoutExpired(['taskkill'], 10)
        with mock.patch.object(jobs, 'os', types.SimpleNamespace(name='nt')), \
                mock.patch.object(jobs.subprocess, 'CREATE_NO_WINDOW', 0x08000000, create=True), \
                mock.patch.object(jobs.subprocess, 'run', side_effect=timeout) as run:
            task.cancel()
        run.assert_called_once()
        self.assertTrue(task.finished)
        self.assertFalse(task.process.is_alive())
        self.assertFalse(list(self.base.glob('.kantan-*')))
        self.assertFalse((self.base / 'large').exists())
        self.assertEqual(task.poll(), [])

    def test_cancel_cleans_up_even_if_stopping_raises(self):
        task = BackgroundTask('extract', self.archive, dest=self.base / 'out')
        process = task.process
        self.addCleanup(lambda: (process.kill(), process.join(5)))
        with mock.patch.object(task, '_stop_process', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                task.cancel()
        self.assertTrue(task.finished)
        self.assertTrue(task.connection.closed)
        self.assertFalse(list(self.base.glob('.kantan-*')))

    def test_windows_taskkill_missing_falls_back_to_terminate(self):
        task = BackgroundTask.__new__(BackgroundTask)
        task.process = mock.Mock()
        task.process.pid = 12345
        task.process.is_alive.side_effect = [True, False]
        with mock.patch.object(jobs, 'os', types.SimpleNamespace(name='nt')), \
                mock.patch.object(jobs.subprocess, 'CREATE_NO_WINDOW', 0x08000000, create=True), \
                mock.patch.object(jobs.subprocess, 'run', side_effect=OSError('not installed')):
            task._stop_process()
        task.process.terminate.assert_called_once()
        task.process.join.assert_called_once_with(5)
        task.process.kill.assert_not_called()

    def test_cancel_twice_does_not_repeat_cleanup(self):
        task = BackgroundTask('list', self.archive)
        self.addCleanup(task.cancel)
        task.cancel()
        assert task.finished
        assert task.connection.closed
        task.cancel()  # no second close/terminate for a completed task
        assert task.finished

    def test_unexpected_worker_exit_reports_error(self):
        task = BackgroundTask('extract', self.archive, dest=self.base / 'out')
        task.process.terminate()
        task.process.join(5)
        kind, _payload = self.finish(task)
        self.assertEqual(kind, 'error')
        self.assertFalse(list(self.base.glob('.kantan-*')))


if __name__ == '__main__':
    unittest.main()
