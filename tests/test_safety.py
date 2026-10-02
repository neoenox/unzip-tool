"""Extraction must never overwrite or publish partial results."""
import io
import os
import stat
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from unzipper import PasswordRequiredError, clean_staging, default_dest_for, extract_archive


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def archive(self, entries):
        src = self.base / 'sample.zip'
        with zipfile.ZipFile(src, 'w') as z:
            for name, data in entries:
                z.writestr(name, data)
        return src

    def test_existing_destination_is_preserved(self):
        dest = self.base / 'out'
        dest.mkdir()
        (dest / 'a.txt').write_text('original')
        result = extract_archive(self.archive([('a.txt', 'new')]), dest)
        self.assertEqual((dest / 'a.txt').read_text(), 'original')
        self.assertNotEqual(result, dest)
        self.assertEqual((result / 'a.txt').read_text(), 'new')

    def test_unsafe_names_leave_no_output(self):
        for name in ('../escape', '/absolute', 'C:/escape', 'CON.txt',
                     'file:stream', 'trailing. ', 'sub/../escape'):
            with self.subTest(name=name):
                src = self.archive([('good.txt', 'ok'), (name, 'evil')])
                with self.assertRaises(ValueError):
                    extract_archive(src, self.base / 'out')
                self.assertFalse((self.base / 'out').exists())
                self.assertFalse(list(self.base.glob('.kantan-*')))

    def test_case_collision_and_file_parent_rejected(self):
        for names in (['A.txt', 'a.txt'], ['a', 'a/b.txt'], ['a/b.txt', 'A']):
            with self.subTest(names=names):
                with self.assertRaises(ValueError):
                    extract_archive(self.archive([(n, 'x') for n in names]), self.base / 'out')
                self.assertFalse((self.base / 'out').exists())

    def test_crc_failure_cleans_staging(self):
        src = self.archive([('a', 'unique payload'), ('b', 'other')])
        src.write_bytes(src.read_bytes().replace(b'unique payload', b'broken payload'))
        with self.assertRaises(zipfile.BadZipFile):
            extract_archive(src, self.base / 'out')
        self.assertFalse((self.base / 'out').exists())
        self.assertFalse(list(self.base.glob('.kantan-*')))

    def test_tar_link_rejected(self):
        src = self.base / 'link.tar'
        with tarfile.open(src, 'w') as tf:
            entry = tarfile.TarInfo('good')
            entry.size = 2
            tf.addfile(entry, io.BytesIO(b'ok'))
            link = tarfile.TarInfo('link')
            link.type = tarfile.SYMTYPE
            link.linkname = '../outside'
            tf.addfile(link)
        with self.assertRaises(ValueError):
            extract_archive(src, self.base / 'out')
        self.assertFalse((self.base / 'out').exists())

    def test_zip_link_rejected(self):
        src = self.base / 'link.zip'
        with zipfile.ZipFile(src, 'w') as z:
            info = zipfile.ZipInfo('link')
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(info, '../escape')
        with self.assertRaises(ValueError):
            extract_archive(src, self.base / 'out')
        self.assertFalse((self.base / 'out').exists())

    def test_readonly_staging_is_cleaned(self):
        staging = self.base / '.kantan-readonly'
        staging.mkdir()
        file = staging / 'file.txt'
        file.write_text('test')
        os.chmod(file, stat.S_IREAD)
        clean_staging(staging)
        self.assertFalse(staging.exists())

    def test_suffix_only_archive_has_dedicated_destination(self):
        self.assertEqual(default_dest_for(self.base / '.zip').name, '解凍したファイル')

    def test_progress_failure_cleans_partial_result(self):
        def fail(_done, _total):
            raise RuntimeError('injected failure')
        with self.assertRaises(RuntimeError):
            extract_archive(self.archive([('a', 'ok'), ('b', 'ok')]), self.base / 'out', fail)
        self.assertFalse((self.base / 'out').exists())
        self.assertFalse(list(self.base.glob('.kantan-*')))

    def test_zip_password_failure_cleans_staging_and_retries(self):
        src = Path(__file__).parent / 'vendor' / 'pw.zip'
        for password in (None, b'wrong'):
            with self.subTest(password=password):
                with self.assertRaises(PasswordRequiredError):
                    extract_archive(src, self.base / 'out', password=password)
                self.assertFalse((self.base / 'out').exists())
                self.assertFalse(list(self.base.glob('.kantan-*')))
        result = extract_archive(src, self.base / 'out', password=b'testpw')
        self.assertEqual((result / 'hello.txt').read_text(), 'hello pw')


if __name__ == '__main__':
    unittest.main()
