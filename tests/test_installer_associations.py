"""インストーラーのファイル関連付け定義を検証する。"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ISS = (ROOT / 'installer' / 'KantanKaiko.iss').read_text(encoding='utf-8-sig')

SUFFIXES = ('.zip', '.7z', '.rar', '.tar', '.gz', '.tgz', '.bz2', '.tbz', '.xz', '.txz')


class InstallerAssociationTests(unittest.TestCase):
    def test_open_with_is_registered_for_all_suffixes(self):
        for suffix in SUFFIXES:
            with self.subTest(suffix=suffix):
                self.assertIn(
                    f'Subkey: "Software\\Classes\\{suffix}\\OpenWithProgids"', ISS)

    def test_default_association_is_opt_in(self):
        task = next(line for line in ISS.splitlines()
                    if line.startswith('Name: "defaultassoc"'))
        self.assertIn('Flags: unchecked', task)
        for suffix in SUFFIXES:
            with self.subTest(suffix=suffix):
                self.assertIn(
                    f'Subkey: "Software\\Classes\\{suffix}"; ValueType: string; '
                    'ValueName: ""; ValueData: "KantanKaiko.Archive"; Tasks: defaultassoc',
                    ISS)


if __name__ == '__main__':
    unittest.main()
