"""別プロセスからのWM_DROPFILES堅牢性テスト。

実ドロップ(Explorer等)はOLE共有メモリ経由の正規HDROPで来るが、
テストからは正規の共有HDROPを合成できない。そのため本テストでは
「正規でない通知が来ても死なない・壊れない」ことを検証する。
正常配送の検証は tests/test_e2e.py (同一プロセス) で行う。

検証内容:
1. 別プロセスから hdrop=NULL の通知 → 無視し、生存＋イベントループ健全

※意図的なゴミハンドルは対象外: 無効アドレスへの一切の接触
(GlobalFlags/DragQuery/DragFinishのいずれも)が user mode ではAVし得るため、
防ぎようがなく、かつ現実のドロップでは起こらない (要同一desktop上の悪意送信)。

実行: python tests/test_xproc_dnd.py
"""
import ctypes
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

WM_DROPFILES = 0x0233


def _send(hwnd: int, hdrop: int) -> int:
    user32 = ctypes.windll.user32
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SendMessageW.restype = wintypes.LPARAM
    return user32.SendMessageW(hwnd, WM_DROPFILES, hdrop, 0)


def _heartbeat_fresh(tmp: Path) -> bool:
    try:
        return time.time() - float((tmp / "heartbeat.txt").read_text(encoding="utf-8")) < 3.0
    except Exception:
        return False


def test_cross_process_robustness() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="xproc-"))
    probe = Path(__file__).resolve().parent / "xproc_probe.py"
    p = subprocess.Popen([sys.executable, str(probe), str(tmp)])
    try:
        hwndf = tmp / "hwnd.txt"
        deadline = time.time() + 20
        while not hwndf.exists():
            assert time.time() < deadline, "probe did not start"
            assert p.poll() is None, "probe died at startup"
            time.sleep(0.1)
        hwnd = int(hwndf.read_text())
        # 初回ハートビートを待つ (プローブ起動直後はまだ無い)
        deadline = time.time() + 15
        while not _heartbeat_fresh(tmp):
            assert time.time() < deadline, "probe event loop never started"
            assert p.poll() is None, "probe died at startup"
            time.sleep(0.2)

        _send(hwnd, 0)  # NULL
        time.sleep(2)
        assert p.poll() is None, "app DIED on foreign NULL hdrop"
        assert _heartbeat_fresh(tmp), "event loop BROKEN on foreign NULL hdrop"
    finally:
        p.terminate()
    print("PASS test_cross_process_robustness")


def main() -> int:
    if sys.platform != "win32":
        print("SKIP test_cross_process_robustness (Windows only)")
        return 0
    test_cross_process_robustness()
    print("ALL XPROC PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
