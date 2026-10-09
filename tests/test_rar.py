"""RAR対応テスト。UnRARツールが必要 (未検出時はスキップ)。

ツールの指定: 環境変数 KANTAN_UNRAR > tools/UnRAR.exe > WinRAR > PATH。
実行例: $env:KANTAN_UNRAR='C:/tools/UnRAR.exe'; python tests/test_rar.py
"""
import os
import sys
import tempfile
from pathlib import Path

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
        assert seen[-1] == (12, 12), seen


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


def main() -> int:
    test_rar_basics()
    print("PASS test_rar_basics")
    test_rar3_rar5()
    print("PASS test_rar3_rar5")
    test_rar_no_tool_message()
    print("PASS test_rar_no_tool_message")
    print("ALL RAR PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
