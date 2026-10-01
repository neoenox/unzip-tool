"""7z対応テスト。py7zrで資材を自作するため外部ツール不要。

実行: python tests/test_7z.py
"""
import sys
import tempfile
from pathlib import Path

import py7zr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unzipper import _check_names_safe, default_dest_for, detect_kind, extract_archive, is_supported, list_contents  # noqa: E402


def make_7z(base: Path, name: str = "t.7z", password: str | None = None) -> Path:
    src = base / "src"
    (src / "sub").mkdir(parents=True, exist_ok=True)
    (src / "hello.txt").write_text("hello 7z", encoding="utf-8")
    (src / "日本語.txt").write_text("jp", encoding="utf-8")
    (src / "sub" / "a.bin").write_bytes(b"x" * 1000)
    zpath = base / name
    with py7zr.SevenZipFile(zpath, "w", password=password) as a:
        a.writeall(src, ".")
    return zpath


def test_7z_basics() -> None:
    assert is_supported("a.7z")
    assert detect_kind("a.7z") == "7z"
    assert default_dest_for("d/a.7z").name == "a"


def test_7z_roundtrip() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="7z-"))
    zpath = make_7z(tmp)
    names = sorted(e.name for e in list_contents(zpath))
    assert names == sorted([".", "hello.txt", "日本語.txt", "sub", "sub/a.bin"]), names
    dest = tmp / "out"
    seen = []
    extract_archive(zpath, dest, on_progress=lambda d, t: seen.append((d, t)))
    assert (dest / "hello.txt").read_text(encoding="utf-8") == "hello 7z"
    assert (dest / "日本語.txt").read_text(encoding="utf-8") == "jp"
    assert (dest / "sub" / "a.bin").read_bytes() == b"x" * 1000
    assert seen[-1][0] == seen[-1][1] and seen[-1][1] > 0, seen


def test_7z_password() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="7zpw-"))
    zpath = make_7z(tmp, "pw.7z", password="secret")
    try:
        extract_archive(zpath, tmp / "nope")
    except Exception:
        pass  # パスワード無しでは失敗する (形式により例外種別が異なる)
    else:
        raise AssertionError("expected failure without password")
    dest = tmp / "out"
    extract_archive(zpath, dest, password="secret".encode())
    assert (dest / "hello.txt").read_text(encoding="utf-8") == "hello 7z"


def test_7z_evil_names_rejected() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="7zevil-"))
    dest = tmp / "out"
    dest.mkdir()
    # ..系・ドライブ絶対は拒否 (py7zr本体もBad7zFileで拒否する)
    for evil in ("../evil.txt", "..\\evil.txt", "sub/../../evil.txt", "C:/win.txt"):
        try:
            _check_names_safe(dest, [evil])
        except ValueError:
            pass
        else:
            raise AssertionError(f"not rejected: {evil}")
    # 先頭/ は剥離してdest内に収める (py7zrと同挙動のため安全)
    _check_names_safe(dest, ["/abs.txt", "ok.txt", "sub/ok2.txt"])


def main() -> int:
    test_7z_basics()
    print("PASS test_7z_basics")
    test_7z_roundtrip()
    print("PASS test_7z_roundtrip")
    test_7z_password()
    print("PASS test_7z_password")
    test_7z_evil_names_rejected()
    print("PASS test_7z_evil_names_rejected")
    print("ALL 7Z PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
