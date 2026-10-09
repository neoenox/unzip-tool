"""Real Tk flows, including multiple archives, retry and cancellation."""
import sys
import errno
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import py7zr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import App, main


class UITests(unittest.TestCase):
    def test_shell_launch_passes_paths_without_extracting(self):
        paths = ['C:/日本語 フォルダ/archive.zip', 'C:/second.7z']
        with patch('app.App') as constructor, patch('app.multiprocessing.freeze_support'):
            main(paths)
        constructor.return_value.on_drop_files.assert_called_once_with(paths)
        constructor.return_value.start_extract.assert_not_called()
        constructor.return_value.mainloop.assert_called_once()

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
        self.assertIsNone(self.app._updating)
        self.app.on_drop_files([str(self.archive('one.zip'))])
        self.pump(lambda: self.app.jobs[0].state == 'ready')
        job = self.app.jobs[0]
        self.assertFalse(job.pw_frame.winfo_manager())
        self.assertFalse(job.details_wrap.winfo_manager())
        job.details_btn.invoke()
        self.app.update()
        self.assertEqual(job.details_wrap.winfo_manager(), 'pack')
        self.assertEqual(job.tree.item(job.tree.get_children()[0])['text'], 'folder')

    def test_manual_update_check_and_official_release_link(self):
        from unittest.mock import Mock
        task = Mock()
        task.poll.return_value = [('done', {'newer': True, 'version': '1.2.0',
                                           'url': 'https://github.com/neoenox/unzip-tool/releases/tag/v1.2.0'})]
        with patch('app.BackgroundTask', return_value=task) as constructor:
            self.app.check_updates()
        constructor.assert_called_once_with('update', '')
        self.app._poll_update()
        self.assertEqual(self.app.update_btn.cget('text'), '新版を開く')
        with patch('app.webbrowser.open') as browser:
            self.app.check_updates()
        browser.assert_called_once_with('https://github.com/neoenox/unzip-tool/releases/tag/v1.2.0')

    def test_failed_update_can_be_retried(self):
        from unittest.mock import Mock
        task = Mock()
        task.poll.return_value = [('error', 'offline')]
        with patch('app.BackgroundTask', return_value=task):
            self.app.check_updates()
        self.app._poll_update()
        self.assertEqual(str(self.app.update_btn.cget('state')), 'normal')
        self.assertIsNone(self.app._updating)
        self.assertIn('再試行', self.app.update_text.get())

    def test_card_click_selects_job(self):
        self.app.on_drop_files([str(self.archive('one.zip')), str(self.archive('two.zip'))])
        self.pump(lambda: all(j.state == 'ready' for j in self.app.jobs))
        first, second = self.app.jobs
        self.assertIs(self.app.selected, second)
        first.message.event_generate('<Button-1>')
        self.app.update()
        self.assertIs(self.app.selected, first)
        second.summary.event_generate('<Button-1>')
        self.app.update()
        self.assertIs(self.app.selected, second)

    def test_corrupt_archive_does_not_block_next_archive(self):
        broken = self.base / 'broken.zip'
        broken.write_bytes(b'not a zip')
        self.app.on_drop_files([str(broken), str(self.archive('good.zip'))])
        self.pump(lambda: all(j.state != 'scanning' for j in self.app.jobs))
        self.assertIn('壊れている', self.app.jobs[0].message.cget('text'))
        self.assertEqual(self.app.jobs[0].summary.cget('text'), '内容を確認できません')
        self.app.start_extract()
        self.pump(lambda: not self.app.busy)
        self.assertEqual(self.app.jobs[1].state, 'done')

    def test_disk_full_during_task_start_has_japanese_guidance(self):
        self.app.on_drop_files([str(self.archive('one.zip'))])
        self.pump(lambda: self.app.jobs[0].state == 'ready')
        with patch('app.BackgroundTask', side_effect=OSError(errno.ENOSPC, 'No space left')):
            self.app.start_extract()
        self.assertFalse(self.app.busy)
        self.assertIn('空き容量', self.app.jobs[0].message.cget('text'))

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
        job = self.app.jobs[0]
        self.pump(lambda: job.pw_frame.winfo_manager())
        job.pw_var.set('wrong')
        self.app.start_extract()
        self.pump(lambda: not self.app.busy and job.state == 'password')
        job.pw_var.set('secret')
        self.app.start_extract()
        self.pump(lambda: job.state == 'done')
        self.assertEqual((Path(job.result) / 'hello.txt').read_text(), 'hello')
        self.assertEqual(job.pw_var.get(), '')
        self.assertFalse(job.pw_frame.winfo_manager())

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
        job = self.app.jobs[0]
        self.pump(lambda: job.pw_frame.winfo_manager())
        job.pw_var.set('wrong')
        self.app.start_extract()
        self.pump(lambda: not self.app.busy)
        self.assertEqual(job.state, 'password')
        job.pw_var.set('secret')
        self.app.start_extract()
        self.pump(lambda: job.state == 'done')
        self.assertEqual((Path(job.result) / 'hidden.txt').read_text(), 'hidden')

    def test_open_result_uses_actual_collision_destination(self):
        src = self.archive('one.zip')
        existing = self.base / 'one'
        existing.mkdir()
        self.app.on_drop_files([str(src)])
        self.pump(lambda: self.app.jobs[0].state == 'ready')
        self.app.start_extract()
        self.pump(lambda: self.app.jobs[0].state == 'done')
        job = self.app.jobs[0]
        with patch('app.os.startfile', create=True) as open_folder:
            self.app.open_result(job)
            open_folder.assert_called_once_with(job.result)
        self.assertEqual(Path(job.result).name, 'one (2)')

    def test_extract_tracks_progress_counts(self):
        src = self.base / 'multi.zip'
        with zipfile.ZipFile(src, 'w') as z:
            for i in range(3):
                z.writestr(f'file{i}.txt', f'data{i}')
        self.app.on_drop_files([str(src)])
        self.pump(lambda: self.app.jobs[0].state == 'ready')
        job = self.app.jobs[0]
        self.app.start_extract()
        self.pump(lambda: job.state == 'done')
        self.assertEqual(job.byte_total, 15)  # 5B x 3 (バイト単位)
        self.assertEqual(job.byte_done, 15)
        self.assertTrue(job.last_file)

    def test_remove_single_card(self):
        self.app.on_drop_files([str(self.archive('one.zip')), str(self.archive('two.zip'))])
        self.pump(lambda: all(j.state == 'ready' for j in self.app.jobs))
        first = self.app.jobs[0]
        self.app.remove_job(first)
        self.app.update()
        self.assertEqual(len(self.app.jobs), 1)
        self.assertIs(self.app.selected, self.app.jobs[0])

    def test_retry_failed_job(self):
        broken = self.base / 'broken.zip'
        broken.write_bytes(b'not a zip')
        self.app.on_drop_files([str(broken)])
        self.pump(lambda: self.app.jobs[0].state == 'failed')
        job = self.app.jobs[0]
        self.app.update()
        self.assertTrue(job.retry_btn.winfo_manager())
        job.retry_btn.invoke()
        self.pump(lambda: not self.app.busy and job.state == 'failed')

    def test_state_badge_and_overall_bar(self):
        self.app.on_drop_files([str(self.archive('one.zip'))])
        self.pump(lambda: self.app.jobs[0].state == 'ready')
        job = self.app.jobs[0]
        self.assertEqual(job.state_badge.cget('text'), '解凍できます')
        job.state = 'failed'
        self.app._sync_card_chrome(job)
        self.assertEqual(job.state_badge.cget('text'), '失敗')
        self.assertEqual(job.fmt_badge.cget('text'), 'ZIP')
        self.app._extract_total = 2
        self.app.busy = True
        self.app._sync_overall()
        self.app.update()
        self.assertTrue(self.app.overall_frame.winfo_manager())
        self.assertEqual(self.app.overall_label.cget('text'), '全体 0/2')
        self.app.busy = False
        self.app._sync_overall()
        self.app.update()
        self.assertFalse(self.app.overall_frame.winfo_manager())

    def test_steps_indicator_tracks_progress(self):
        labels = self.app.step_labels
        self.assertEqual(len(labels), 3)
        self.assertEqual(labels[0].cget('foreground'), '#1d4ed8')
        self.app.on_drop_files([str(self.archive('one.zip'))])
        self.pump(lambda: self.app.jobs[0].state == 'ready')
        self.assertEqual(labels[2].cget('foreground'), '#1d4ed8')
        self.assertEqual(labels[0].cget('foreground'), '#94a3b8')

    def test_minimum_window_keeps_actions_visible_with_details_and_password(self):
        self.app.on_drop_files([str(self.archive('one.zip'))])
        self.pump(lambda: self.app.jobs[0].state == 'ready')
        job = self.app.jobs[0]
        job.details_btn.invoke()
        job.needs_password = True
        self.app._sync_card_pw_row(job)
        self.app.update()
        self.assertTrue(job.pw_frame.winfo_manager())
        self.app.geometry('600x640')
        self.app.deiconify()
        self.app.update()
        for button in (self.app.extract_btn, self.app.cancel_btn):
            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                 self.app.winfo_rooty() + self.app.winfo_height())


if __name__ == '__main__':
    unittest.main()
