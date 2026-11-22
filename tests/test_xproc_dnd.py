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


def test_ole_hdrop_with_invalid_handle_is_rejected():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import dnd_ole

    class FakeGlobalFlags:
        argtypes = None
        restype = None

        def __init__(self, value):
            self.value = value

        def __call__(self, _hdrop):
            return self.value

    class FakeKernel32:
        def __init__(self, value):
            self.GlobalFlags = FakeGlobalFlags(value)

    assert dnd_ole._hdrop_valid(FakeKernel32(0), 123)
    assert not dnd_ole._hdrop_valid(FakeKernel32(0x8000), 123)
    assert not dnd_ole._hdrop_valid(FakeKernel32(0), 0)


def test_register_failure_unwinds_com_apartment():
    import dnd_ole
    from unittest import mock

    calls = []

    class FakeOle:
        def OleInitialize(self, _arg):
            calls.append("init")
            return dnd_ole.S_OK

        def OleUninitialize(self):
            calls.append("uninit")

        def RegisterDragDrop(self, *_args):
            return -1

        def RevokeDragDrop(self, *_args):
            return 0

    with mock.patch.object(dnd_ole, "_ole32", return_value=FakeOle()), \
            mock.patch.object(dnd_ole.os, "name", "nt"):
        assert dnd_ole.register(9001, lambda paths, skipped: None) is False
    assert calls == ["init", "uninit"]


def test_revoke_releases_owned_apartment():
    import dnd_ole
    from unittest import mock

    calls = []

    class FakeOle:
        def OleInitialize(self, _arg):
            calls.append("init")
            return dnd_ole.S_OK

        def OleUninitialize(self):
            calls.append("uninit")

        def RegisterDragDrop(self, *_args):
            return dnd_ole.S_OK

        def RevokeDragDrop(self, *_args):
            return 0

    with mock.patch.object(dnd_ole, "_ole32", return_value=FakeOle()), \
            mock.patch.object(dnd_ole.os, "name", "nt"):
        assert dnd_ole.register(9002, lambda paths, skipped: None) is True
        dnd_ole.revoke(9002)
    assert calls == ["init", "uninit"]


def test_query_interface_failure_clears_output_pointer():
    import ctypes
    import dnd_ole

    target = dnd_ole._DropTarget(1, lambda paths, skipped: None)
    ppv = (ctypes.c_void_p * 1)(12345)
    iid = dnd_ole._guid(0x1234, 0x00)
    hr = target._vtbl.QueryInterface(None, ctypes.byref(iid), ppv)
    assert hr == dnd_ole.E_NOINTERFACE
    assert ppv[0] is None


def _data_object_for_dnd_ole(dnd_ole, supported):
    query = dnd_ole._QueryGetData(
        lambda this, fmt: dnd_ole.S_OK if supported else dnd_ole.S_FALSE)
    vtbl = (ctypes.c_void_p * 6)()
    vtbl[5] = ctypes.cast(query, ctypes.c_void_p).value
    iface = (ctypes.c_void_p * 1)(
        ctypes.cast(ctypes.pointer(vtbl), ctypes.c_void_p).value)
    return ctypes.cast(ctypes.pointer(iface), ctypes.c_void_p), (query, vtbl, iface)


def test_ole_drag_requires_hdrop():
    import dnd_ole

    target = dnd_ole._DropTarget(9100, lambda paths, skipped: None)
    effect = ctypes.c_ulong(0)
    pt = dnd_ole.POINT(0, 0)
    no_files, keep_no = _data_object_for_dnd_ole(dnd_ole, False)
    target._vtbl.DragEnter(target.pointer, no_files, 1, pt, ctypes.pointer(effect))
    assert effect.value == 0
    assert not dnd_ole.is_drag_over(9100)
    files, keep_yes = _data_object_for_dnd_ole(dnd_ole, True)
    target._vtbl.DragEnter(target.pointer, files, 1, pt, ctypes.pointer(effect))
    assert effect.value == dnd_ole.DROPEFFECT_COPY
    assert dnd_ole.is_drag_over(9100)
    target._vtbl.DragOver(target.pointer, 1, pt, ctypes.pointer(effect))
    assert effect.value == dnd_ole.DROPEFFECT_COPY
    target._vtbl.DragLeave(target.pointer)
    assert not dnd_ole.is_drag_over(9100)


def test_dropfiles_not_forwarded_and_reports_limit():
    import dnd
    from types import SimpleNamespace
    from unittest import mock
    if sys.platform != "win32":
        return

    calls = []

    class FakeShell:
        def DragQueryFileW(self, hdrop, index, buf, size):
            if index == 0xFFFFFFFF:
                return dnd.MAX_FILES + 2
            if buf is None:
                return 5
            buf.value = 'x.zip'
            return 5

        def DragFinish(self, hdrop):
            calls.append(('finish', hdrop))

        def DragAcceptFiles(self, hwnd, enabled):
            pass

    class FakeKernel:
        def GlobalFlags(self, hdrop):
            return 0

    wndproc = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_uint,
                               ctypes.c_void_p, ctypes.c_void_p)

    def call_proc(*args):
        calls.append(('forward', args))
        return 0

    widget = SimpleNamespace(update_idletasks=lambda: None, winfo_id=lambda: 9101)
    procs = (SimpleNamespace(IsWindow=lambda hwnd: True), FakeShell(), FakeKernel(),
             lambda hwnd, index, proc: 123, call_proc, wndproc)
    with mock.patch.object(dnd, '_setup_procs', return_value=procs), \
            mock.patch.object(dnd.dnd_ole, 'register', return_value=True):
        assert dnd.enable_drop(widget) is True
        handler = dnd._hooks[9101][1]
        handler(9101, WM_DROPFILES, 42, 0)
    try:
        assert calls == [('finish', 42)], calls
        assert len(dnd._pending[9101][0]) == dnd.MAX_FILES
        assert dnd.take_truncated_files(widget) == 2
    finally:
        dnd._hooks.pop(9101, None)
        dnd._pending.pop(9101, None)
        dnd._truncated.pop(9101, None)

def main() -> int:
    test_ole_hdrop_with_invalid_handle_is_rejected()
    print("PASS test_ole_hdrop_with_invalid_handle_is_rejected")
    test_register_failure_unwinds_com_apartment()
    print("PASS test_register_failure_unwinds_com_apartment")
    test_revoke_releases_owned_apartment()
    print("PASS test_revoke_releases_owned_apartment")
    test_query_interface_failure_clears_output_pointer()
    print("PASS test_query_interface_failure_clears_output_pointer")
    test_ole_drag_requires_hdrop()
    print("PASS test_ole_drag_requires_hdrop")
    test_dropfiles_not_forwarded_and_reports_limit()
    print("PASS test_dropfiles_not_forwarded_and_reports_limit")
    if sys.platform != "win32":
        print("SKIP test_cross_process_robustness (Windows only)")
        return 0
    test_cross_process_robustness()
    print("ALL XPROC PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
