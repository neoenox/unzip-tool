import hashlib
import io
import json
import shutil
import ssl
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from updates import check_latest, _installer_asset, download_update  # noqa: E402


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

    def test_certificate_errors_get_distinct_guidance(self):
        certificate_error = ssl.SSLCertVerificationError('unable to get issuer certificate')
        curl_failure = SimpleNamespace(returncode=1, stdout=b'', stderr=b'failed')
        for failure in (certificate_error, URLError(certificate_error)):
            with patch('updates.urlopen', side_effect=failure), \
                    patch('updates.shutil.which', return_value='curl.exe'), \
                    patch('updates.subprocess.run', return_value=curl_failure):
                with self.assertRaisesRegex(ValueError, '証明書'):
                    check_latest('1.0.0')

    def test_certificate_error_falls_back_to_system_curl(self):
        body, _payload = self.release_with_asset()
        certificate_error = ssl.SSLCertVerificationError('bad cert')

        def curl_writes_to_stdout(command, stdout=None, **kwargs):
            # 実装は応答を一時ファイルへ流す (メモリに載せない)。
            stdout.write(body.getvalue())
            return SimpleNamespace(returncode=0, stderr=b'')

        with patch('updates.urlopen', side_effect=certificate_error), \
                patch('updates.shutil.which', return_value='curl.exe'), \
                patch('updates.subprocess.run', side_effect=curl_writes_to_stdout) as run:
            result = check_latest('1.9.0')
        self.assertTrue(result['newer'])
        run.assert_called_once()

    def release_with_asset(self, tag='v1.10.0'):
        payload = b'installer-bytes'
        name = f'KantanKaiko-Setup-{tag[1:]}.exe'
        release = {
            'tag_name': tag, 'draft': False, 'prerelease': False,
            'assets': [{
                'name': name,
                'browser_download_url':
                    f'https://github.com/neoenox/unzip-tool/releases/download/{tag}/{name}',
                'size': len(payload),
                'digest': 'sha256:' + hashlib.sha256(payload).hexdigest(),
            }],
        }
        return io.BytesIO(json.dumps(release).encode()), payload

    def test_installer_asset_is_limited_to_official_release(self):
        body, _payload = self.release_with_asset()
        with patch('updates.urlopen', return_value=body):
            result = check_latest('1.9.0')
        self.assertTrue(result['newer'])
        package = result['update']
        self.assertEqual(package['name'], 'KantanKaiko-Setup-1.10.0.exe')
        self.assertEqual(package['version'], '1.10.0')
        self.assertEqual(len(package['sha256']), 64)

        release = json.loads(self.release_with_asset()[0].getvalue())
        bad = dict(release['assets'][0])
        bad['browser_download_url'] = 'https://example.com/setup.exe'
        with self.assertRaisesRegex(ValueError, '公式リリース'):
            _installer_asset({**release, 'assets': [bad]}, 'v1.10.0')
        bad = dict(release['assets'][0], digest='sha256:bad')
        with self.assertRaisesRegex(ValueError, '検証情報'):
            _installer_asset({**release, 'assets': [bad]}, 'v1.10.0')

    def test_download_update_verifies_digest_and_progress(self):
        body, payload = self.release_with_asset()
        with patch('updates.urlopen', return_value=body):
            package = check_latest('1.9.0')['update']
        seen = []
        with patch('updates.urlopen', return_value=io.BytesIO(payload)):
            path = download_update(package, on_progress=lambda done, total: seen.append((done, total)))
        try:
            self.assertEqual(Path(path).read_bytes(), payload)
            self.assertEqual(seen[-1], (len(payload), len(payload)))
        finally:
            shutil.rmtree(Path(path).parent, ignore_errors=True)

        with patch('updates.urlopen', return_value=io.BytesIO(payload)):
            with self.assertRaisesRegex(ValueError, '検証に失敗'):
                download_update({**package, 'sha256': '0' * 64})
        with self.assertRaisesRegex(ValueError, '公式リリース以外'):
            download_update({**package, 'url': 'https://example.com/setup.exe'})


if __name__ == '__main__':
    unittest.main()
