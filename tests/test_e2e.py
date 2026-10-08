"""E2Eテスト (標準ライブラリのみ、pytest不要)。

実物のAppウィンドウを使い、以下を端から端まで検証する。
1. GUI解凍E2E: アーカイブ設定→「解凍する」→ファイル実体と完了表示を確認
2. OSレベルDnD E2E: 本物のHDROPを作り WM_DROPFILES を送信→入力欄に反映されるか確認

実行: python tests/test_e2e.py
"""
from __future__ import annotations

import ctypes
import sys
import tempfile
import time
import zipfile
from ctypes import wintypes
from pathlib import Path
from tkinter import messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import App  # noqa: E402

WM_DROPFILES = 0x0233
# GMEM_MOVEABLE | GMEM_ZEROINIT | GMEM_DDESHARE
# DDESHARE必須: 実ドロップ(Explorer等)は共有メモリで来る。付けないと
# 別プロセスからのDragQuery/DragFinishが壊れる (テスト側の再現条件)。
GHND = 0x0002 | 0x0040 | 0x2000


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class DROPFILES(ctypes.Structure):
    _fields_ = [
        ("pFiles", wintypes.DWORD),
        ("pt", POINT),
        ("fNC", wintypes.BOOL),
        ("fWide", wintypes.BOOL),
    ]


def make_hdrop(paths: list[str]) -> int:
    """本物のHDROPを構築する (受け側がDragFinishで解放するのがOSの約束)。"""
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = wintypes.BOOL

    raw = ("\0".join(paths) + "\0\0").encode("utf-16-le")
    size = ctypes.sizeof(DROPFILES) + len(raw)
    h = kernel32.GlobalAlloc(GHND, size)
    assert h, "GlobalAlloc failed"
    ptr = kernel32.GlobalLock(h)
    assert ptr, "GlobalLock failed"
    df = DROPFILES()
    df.pFiles = ctypes.sizeof(DROPFILES)
    df.fWide = True
    ctypes.memmove(ptr, ctypes.byref(df), ctypes.sizeof(df))
    ctypes.memmove(ptr + df.pFiles, raw, len(raw))
    kernel32.GlobalUnlock(h)
    return h


def send_drop(hwnd: int, paths: list[str]) -> None:
    user32 = ctypes.windll.user32
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SendMessageW.restype = wintypes.LPARAM
    hdrop = make_hdrop(paths)
    user32.SendMessageW(hwnd, WM_DROPFILES, hdrop, 0)
    # hdropは受け側(DragFinish)が解放済みのため、ここでは触らない


def make_sample_zip(base: Path) -> Path:
    zpath = base / "sample.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("hello.txt", "hello e2e")
        z.writestr("日本語.txt", "mojibake e2e")
    return zpath


def pump(app: App, cond, timeout: float = 20.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        app.update()
        try:
            if cond():
                return True
        except Exception:
            pass
        time.sleep(0.05)
    return False


def mute_dialogs():
    orig = (messagebox.showinfo, messagebox.showwarning, messagebox.showerror)
    messagebox.showinfo = lambda *a, **k: None
    messagebox.showwarning = lambda *a, **k: None
    messagebox.showerror = lambda *a, **k: None
    return orig


def restore_dialogs(orig) -> None:
    messagebox.showinfo, messagebox.showwarning, messagebox.showerror = orig


def test_gui_extract_e2e() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="e2e-"))
    zpath = make_sample_zip(tmp)
    dest = tmp / "out"
    app = App()
    app.withdraw()
    orig = mute_dialogs()
    try:
        if sys.platform == "win32":
            assert app._dnd_enabled, "DnD hook not enabled"
        app.archive_var.set(str(zpath))
        assert pump(app, lambda: "2 件" in app.status.get()), f"list failed: {app.status.get()}"
        app.dest_var.set(str(dest))
        app.start_extract()
        ok = pump(app, lambda: app.status.get().startswith("完了"))
        assert ok, f"extract did not finish: {app.status.get()}"
        assert (dest / "hello.txt").read_text(encoding="utf-8") == "hello e2e"
        assert (dest / "日本語.txt").read_text(encoding="utf-8") == "mojibake e2e"
    finally:
        restore_dialogs(orig)
        app._on_close()
    print("PASS test_gui_extract_e2e")


def test_os_level_drop_e2e() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="e2e-drop-"))
    zpath = make_sample_zip(tmp)
    app = App()
    app.withdraw()
    orig = mute_dialogs()
    try:
        send_drop(app.winfo_id(), [str(zpath)])
        ok = pump(app, lambda: app.archive_var.get() == str(zpath))
        assert ok, f"drop not reflected: {app.archive_var.get()!r}"
        assert pump(app, lambda: "2 件" in app.status.get()), f"list failed: {app.status.get()}"
    finally:
        restore_dialogs(orig)
        app._on_close()
    print("PASS test_os_level_drop_e2e")


def main() -> int:
    test_gui_extract_e2e()
    if sys.platform == "win32":
        test_os_level_drop_e2e()
    else:
        print("SKIP test_os_level_drop_e2e (Windows only)")
    print("ALL E2E PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
