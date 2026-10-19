"""別プロセスからのWM_DROPFILES堅牢性テスト。

実ドロップ(Explorer等)はOLE共有メモリ経由の正規HDROPで来るが、
テストからは正規の共有HDROPを合成できない。そのため本テストでは
「正規でない通知が来ても死なない・壊れない」ことを検証する。
正常配送の検証は tests/test_e2e.py (同一プロセス) で行う。

検証内容:
1. 別プロセスから hdrop=NULL の通知 → 無視し、生存＋イベントループ健全
   健全性は「通知の後も heartbeat が新しくなる」ことで判断する。1時点の
   age 判定は負荷で揺れるが、進んでいるかどうかは揺れない (#84)。

※意図的なゴミハンドルは対象外: 無効アドレスへの一切の接触
(GlobalFlags/DragQuery/DragFinishのいずれも)が user mode ではAVし得るため、
防ぎようがなく、かつ現実のドロップでは起こらない (要同一desktop上の悪意送信)。

実行: python tests/test_xproc_dnd.py
"""

import ctypes
import shutil
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

WM_DROPFILES = 0x0233


def _send(hwnd: int, hdrop: int) -> int:
    user32 = ctypes.windll.user32
    user32.SendMessageW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.SendMessageW.restype = wintypes.LPARAM
    return user32.SendMessageW(hwnd, WM_DROPFILES, hdrop, 0)


def _heartbeat_age(tmp: Path) -> float | None:
    """heartbeat.txt が最後に更新されてからの秒数。まだ無い・読めないときは None。"""
    try:
        return time.time() - float((tmp / "heartbeat.txt").read_text(encoding="utf-8"))
    except Exception:
        return None


def _snapshot(process: subprocess.Popen, tmp: Path, started: float) -> str:
    """失敗メッセージに載せる測定値。どの段階でどれだけ遅れたかを残す (#84)。"""
    age = _heartbeat_age(tmp)
    return (
        f"elapsed={time.time() - started:.2f}s"
        f" heartbeat_age={'none' if age is None else f'{age:.2f}s'}"
        f" hwnd_written={(tmp / 'hwnd.txt').exists()}"
        f" exitcode={process.poll()}"
    )


def test_cross_process_robustness() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="xproc-"))
    probe = Path(__file__).resolve().parent / "xproc_probe.py"
    started = time.time()
    process = None
    try:
        process = subprocess.Popen([sys.executable, str(probe), str(tmp)])

        hwndf = tmp / "hwnd.txt"
        deadline = started + 20
        while not hwndf.exists():
            assert time.time() < deadline, (
                f"probe did not start ({_snapshot(process, tmp, started)})"
            )
            assert process.poll() is None, (
                f"probe died at startup ({_snapshot(process, tmp, started)})"
            )
            time.sleep(0.1)
        hwnd = int(hwndf.read_text())

        # 初回ハートビートを待つ (プローブ起動直後はまだ無い)
        deadline = started + 15
        while True:
            age = _heartbeat_age(tmp)
            if age is not None and age < 3.0:
                break
            assert time.time() < deadline, (
                f"probe event loop never started ({_snapshot(process, tmp, started)})"
            )
            assert process.poll() is None, (
                f"probe died at startup ({_snapshot(process, tmp, started)})"
            )
            time.sleep(0.2)

        before = _heartbeat_age(tmp)
        _send(hwnd, 0)  # NULL
        # 通知を処理した後もループが回っている証拠として、より新しい heartbeat を待つ。
        deadline = time.time() + 10
        while True:
            age = _heartbeat_age(tmp)
            assert process.poll() is None, (
                f"app DIED on foreign NULL hdrop ({_snapshot(process, tmp, started)})"
            )
            if age is not None and before is not None and age < before:
                break
            assert time.time() < deadline, (
                "event loop did not advance after a foreign NULL hdrop"
                f" ({_snapshot(process, tmp, started)} heartbeat_before={before:.2f}s)"
            )
            time.sleep(0.1)
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        shutil.rmtree(tmp, ignore_errors=True)
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
