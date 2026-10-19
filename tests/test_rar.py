"""RAR対応テスト。UnRARツールが必要 (未検出時はスキップ)。

ツールの指定: 環境変数 KANTAN_UNRAR を指定したときはそのパスだけを使う。
指定が無いときは tools/UnRAR.exe > WinRAR > PATH の順 (#80)。
実行例: $env:KANTAN_UNRAR='C:/tools/UnRAR.exe'; python tests/test_rar.py
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unzipper  # noqa: E402
from unzipper import default_dest_for, detect_kind, extract_archive, find_unrar_tool, is_supported, list_contents  # noqa: E402

VENDOR = Path(__file__).resolve().parent / "vendor"


def tool_available() -> bool:
    return find_unrar_tool() is not None


def test_rar_basics() -> None:
    assert is_supported("a.rar")
    assert not is_supported("a.xyz")
    assert detect_kind("a.rar") == "rar"
    assert default_dest_for("d/a.rar").name == "a"


def test_rar3_rar5() -> None:
    if not tool_available():
        print("SKIP test_rar3_rar5 (UnRAR not found)")
        return
    for name in ("testfile.rar3.rar", "testfile.rar5.rar"):
        src = VENDOR / name
        entries = list_contents(src)
        assert [(e.name, e.size) for e in entries] == [("testfile.txt", 12)], entries
        dest = Path(tempfile.mkdtemp(prefix="rar-")) / name
        seen = []
        extract_archive(src, dest, on_progress=lambda d, t: seen.append((d, t)))
        assert (dest / "testfile.txt").read_text() == "Testing 123\n"
        assert seen[-1] == (1, 1), seen


def test_rar_no_tool_message() -> None:
    if tool_available():
        print("SKIP test_rar_no_tool_message (tool present)")
        return
    try:
        list_contents(VENDOR / "testfile.rar5.rar")
    except ValueError as e:
        assert "UnRAR" in str(e), e
    else:
        raise AssertionError("expected ValueError without tool")


def test_configured_tool_is_authoritative() -> None:
    """KANTAN_UNRAR を指定したら、そのパスだけを使う (#80)。

    Windowsは子プロセスの ProgramFiles を親の変更どおりにしないため、
    WinRAR導入機では環境変数だけでは「ツール無し」を作れない。指定を最優先に
    することで、未検出の案内文も環境に依存せず検査できる。
    """
    with tempfile.TemporaryDirectory(prefix="rar-spec-") as d:
        base = Path(d)
        adjacent = base / "tools"
        adjacent.mkdir()
        adjacent_tool = adjacent / "UnRAR.exe"
        adjacent_tool.write_bytes(b"MZ")  # 隣接候補が見つかってしまう状況
        missing = base / "missing.exe"
        with patch.object(unzipper, "_base_dirs", lambda: [base]):
            with patch.dict(os.environ, {"KANTAN_UNRAR": str(missing)}):
                assert find_unrar_tool() is None
            with patch.dict(os.environ, {"KANTAN_UNRAR": str(adjacent_tool)}):
                assert find_unrar_tool() == adjacent_tool


def test_configured_tool_error_names_the_path() -> None:
    """指定パスが無いときは、案内文にそのパスを含める (#80)。"""
    with tempfile.TemporaryDirectory(prefix="rar-spec-") as d:
        missing = Path(d) / "missing.exe"
        with patch.dict(os.environ, {"KANTAN_UNRAR": str(missing)}):
            unzipper._rar_tool_ready = False
            try:
                list_contents(VENDOR / "testfile.rar5.rar")
            except ValueError as e:
                assert "UnRAR" in str(e) and str(missing) in str(e), e
            else:
                raise AssertionError("expected ValueError for a missing KANTAN_UNRAR path")


def main() -> int:
    test_rar_basics()
    print("PASS test_rar_basics")
    test_rar3_rar5()
    print("PASS test_rar3_rar5")
    test_rar_no_tool_message()
    print("PASS test_rar_no_tool_message")
    test_configured_tool_is_authoritative()
    print("PASS test_configured_tool_is_authoritative")
    test_configured_tool_error_names_the_path()
    print("PASS test_configured_tool_error_names_the_path")
    print("ALL RAR PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
