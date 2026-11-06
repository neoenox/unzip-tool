"""zipエントリ名の文字コード判定 (UTF-8フラグ無しのUTF-8 / cp932) の回帰テスト。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from unzipper import _decode_zip_name

NAMES = ["ファイル", "日本語フォルダ", "新しいフォルダ", "報告書", "写真",
         "プログラム", "メモ.txt", "ふ", "会議議事録", "データ/資料.txt"]


def as_python_reads_without_flag(data: bytes) -> str:
    # zipfile は UTF-8フラグ無しの名前を cp437 として読む
    return data.decode("cp437")


class ZipNameTests(unittest.TestCase):
    def test_utf8_without_flag_is_not_misread_as_cp932(self):
        for name in NAMES:
            with self.subTest(name=name):
                raw = as_python_reads_without_flag(name.encode("utf-8"))
                self.assertEqual(_decode_zip_name(raw), name)

    def test_cp932_without_flag_is_restored(self):
        for name in NAMES:
            with self.subTest(name=name):
                raw = as_python_reads_without_flag(name.encode("cp932"))
                self.assertEqual(_decode_zip_name(raw), name)

    def test_ascii_and_already_decoded_names_are_untouched(self):
        self.assertEqual(_decode_zip_name("readme.txt"), "readme.txt")
        self.assertEqual(_decode_zip_name("日本語"), "日本語")


if __name__ == "__main__":
    unittest.main()
