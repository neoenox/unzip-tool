"""Regression test for #11: listing is debounced, async, and single-shot.

Covers the three acceptance points without timing flakes:
1. Password keystrokes are debounced (350ms): rapid typing schedules a
   single inspection, not one BackgroundTask per keystroke.
2. Archive switching does not double-list: `select_job()` syncs Tk vars
   under `_syncing`, so no trace re-fires and `revision` is unchanged.
3. Stale results never overwrite newer input: `_poll_listing` drops
   payloads whose revision no longer matches (`revision != job.revision`).

GUI tests need a real Tk window (Windows CI provides one).
"""
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as app_module
from app import App


class ListingDebounceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.app = App()
        self.app.withdraw()
        self.addCleanup(self.app._on_close)

    def pump(self, condition, timeout=20):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self.app.update()
            try:
                if condition():
                    return
            except Exception:
                pass
            time.sleep(0.02)
        self.fail(f"timeout: {self.app.status.get()}")

    def make_zip(self, name="one.zip"):
        src = self.base / name
        with zipfile.ZipFile(src, "w") as z:
            z.writestr("hello.txt", name)
        return src

    def test_rapid_password_typing_starts_single_listing(self):
        self.app.on_drop_files([str(self.make_zip())])
        self.pump(lambda: self.app.jobs[0].state == "ready")
        job = self.app.jobs[0]
        base_revision = job.revision

        starts = []
        real_task = app_module.BackgroundTask

        def counting_task(*args, **kwargs):
            # Capture the job revision this listing was started for.
            starts.append(job.revision)
            return real_task(*args, **kwargs)

        with mock.patch.object(app_module, "BackgroundTask", side_effect=counting_task):
            # Simulate fast typing: 5 keystrokes well inside the 350ms window.
            for ch in "abcde":
                job.pw_var.set(ch)
                self.app.update()
                time.sleep(0.02)
            # Debounce pending: no new listing task may start yet.
            pending_starts = len(starts)
            self.app.update()
            time.sleep(0.1)
            self.app.update()
            self.assertEqual(len(starts), pending_starts,
                             "listing started before debounce window elapsed")
            # After the window, exactly one listing for the latest revision.
            self.pump(lambda: len(starts) >= pending_starts + 1, timeout=20)
            time.sleep(0.1)
            self.app.update()
            self.assertEqual(len(starts), pending_starts + 1,
                             f"expected single debounced listing, got {len(starts) - pending_starts}")
            self.assertEqual(job.revision, base_revision + 5)
            self.assertEqual(starts[-1], job.revision,
                             "listing must track the latest revision")

    def test_select_job_does_not_relist(self):
        self.app.on_drop_files([str(self.make_zip("a.zip"))])
        self.pump(lambda: self.app.jobs[0].state == "ready")
        job = self.app.jobs[0]
        revision = job.revision
        with mock.patch.object(app_module, "BackgroundTask",
                               side_effect=AssertionError("must not list")) as _:
            # Re-selecting the same job only syncs Tk vars; no new list task.
            self.app.select_job(job)
            for _i in range(5):
                self.app.update()
                time.sleep(0.05)
        self.assertEqual(job.revision, revision)
        self.assertIsNone(self.app._listing)

    def test_stale_listing_result_is_dropped(self):
        self.app.on_drop_files([str(self.make_zip())])
        self.pump(lambda: self.app.jobs[0].state == "ready")
        job = self.app.jobs[0]
        old_entries = list(job.entries)
        # Simulate a stale worker finishing after newer input arrived.
        stale_revision = job.revision
        job.password = "newer"
        job.revision = stale_revision + 1
        fake_task = mock.Mock()
        fake_task.poll.return_value = [("done", ([], False))]
        self.app._listing = (fake_task, job, stale_revision)
        self.app._poll_listing()
        self.assertEqual(job.entries, old_entries,
                         "stale listing overwrote newer revision")
        # The stale slot is consumed; a re-list for the newer revision may
        # already be scheduled, but it must never target the stale revision.
        if self.app._listing is not None:
            self.assertEqual(self.app._listing[2], job.revision)
            self.assertNotEqual(self.app._listing[2], stale_revision)


if __name__ == "__main__":
    unittest.main()
