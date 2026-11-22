"""WM_DROPFILES / OLE で共有する HDROP 処理 (Tk 非依存、ctypes のみ)。"""
from __future__ import annotations

import ctypes

MAX_FILES = 64  # 一度に取り出すパスの上限
GMEM_INVALID_HANDLE = 0x8000  # GlobalFlags(): 無効ハンドル


def hdrop_valid(kernel32, hdrop) -> bool:
    """自プロセスから触れる HDROP か。ゴミ/NULL には触れない。"""
    if not hdrop:
        return False
    try:
        return (kernel32.GlobalFlags(hdrop) & GMEM_INVALID_HANDLE) == 0
    except Exception:
        return False


def query_paths(shell32, hdrop) -> tuple[list[str], int]:
    """パス列と、上限を超えて破棄した件数を返す。"""
    count = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
    paths: list[str] = []
    for i in range(min(count, MAX_FILES)):
        length = shell32.DragQueryFileW(hdrop, i, None, 0)
        buf = ctypes.create_unicode_buffer(length + 1)
        shell32.DragQueryFileW(hdrop, i, buf, length + 1)
        paths.append(buf.value)
    return paths, max(0, count - MAX_FILES)
