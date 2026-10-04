"""Manual, bounded checks against the application's official release feed."""
import json
import re
from urllib.error import URLError
from urllib.request import Request, urlopen

from version import VERSION

API_URL = 'https://api.github.com/repos/neoenox/unzip-tool/releases/latest'
RELEASE_URL = 'https://github.com/neoenox/unzip-tool/releases'


def version_number(value):
    if not isinstance(value, str) or not re.fullmatch(r'v?\d+\.\d+\.\d+', value):
        raise ValueError('更新情報のバージョンを確認できませんでした。後でもう一度お試しください。')
    return tuple(int(part) for part in value.removeprefix('v').split('.'))


def check_latest(current=VERSION):
    request = Request(API_URL, headers={'Accept': 'application/vnd.github+json',
                                       'User-Agent': f'KantanKaiko/{VERSION}'})
    try:
        with urlopen(request, timeout=8) as response:
            raw = response.read(256 * 1024 + 1)
        if len(raw) > 256 * 1024:
            raise ValueError('更新情報が大きすぎます。後でもう一度お試しください。')
        release = json.loads(raw)
        if not isinstance(release, dict) or release.get('draft') or release.get('prerelease'):
            raise ValueError('正式版の更新情報を確認できませんでした。')
        tag = release.get('tag_name')
        newer = version_number(tag) > version_number(current)
        return {'version': tag.removeprefix('v'), 'newer': newer,
                'url': f'{RELEASE_URL}/tag/{tag}'}
    except (URLError, TimeoutError, OSError) as error:
        raise ValueError('更新情報を取得できません。インターネット接続を確認して再試行してください。') from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError('更新情報を読み取れませんでした。後でもう一度お試しください。') from error
