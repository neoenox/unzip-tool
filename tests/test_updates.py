import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from updates import check_latest


class UpdateTests(unittest.TestCase):
    def response(self, tag):
        return io.BytesIO(json.dumps({'tag_name': tag, 'draft': False, 'prerelease': False}).encode())

    def test_new_version_and_safe_official_url(self):
        with patch('updates.urlopen', return_value=self.response('v1.10.0')):
            result = check_latest('1.9.0')
        self.assertTrue(result['newer'])
        self.assertEqual(result['url'], 'https://github.com/neoenox/unzip-tool/releases/tag/v1.10.0')

    def test_equal_and_older_versions(self):
        for tag in ('v1.9.0', 'v1.8.9'):
            with patch('updates.urlopen', return_value=self.response(tag)):
                self.assertFalse(check_latest('1.9.0')['newer'])

    def test_bad_tags_and_network_errors_have_guidance(self):
        for tag in ('https://example.com', 'v1.0.0-beta', 'v1.0'):
            with patch('updates.urlopen', return_value=self.response(tag)):
                with self.assertRaises(ValueError):
                    check_latest('1.0.0')
        with patch('updates.urlopen', side_effect=URLError('offline')):
            with self.assertRaisesRegex(ValueError, '接続'):
                check_latest('1.0.0')


if __name__ == '__main__':
    unittest.main()
