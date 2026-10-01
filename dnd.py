"""Windows ファイルドラッグ&ドロップ (WM_DROPFILES / ctypes、標準ライブラリのみ)。

tkinter にはファイルDnDが無いため、ウィンドウに WM_DROPFILES を受け付ける。
Windows以外では enable_drop() は False を返し、何もしない。
"""
from __future__ import annotations

import ctypes
import os
from typing import Callable

WM_DROPFILES = 0x0233
GWL_WNDPROC = -4
MAX_FILES = 64  # 取り出し上限 (シンプル版)

DropCallback = Callable[[list[str]], None]

# hwnd -> (旧WndProc, 新WndProcへの参照, widget) ※参照保持しないとGCでクラッシュする
_hooks: dict[int, tuple[int, object, object]] = {}


def _setup_procs():
    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32
    from ctypes import wintypes

    if ctypes.sizeof(ctypes.c_void_p) == 8:
        set_long = user32.SetWindowLongPtrW
        set_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        set_long.restype = wintypes.LPARAM
    else:
        set_long = user32.SetWindowLongW
        set_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        set_long.restype = wintypes.LPARAM

    call_proc = user32.CallWindowProcW
    call_proc.argtypes = [wintypes.LPARAM, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    call_proc.restype = wintypes.LPARAM

    shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
    shell32.DragAcceptFiles.restype = None
    shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
    shell32.DragQueryFileW.restype = wintypes.UINT
    shell32.DragFinish.argtypes = [wintypes.HANDLE]
    shell32.DragFinish.restype = None

    WNDPROC = ctypes.WINFUNCTYPE(wintypes.LPARAM, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    return user32, shell32, set_long, call_proc, WNDPROC


def _query_paths(shell32, hdrop: int) -> list[str]:
    count = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
    paths: list[str] = []
    for i in range(min(count, MAX_FILES)):
        length = shell32.DragQueryFileW(hdrop, i, None, 0)
        buf = ctypes.create_unicode_buffer(length + 1)
        shell32.DragQueryFileW(hdrop, i, buf, length + 1)
        paths.append(buf.value)
    return paths


def enable_drop(widget, callback: DropCallback) -> bool:
    """widget(トップレベル)へのファイルドロップを有効化。成功時True。"""
    if os.name != "nt":
        return False
    try:
        widget.update_idletasks()
        hwnd = widget.winfo_id()
        user32, shell32, set_long, call_proc, WNDPROC = _setup_procs()
        if not user32.IsWindow(hwnd):
            return False
        if hwnd in _hooks:
            return True

        def handler(hwnd_, msg, wp, lp):
            if msg == WM_DROPFILES:
                try:
                    paths = _query_paths(shell32, wp)
                    widget.after(0, lambda: callback(paths))
                except Exception:
                    pass
                finally:
                    try:
                        shell32.DragFinish(wp)
                    except Exception:
                        pass
                return 0
            try:
                old = _hooks[hwnd_][0]
            except KeyError:
                return 0
            return call_proc(old, hwnd_, msg, wp, lp)

        proc = WNDPROC(handler)
        old_proc = set_long(hwnd, GWL_WNDPROC, ctypes.cast(proc, ctypes.c_void_p))
        if not old_proc:
            return False
        _hooks[hwnd] = (old_proc, proc, widget)
        shell32.DragAcceptFiles(hwnd, True)
        return True
    except Exception:
        return False


def disable_drop(widget) -> None:
    """終了時にWndProcを復元する。失敗しても無視。"""
    if os.name != "nt":
        return
    try:
        hwnd = widget.winfo_id()
        hook = _hooks.pop(hwnd, None)
        if not hook:
            return
        old_proc, _, _ = hook
        _, _, set_long, _, _ = _setup_procs()

        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32
        try:
            shell32.DragAcceptFiles(hwnd, False)
        except Exception:
            pass
        try:
            if user32.IsWindow(hwnd):
                set_long(hwnd, GWL_WNDPROC, ctypes.c_void_p(old_proc))
        except Exception:
            pass
    except Exception:
        pass
