"""保存設定 (#24) の読み書き・検証。Tk を必要としない。"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import settings


class SettingsFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.path = self.base / 'settings.json'

    def test_missing_file_returns_defaults(self):
        loaded = settings.Settings.load(self.path)
        self.assertEqual(loaded.geometry, '')
        self.assertEqual(loaded.last_dest, '')

    def test_round_trip_keeps_japanese_path(self):
        dest = self.base / '日本語 フォルダ'
        dest.mkdir()
        written = settings.Settings(geometry='820x700+40+40', last_dest=str(dest))
        self.assertTrue(written.save(self.path))
        loaded = settings.Settings.load(self.path)
        self.assertEqual(loaded.geometry, '820x700+40+40')
        self.assertEqual(loaded.last_dest, str(dest))
        self.assertIn('日本語 フォルダ', self.path.read_text(encoding='utf-8'))

    def test_corrupt_file_is_ignored(self):
        self.path.write_text('{not json', encoding='utf-8')
        self.assertEqual(settings.Settings.load(self.path), settings.Settings())

    def test_non_object_file_is_ignored(self):
        self.path.write_text('[1, 2, 3]', encoding='utf-8')
        self.assertEqual(settings.Settings.load(self.path), settings.Settings())

    def test_wrong_types_are_dropped(self):
        self.path.write_text(json.dumps({'geometry': 5, 'last_dest': ['x']}), encoding='utf-8')
        loaded = settings.Settings.load(self.path)
        self.assertEqual(loaded.geometry, '')
        self.assertEqual(loaded.last_dest, '')

    def test_small_or_broken_geometry_is_dropped(self):
        for geometry in ('1x1+0+0', '600x640+0+0', '820x700+0', 'wide', ''):
            with self.subTest(geometry=geometry):
                self.path.write_text(json.dumps({'geometry': geometry}), encoding='utf-8')
                self.assertEqual(settings.Settings.load(self.path).geometry, '')

    def test_valid_geometry_is_kept(self):
        for geometry in ('820x700', '820x700+40+40', '1920x1080-100-50'):
            with self.subTest(geometry=geometry):
                self.path.write_text(json.dumps({'geometry': geometry}), encoding='utf-8')
                self.assertEqual(settings.Settings.load(self.path).geometry, geometry)

    def test_save_failure_is_reported_not_raised(self):
        blocker = self.base / 'not-a-folder'
        blocker.write_text('x', encoding='utf-8')
        self.assertFalse(settings.Settings(geometry='820x700').save(blocker / 'nested' / 'settings.json'))

    def test_save_leaves_no_temporary_file(self):
        settings.Settings(geometry='820x700').save(self.path)
        self.assertEqual([p.name for p in self.base.iterdir()], ['settings.json'])


class GeometryTests(unittest.TestCase):
    def test_parse_geometry(self):
        self.assertEqual(settings.parse_geometry('820x700+40+40'), (820, 700, 40, 40))
        self.assertEqual(settings.parse_geometry('820x700'), (820, 700, None, None))
        self.assertIsNone(settings.parse_geometry('820x700+40'))
        self.assertIsNone(settings.parse_geometry(''))

    def test_valid_geometry_requires_minimum_size(self):
        self.assertTrue(settings.valid_geometry('820x700+40+40'))
        self.assertTrue(settings.valid_geometry('640x560'))
        self.assertFalse(settings.valid_geometry('639x560'))
        self.assertFalse(settings.valid_geometry('820x559'))

    def test_offscreen_geometry_is_rejected(self):
        area = (0, 0, 1920, 1080)
        self.assertTrue(settings.placeable_geometry('820x700+100+100', area))
        self.assertTrue(settings.placeable_geometry('820x700', area))
        # 右へ寄りすぎ（画面内に80px未満しか残らない）
        self.assertFalse(settings.placeable_geometry('820x700+1880+100', area))
        # 下へ寄りすぎ（タイトルバーが画面外）
        self.assertFalse(settings.placeable_geometry('820x700+100+1070', area))

    def test_negative_coordinates_on_left_monitor_are_placeable(self):
        area = (-1920, 0, 3840, 1080)
        self.assertTrue(settings.placeable_geometry('820x700-1000+100', area))

    def test_virtual_screen_does_not_raise(self):
        area = settings.virtual_screen()
        self.assertTrue(area is None or len(area) == 4)


class ConfigDirTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def _restore_env(self, key, previous):
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous

    def test_override_directory_wins(self):
        previous = os.environ.get(settings.ENV_DIR)
        os.environ[settings.ENV_DIR] = str(self.base)
        self.addCleanup(self._restore_env, settings.ENV_DIR, previous)
        self.assertEqual(settings.config_dir(), self.base)
        self.assertEqual(settings.settings_path(), self.base / 'settings.json')

    def test_appdata_is_used_by_default(self):
        previous_dir = os.environ.pop(settings.ENV_DIR, None)
        previous_appdata = os.environ.get('APPDATA')
        os.environ['APPDATA'] = r'C:\Users\tester\AppData\Roaming'
        self.addCleanup(self._restore_env, settings.ENV_DIR, previous_dir)
        self.addCleanup(self._restore_env, 'APPDATA', previous_appdata)
        self.assertEqual(settings.config_dir(),
                         Path(r'C:\Users\tester\AppData\Roaming') / 'KantanKaiko')


if __name__ == '__main__':
    unittest.main()
