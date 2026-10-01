"""Windows ファイルドラッグ&ドロップ (WM_DROPFILES / ctypes、標準ライブラリのみ)。

tkinter にはファイルDnDが無いため、ウィンドウに WM_DROPFILES を受け付ける。
Windows以外では enable_drop() は False を返し、何もしない。
"""
from __future__ import annotations

import ctypes
import os

WM_DROPFILES = 0x0233
GWL_WNDPROC = -4
MAX_FILES = 64  # 取り出し上限 (シンプル版)

# hwnd -> (旧WndProc, 新WndProcへの参照) ※参照保持しないとGCでクラッシュする
_hooks: dict[int, tuple[int, object]] = {}

# hwnd -> 未処理のドロップ [{paths}, ...]
# WndProc内ではTkを一切触らない (別プロセスからの通知時に再入すると
# インタプリタごと落ちるため)。取り出しはメインループ側のpollで行う。
_pending: dict[int, list[list[str]]] = {}


def _setup_procs():
    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32
    kernel32 = ctypes.windll.kernel32
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

    kernel32.GlobalFlags.argtypes = [wintypes.HANDLE]
    kernel32.GlobalFlags.restype = wintypes.UINT

    WNDPROC = ctypes.WINFUNCTYPE(wintypes.LPARAM, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    return user32, shell32, kernel32, set_long, call_proc, WNDPROC


GMEM_INVALID_HANDLE = 0x8000


def _hdrop_valid(kernel32, hdrop: int) -> bool:
    """自プロセスから見て有効なHDROPか。ゴミ/NULLには触らない。"""
    if not hdrop:
        return False
    try:
        return (kernel32.GlobalFlags(hdrop) & GMEM_INVALID_HANDLE) == 0
    except Exception:
        return False


def _query_paths(shell32, hdrop: int) -> list[str]:
    count = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
    paths: list[str] = []
    for i in range(min(count, MAX_FILES)):
        length = shell32.DragQueryFileW(hdrop, i, None, 0)
        buf = ctypes.create_unicode_buffer(length + 1)
        shell32.DragQueryFileW(hdrop, i, buf, length + 1)
        paths.append(buf.value)
    return paths


def enable_drop(widget) -> bool:
    """widget(トップレベル)へのファイルドロップを有効化。成功時True。
    通知は take_dropped_files() でpollして受け取る (コールバック方式は
    別プロセス通知時の再入で落ちるため使わない)。"""
    if os.name != "nt":
        return False
    try:
        widget.update_idletasks()
        hwnd = widget.winfo_id()
        user32, shell32, kernel32, set_long, call_proc, WNDPROC = _setup_procs()
        if not user32.IsWindow(hwnd):
            return False
        if hwnd in _hooks:
            return True

        def handler(hwnd_, msg, wp, lp):
            if msg == WM_DROPFILES:
                # Tk呼び出し禁止: 純Python+ctypesだけで完結させる。
                # 無効ハンドルには一切触らない (他プロセスのゴミで破壊を防ぐ)。
                valid = False
                try:
                    valid = _hdrop_valid(kernel32, wp)
                    if valid:
                        paths = _query_paths(shell32, wp)
                        _pending.setdefault(hwnd_, []).append(paths)
                except Exception:
                    valid = False
                finally:
                    if valid:
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
        _hooks[hwnd] = (old_proc, proc)
        shell32.DragAcceptFiles(hwnd, True)
        return True
    except Exception:
        return False


def take_dropped_files(widget) -> list[list[str]]:
    """未処理のドロップを取り出す (メインスレッドのpollからのみ呼ぶ)。"""
    if os.name != "nt":
        return []
    try:
        return _pending.pop(widget.winfo_id(), [])
    except Exception:
        return []


def disable_drop(widget) -> None:
    """終了時にWndProcを復元する。失敗しても無視。"""
    if os.name != "nt":
        return
    try:
        hwnd = widget.winfo_id()
        hook = _hooks.pop(hwnd, None)
        if not hook:
            return
        old_proc, _ = hook
        _, _, _, set_long, _, _ = _setup_procs()

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
