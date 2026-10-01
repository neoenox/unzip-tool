"""Real Tk flows, including multiple archives, retry and cancellation."""
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import py7zr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import App


class UITests(unittest.TestCase):
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
            if condition():
                return
            time.sleep(.02)
        self.fail(self.app.status.get())

    def archive(self, name):
        src = self.base / name
        with zipfile.ZipFile(src, 'w') as z:
            z.writestr('folder/日本語.txt', name)
        return src

    def test_empty_and_collapsed_details(self):
        self.assertFalse(self.app._pw_visible)
        self.assertFalse(self.app.details.winfo_manager())
        self.app.on_drop_files([str(self.archive('one.zip'))])
        self.pump(lambda: self.app.jobs[0].state == 'ready')
        self.app.toggle_details()
        self.assertEqual(self.app.details.winfo_manager(), 'pack')
        self.assertEqual(self.app.tree.item(self.app.tree.get_children()[0])['text'], 'folder')

    def test_batch_extract_without_popups(self):
        self.app.on_drop_files([str(self.archive('one.zip')), str(self.archive('two.zip'))])
        self.pump(lambda: len(self.app.jobs) == 2 and all(j.state == 'ready' for j in self.app.jobs))
        with patch('tkinter.messagebox.showinfo', side_effect=AssertionError('modal')):
            self.app.start_extract()
            self.pump(lambda: all(j.state == 'done' for j in self.app.jobs))
        for job in self.app.jobs:
            self.assertTrue((Path(job.result) / 'folder' / '日本語.txt').is_file())

    def test_password_retry_and_clear_on_selection(self):
        src = self.base / 'secret.7z'
        with py7zr.SevenZipFile(src, 'w', password='secret') as z:
            z.writestr('hello', 'hello.txt')
        self.app.on_drop_files([str(src)])
        self.pump(lambda: self.app._pw_visible)
        self.app.password_var.set('wrong')
        self.app.start_extract()
        self.pump(lambda: not self.app.busy and self.app.jobs[0].state == 'password')
        self.app.password_var.set('secret')
        self.app.start_extract()
        self.pump(lambda: self.app.jobs[0].state == 'done')
        self.assertEqual((Path(self.app.jobs[0].result) / 'hello.txt').read_text(), 'hello')
        self.app.on_drop_files([str(self.archive('plain.zip'))])
        self.assertEqual(self.app.password_var.get(), '')
        self.assertFalse(self.app._pw_visible)

    def test_cancel_and_restart(self):
        self.app.on_drop_files([str(self.archive('one.zip'))])
        self.pump(lambda: self.app.jobs[0].state == 'ready')
        self.app.start_extract()
        self.app.cancel_extract()
        self.assertFalse((self.base / 'one').exists())
        self.assertFalse(list(self.base.glob('.kantan-*')))
        self.app.start_extract()
        self.pump(lambda: self.app.jobs[0].state == 'done')

    def test_old_listing_cannot_replace_current_selection(self):
        self.app.on_drop_files([str(self.archive('one.zip'))])
        self.app.on_drop_files([str(self.archive('two.zip'))])
        self.pump(lambda: all(j.state == 'ready' for j in self.app.jobs))
        self.assertEqual(self.app.selected.archive.name, 'two.zip')
        self.assertEqual(self.app.archive_var.get(), str(self.base / 'two.zip'))

    def test_encrypted_headers_allow_password_retry(self):
        src = self.base / 'headers.7z'
        with py7zr.SevenZipFile(src, 'w', password='secret', header_encryption=True) as z:
            z.writestr('hidden', 'hidden.txt')
        self.app.on_drop_files([str(src)])
        self.pump(lambda: self.app._pw_visible)
        self.app.password_var.set('wrong')
        self.app.start_extract()
        self.pump(lambda: not self.app.busy)
        self.assertEqual(self.app.jobs[0].state, 'password')
        self.app.password_var.set('secret')
        self.app.start_extract()
        self.pump(lambda: self.app.jobs[0].state == 'done')
        self.assertEqual((Path(self.app.jobs[0].result) / 'hidden.txt').read_text(), 'hidden')

    def test_open_result_uses_actual_collision_destination(self):
        src = self.archive('one.zip')
        existing = self.base / 'one'
        existing.mkdir()
        self.app.on_drop_files([str(src)])
        self.pump(lambda: self.app.jobs[0].state == 'ready')
        self.app.start_extract()
        self.pump(lambda: self.app.jobs[0].state == 'done')
        job = self.app.jobs[0]
        with patch('app.os.startfile') as open_folder:
            self.app.open_result(job)
            open_folder.assert_called_once_with(job.result)
        self.assertEqual(Path(job.result).name, 'one (2)')

    def test_minimum_window_keeps_actions_visible_with_details_and_password(self):
        self.app.on_drop_files([str(self.archive('one.zip'))])
        self.pump(lambda: self.app.jobs[0].state == 'ready')
        self.app.toggle_details()
        self.app._show_password_row()
        self.app.geometry('600x640')
        self.app.deiconify()
        self.app.update()
        for button in (self.app.extract_btn, self.app.cancel_btn):
            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                 self.app.winfo_rooty() + self.app.winfo_height())


if __name__ == '__main__':
    unittest.main()
