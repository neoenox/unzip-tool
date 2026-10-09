"""UnRAR自動取得のテスト (ネットワーク不要。file:// URLで検証)。"""
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unzipper  # noqa: E402
from unzipper import (  # noqa: E402
    RAR_TOOL_HELP,
    download_unrar,
    ensure_unrar_tool,
    is_missing_unrar_error,
    user_tool_dir,
    user_unrar_path,
)

FAKE_EXE = b"MZ" + b"\x00" * 200_000


def make_source(content: bytes = FAKE_EXE) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".exe")
    tmp.write(content)
    tmp.close()
    return Path(tmp.name).as_uri()


def test_help_mentions_auto_fetch() -> None:
    assert "自動" in RAR_TOOL_HELP or "取得" in RAR_TOOL_HELP, RAR_TOOL_HELP
    assert is_missing_unrar_error(RAR_TOOL_HELP)
    assert not is_missing_unrar_error("書庫が壊れています")


def test_user_dir_respects_localappdata() -> None:
    old = os.environ.get("LOCALAPPDATA")
    os.environ["LOCALAPPDATA"] = r"C:\Fake\AppData\Local"
    try:
        assert user_unrar_path() == Path(r"C:\Fake\AppData\Local") / "KantanKaiko" / "tools" / "UnRAR.exe"
    finally:
        if old is None:
            del os.environ["LOCALAPPDATA"]
        else:
            os.environ["LOCALAPPDATA"] = old
    assert user_tool_dir().name == "tools"


def test_download_raw_file_url() -> None:
    url = make_source()
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "tools" / "UnRAR.exe"
        got = download_unrar(dest, url=url)
        assert got == dest
        assert dest.read_bytes()[:2] == b"MZ"


def test_download_rejects_non_exe() -> None:
    url = make_source(b"not-an-exe" * 1000)
    with tempfile.TemporaryDirectory() as tmp:
        try:
            download_unrar(Path(tmp) / "UnRAR.exe", url=url)
        except ValueError as error:
            assert "実行形式" in str(error) or "小さすぎ" in str(error), error
        else:
            raise AssertionError("expected ValueError for non-exe")


def test_download_hash_mismatch() -> None:
    url = make_source()
    with tempfile.TemporaryDirectory() as tmp:
        try:
            download_unrar(Path(tmp) / "UnRAR.exe", url=url,
                           expected_sha256="0" * 64)
        except ValueError as error:
            assert "ハッシュ" in str(error), error
        else:
            raise AssertionError("expected ValueError for hash mismatch")


def test_download_hash_ok() -> None:
    digest = hashlib.sha256(FAKE_EXE).hexdigest()
    url = make_source()
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "UnRAR.exe"
        download_unrar(dest, url=url, expected_sha256=digest)
        assert dest.is_file()


def test_ensure_without_tool_and_no_auto() -> None:
    old_find = unzipper.find_unrar_tool
    unzipper.find_unrar_tool = lambda: None
    try:
        try:
            ensure_unrar_tool(auto_download=False)
        except ValueError as error:
            assert "UnRAR" in str(error), error
        else:
            raise AssertionError("expected ValueError")
    finally:
        unzipper.find_unrar_tool = old_find


def test_ensure_auto_download_uses_url_env() -> None:
    url = make_source()
    old_find = unzipper.find_unrar_tool
    old_url = os.environ.get("KANTAN_UNRAR_URL")
    old_data = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["KANTAN_UNRAR_URL"] = url
        os.environ["LOCALAPPDATA"] = tmp
        unzipper.find_unrar_tool = old_find  # 実物を使う (隔離先を見る)
        # 隔離先には無いので取得が走る。ただし開発機のtools等に実物があると
        # findが成功してしまうため、findを一時的に隔離先のみ見る形にする。
        unzipper.find_unrar_tool = lambda: (
            user_unrar_path() if user_unrar_path().is_file() else None
        )
        try:
            got = ensure_unrar_tool(auto_download=True)
            assert got.is_file()
            assert got.read_bytes()[:2] == b"MZ"
        finally:
            unzipper.find_unrar_tool = old_find
            if old_url is None:
                os.environ.pop("KANTAN_UNRAR_URL", None)
            else:
                os.environ["KANTAN_UNRAR_URL"] = old_url
            if old_data is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_data


def test_fetch_script_raw() -> None:
    url = make_source()
    digest = hashlib.sha256(FAKE_EXE).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "UnRAR.exe"
        script = Path(__file__).resolve().parent.parent / "scripts" / "fetch_unrar.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--dest", str(dest),
             "--url", url, "--sha256", digest, "--no-sfx-fallback"],
            capture_output=True, text=True, timeout=60,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert dest.is_file()
        # 既存があれば何もしない
        proc2 = subprocess.run(
            [sys.executable, str(script), "--dest", str(dest),
             "--url", url, "--no-sfx-fallback"],
            capture_output=True, text=True, timeout=60,
        )
        assert proc2.returncode == 0, proc2.stdout + proc2.stderr


def main() -> int:
    test_help_mentions_auto_fetch()
    print("PASS test_help_mentions_auto_fetch")
    test_user_dir_respects_localappdata()
    print("PASS test_user_dir_respects_localappdata")
    test_download_raw_file_url()
    print("PASS test_download_raw_file_url")
    test_download_rejects_non_exe()
    print("PASS test_download_rejects_non_exe")
    test_download_hash_mismatch()
    print("PASS test_download_hash_mismatch")
    test_download_hash_ok()
    print("PASS test_download_hash_ok")
    test_ensure_without_tool_and_no_auto()
    print("PASS test_ensure_without_tool_and_no_auto")
    test_ensure_auto_download_uses_url_env()
    print("PASS test_ensure_auto_download_uses_url_env")
    test_fetch_script_raw()
    print("PASS test_fetch_script_raw")
    print("ALL FETCH_UNRAR PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
