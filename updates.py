"""Manual, bounded checks against the application's official release feed."""
import hashlib
import io
import json
import re
import shutil
import ssl
import subprocess
import tempfile
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from version import VERSION

API_URL = 'https://api.github.com/repos/neoenox/unzip-tool/releases/latest'
RELEASE_URL = 'https://github.com/neoenox/unzip-tool/releases'
DOWNLOAD_PREFIX = f'{RELEASE_URL}/download/'
MAX_UPDATE_BYTES = 150 * 1024 * 1024


def _is_certificate_error(error: Exception) -> bool:
    """urlopen raises SSLCertVerificationError directly or wrapped in URLError."""
    if isinstance(error, ssl.SSLCertVerificationError):
        return True
    return isinstance(getattr(error, 'reason', None), ssl.SSLCertVerificationError)


def _open_url(url: str, headers: dict, timeout: int):
    """証明書エラー時に Windows の curl（システム証明書）で再試行する。"""
    try:
        return urlopen(Request(url, headers=headers), timeout=timeout)
    except (URLError, OSError) as error:
        if not _is_certificate_error(error):
            raise
        curl = shutil.which('curl.exe') or shutil.which('curl')
        if not curl:
            raise
        command = [curl, '--fail', '--silent', '--show-error', '--location',
                   '--max-time', str(timeout)]
        for name, value in headers.items():
            command += ['-H', f'{name}: {value}']
        command.append(url)
        try:
            result = subprocess.run(command, capture_output=True, timeout=timeout + 10)
        except (OSError, subprocess.SubprocessError):
            raise error
        if result.returncode != 0:
            raise error
        return io.BytesIO(result.stdout)


def version_number(value):
    if not isinstance(value, str) or not re.fullmatch(r'v?\d+\.\d+\.\d+', value):
        raise ValueError('更新情報のバージョンを確認できませんでした。後でもう一度お試しください。')
    return tuple(int(part) for part in value.removeprefix('v').split('.'))


def _fetch_release():
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': f'KantanKaiko/{VERSION}'}
    try:
        with _open_url(API_URL, headers, 8) as response:
            raw = response.read(256 * 1024 + 1)
        if len(raw) > 256 * 1024:
            raise ValueError('更新情報が大きすぎます。後でもう一度お試しください。')
        release = json.loads(raw)
    except (URLError, TimeoutError, OSError) as error:
        if _is_certificate_error(error):
            raise ValueError(
                '更新情報を取得できません。証明書やプロキシの設定、PCの日時を確認して再試行してください。'
            ) from error
        raise ValueError('更新情報を取得できません。インターネット接続を確認して再試行してください。') from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError('更新情報を読み取れませんでした。後でもう一度お試しください。') from error
    if not isinstance(release, dict) or release.get('draft') or release.get('prerelease'):
        raise ValueError('正式版の更新情報を確認できませんでした。')
    version_number(release.get('tag_name'))
    return release


def _installer_asset(release: dict, tag: str) -> dict | None:
    """公式リリースのインストーラーと GitHub が公表する SHA256 を取り出す。"""
    version = tag.removeprefix('v')
    name = f'KantanKaiko-Setup-{version}.exe'
    assets = release.get('assets')
    if not isinstance(assets, list):
        return None
    asset = next((a for a in assets if isinstance(a, dict) and a.get('name') == name), None)
    if asset is None:
        return None
    url = asset.get('browser_download_url')
    if url != f'{DOWNLOAD_PREFIX}{tag}/{name}':
        raise ValueError('更新ファイルの取得元が公式リリースと一致しません。')
    size = asset.get('size')
    if not isinstance(size, int) or not 0 < size <= MAX_UPDATE_BYTES:
        raise ValueError('更新ファイルのサイズを確認できませんでした。')
    digest = asset.get('digest')
    if not isinstance(digest, str) or not digest.startswith('sha256:'):
        raise ValueError('更新ファイルの検証情報を確認できませんでした。')
    checksum = digest.split(':', 1)[1].lower()
    if not re.fullmatch(r'[0-9a-f]{64}', checksum):
        raise ValueError('更新ファイルの検証情報を確認できませんでした。')
    return {'version': version, 'name': name, 'url': url, 'size': size, 'sha256': checksum}


def check_latest(current=VERSION):
    release = _fetch_release()
    tag = release['tag_name']
    result = {'version': tag.removeprefix('v'),
              'newer': version_number(tag) > version_number(current),
              'url': f'{RELEASE_URL}/tag/{tag}'}
    try:
        result['update'] = _installer_asset(release, tag)
    except ValueError:
        # 古いリリース等で asset 情報が無い場合でも、手動の版確認は成立させる。
        result['update'] = None
    return result


def download_update(package: dict, on_progress=None) -> str:
    """公式アセットをダウンロードし、GitHub 公表の SHA256 を検証してパスを返す。"""
    if not isinstance(package, dict):
        raise ValueError('更新ファイルの情報がありません。')
    url = package.get('url', '')
    expected = re.compile(
        rf'^{re.escape(DOWNLOAD_PREFIX)}v\d+\.\d+\.\d+/KantanKaiko-Setup-\d+\.\d+\.\d+\.exe$')
    if not isinstance(url, str) or not expected.fullmatch(url):
        raise ValueError('公式リリース以外からはダウンロードしません。')
    checksum = package.get('sha256', '')
    if not isinstance(checksum, str) or not re.fullmatch(r'[0-9a-f]{64}', checksum):
        raise ValueError('更新ファイルの検証情報を確認できませんでした。')
    size = package.get('size')
    if not isinstance(size, int) or not 0 < size <= MAX_UPDATE_BYTES:
        raise ValueError('更新ファイルのサイズを確認できませんでした。')

    directory = Path(tempfile.mkdtemp(prefix='kantan-update-'))
    target = directory / Path(url).name
    digest = hashlib.sha256()
    done = 0
    try:
        with _open_url(url, {'User-Agent': f'KantanKaiko/{VERSION}'}, 30) as response, \
                target.open('wb') as stream:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                done += len(chunk)
                if done > MAX_UPDATE_BYTES:
                    raise ValueError('更新ファイルが大きすぎます。')
                digest.update(chunk)
                stream.write(chunk)
                if on_progress:
                    on_progress(done, size)
        if done != size:
            raise ValueError('更新ファイルのダウンロードが途中で終了しました。')
        if digest.hexdigest() != checksum:
            raise ValueError('ダウンロードしたファイルの検証に失敗しました。再試行してください。')
        return str(target)
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise
