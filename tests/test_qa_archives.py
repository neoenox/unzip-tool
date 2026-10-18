"""手動検証用の書庫生成（docs/manual-explorer-qa.md の準備3）が壊れていないことを確認する。

`scripts/make_qa_archives.py` を一時フォルダへ実行し、書庫の中身・暗号化・
アプリ側の読み取りを検証する。ZipCrypto と RAR は外部ツールが要るため、
作れなかった場合はその項目だけスキップする。
"""
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import py7zr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from unzipper import archive_needs_password, extract_archive, list_contents  # noqa: E402

JA_ZIP = "日本語 テスト 1.zip"
JA_ENTRIES = ["notes/deep/さらに深い.txt", "notes/メモ 1.txt", "readme.txt"]
PLAIN_ENTRIES = ["notes/deep/more.txt", "notes/memo.txt", "readme.txt"]


class QaArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="qa-archives-")
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / "archives"
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "make_qa_archives.py"), "--out", str(self.out)],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=180,
            env=dict(os.environ, PYTHONUTF8="1"),
        )
        self.assertEqual(proc.returncode, 0, f"script failed: {proc.stdout}\n{proc.stderr}")
        self.output = proc.stdout

    def test_archives_are_created(self):
        for name in (JA_ZIP, "plain.zip", "test.7z"):
            with self.subTest(archive=name):
                path = self.out / name
                self.assertTrue(path.is_file(), f"{name} が作られていない: {self.output}")
                self.assertGreater(path.stat().st_size, 0, name)

    def test_zip_contents_match_the_documented_layout(self):
        with zipfile.ZipFile(self.out / JA_ZIP) as archive:
            self.assertEqual(sorted(archive.namelist()), JA_ENTRIES)
        with zipfile.ZipFile(self.out / "plain.zip") as archive:
            self.assertEqual(sorted(archive.namelist()), PLAIN_ENTRIES)

    def test_7z_archive_is_readable(self):
        target = self.out / "test.7z"
        with py7zr.SevenZipFile(target) as archive:
            names = sorted(name.replace("\\", "/") for name in archive.getnames())
        self.assertEqual(names, PLAIN_ENTRIES)
        self.assertFalse(archive_needs_password(target))

    def test_secret_zip_is_zipcrypto_with_the_documented_password(self):
        target = self.out / "secret.zip"
        if not target.is_file():
            self.skipTest("7-Zip が見つからない環境のため ZipCrypto 書庫を作れない")
        with zipfile.ZipFile(target) as archive:
            self.assertTrue(archive.infolist()[0].flag_bits & 0x1, "ZipCryptoで暗号化されていない")
        self.assertTrue(archive_needs_password(target))
        self.assertEqual(sorted(entry.name for entry in list_contents(target)), PLAIN_ENTRIES)
        result = Path(self.tmp.name) / "extracted"
        extract_archive(target, result, password=b"kantan")
        self.assertTrue((result / "readme.txt").is_file())

    def test_documented_password_is_used(self):
        script = (ROOT / "scripts" / "make_qa_archives.py").read_text(encoding="utf-8")
        self.assertIn('SECRET_PASSWORD = "kantan"', script)
        doc = (ROOT / "docs" / "manual-explorer-qa.md").read_text(encoding="utf-8")
        self.assertIn("`kantan`", doc)


if __name__ == "__main__":
    unittest.main()
