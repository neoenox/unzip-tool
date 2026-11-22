"""Windows ファイルドラッグ&ドロップ (WM_DROPFILES / ctypes、標準ライブラリのみ)。

tkinter にはファイルDnDが無いため、ウィンドウに WM_DROPFILES を受け付ける。
Windows以外では enable_drop() は False を返し、何もしない。
"""
from __future__ import annotations

import ctypes
import os

import dnd_ole
from dnd_common import MAX_FILES, hdrop_valid as _hdrop_valid, query_paths as _query_paths

WM_DROPFILES = 0x0233
GWL_WNDPROC = -4


# hwnd -> (旧WndProc, 新WndProcへの参照) ※参照保持しないとGCでクラッシュする
_hooks: dict[int, tuple[int, object]] = {}

# hwnd -> 未処理のドロップ [{paths}, ...]
# WndProc内ではTkを一切触らない (別プロセスからの通知時に再入すると
# インタプリタごと落ちるため)。取り出しはメインループ側のpollで行う。
_pending: dict[int, list[list[str]]] = {}

# hwnd -> 上限を超えてドロップされ、取り出されなかった件数
_truncated: dict[int, int] = {}


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
                need_finish = False
                try:
                    if _hdrop_valid(kernel32, wp):
                        need_finish = True
                        paths, skipped = _query_paths(shell32, wp)
                        _pending.setdefault(hwnd_, []).append(paths)
                        if skipped:
                            _truncated[hwnd_] = _truncated.get(hwnd_, 0) + skipped
                except Exception:
                    pass
                finally:
                    if need_finish:
                        try:
                            shell32.DragFinish(wp)
                        except Exception:
                            pass

                # DragFinish 済みの HDROP は旧 WndProc へ渡さない
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
        # ドロップされたパスと超過件数を poll 側へ渡す (OLE も同じ経路)
        def store_paths(paths, skipped):
            _pending.setdefault(hwnd, []).append(paths)
            if skipped:
                _truncated[hwnd] = _truncated.get(hwnd, 0) + skipped

        dnd_ole.register(hwnd, store_paths)
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

def take_truncated_files(widget) -> int:
    """上限超過で破棄した件数を取り出し、クリアする (メインスレッドのみ)。"""
    if os.name != "nt":
        return 0
    try:
        return _truncated.pop(widget.winfo_id(), 0)
    except Exception:
        return 0


def disable_drop(widget) -> None:
    """終了時にWndProcを復元する。失敗しても無視。"""
    if os.name != "nt":
        return
    try:
        hwnd = widget.winfo_id()
        dnd_ole.revoke(hwnd)
        hook = _hooks.pop(hwnd, None)
        _pending.pop(hwnd, None)
        _truncated.pop(hwnd, None)
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


def is_drag_over(widget) -> bool:
    """ドラッグがこのウィンドウ上にあるか (メインスレッドのpollからのみ呼ぶ)。"""
    if os.name != "nt":
        return False
    try:
        return dnd_ole.is_drag_over(widget.winfo_id())
    except Exception:
        return False
