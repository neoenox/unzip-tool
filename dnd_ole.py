"""OLE ドロップターゲット (IDropTarget) — ドラッグ中の状態通知のみを担当する。

`WM_DROPFILES` はドロップした瞬間しか通知しないため、「ドラッグ中」の
視覚フィードバック (#29) には OLE の `IDropTarget` が必要になる。

設計上の制約 (dnd.py と同じ):
- コールバック内では Tk を一切触らない。状態フラグとパス列の蓄積だけを行う。
- 取り出しはメインループ側の poll (`is_drag_over` / 親の `take_dropped_files`)。
- 登録に失敗した場合は現行の `WM_DROPFILES` 経路がそのまま動く (フォールバック)。

このモジュールは Windows 専用。それ以外では `register()` が False を返し、
関数定義も `WINFUNCTYPE` に依存しないため import は全プラットフォームで成功する。
"""
from __future__ import annotations

import ctypes
import os

HRESULT = ctypes.c_long
ULONG = ctypes.c_ulong
DWORD = ctypes.c_ulong
LONG = ctypes.c_long

CF_HDROP = 15
DVASPECT_CONTENT = 1
TYMED_HGLOBAL = 1
DROPEFFECT_COPY = 1
S_OK = 0
S_FALSE = 1
E_NOINTERFACE = -2147467262  # 0x80004002

MAX_FILES = 64  # dnd.py と揃える

# WINFUNCTYPE は Windows のみ。非 Windows でも import できるようにする
# (実行時に register() が False を返すので、その先は使われない)。
_FUNCTYPE = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(data1, tail):
    return GUID(data1, 0, 0, (ctypes.c_ubyte * 8)(0xC0, 0, 0, 0, 0, 0, 0, tail))


IID_IUNKNOWN = _guid(0x00000000, 0x46)
IID_IDROPTARGET = _guid(0x00000122, 0x46)


class POINT(ctypes.Structure):
    _fields_ = [("x", LONG), ("y", LONG)]


class FORMATETC(ctypes.Structure):
    _fields_ = [
        ("cfFormat", ctypes.c_ushort),
        ("ptd", ctypes.c_void_p),
        ("dwAspect", DWORD),
        ("lindex", ctypes.c_long),
        ("tymed", DWORD),
    ]


class STGMEDIUM(ctypes.Structure):
    # 共用体は HGLOBAL (CF_HDROP の実体) だけを読む。
    _fields_ = [
        ("tymed", DWORD),
        ("hGlobal", ctypes.c_void_p),
        ("pUnkForRelease", ctypes.c_void_p),
    ]


_QueryInterface = _FUNCTYPE(
    HRESULT, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))
_AddRef = _FUNCTYPE(ULONG, ctypes.c_void_p)
_Release = _FUNCTYPE(ULONG, ctypes.c_void_p)
_DragEnter = _FUNCTYPE(
    HRESULT, ctypes.c_void_p, ctypes.c_void_p, DWORD, POINT, ctypes.POINTER(DWORD))
_DragOver = _FUNCTYPE(
    HRESULT, ctypes.c_void_p, DWORD, POINT, ctypes.POINTER(DWORD))
_DragLeave = _FUNCTYPE(HRESULT, ctypes.c_void_p)
_Drop = _DragEnter
_GetData = _FUNCTYPE(
    HRESULT, ctypes.c_void_p, ctypes.POINTER(FORMATETC), ctypes.POINTER(STGMEDIUM))


class _Vtbl(ctypes.Structure):
    _fields_ = [
        ("QueryInterface", _QueryInterface),
        ("AddRef", _AddRef),
        ("Release", _Release),
        ("DragEnter", _DragEnter),
        ("DragOver", _DragOver),
        ("DragLeave", _DragLeave),
        ("Drop", _Drop),
    ]


# hwnd -> ドラッグ中か (コールバックが書き、poll が読む)
_drag_over: dict[int, bool] = {}
# hwnd -> 登録済みターゲット (参照保持しないとGCで落ちる)
_targets: dict[int, "_DropTarget"] = {}


def _same_guid(a: GUID, b: GUID) -> bool:
    size = ctypes.sizeof(GUID)
    return ctypes.string_at(ctypes.byref(a), size) == ctypes.string_at(ctypes.byref(b), size)


def _query_paths(hdrop) -> list[str]:
    """HDROP (CF_HDROP の STGMEDIUM) からパスを取り出す。読み取り専用。"""
    from ctypes import wintypes
    shell32 = ctypes.windll.shell32
    shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
    shell32.DragQueryFileW.restype = wintypes.UINT
    count = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
    paths: list[str] = []
    for i in range(min(count, MAX_FILES)):
        length = shell32.DragQueryFileW(hdrop, i, None, 0)
        buf = ctypes.create_unicode_buffer(length + 1)
        shell32.DragQueryFileW(hdrop, i, buf, length + 1)
        paths.append(buf.value)
    return paths


def _paths_from_data_object(data_obj) -> list[str]:
    """IDataObject から CF_HDROP を取り出す。失敗時は空リスト。"""
    if not data_obj:
        return []
    ole32 = ctypes.windll.ole32
    ole32.ReleaseStgMedium.argtypes = [ctypes.POINTER(STGMEDIUM)]
    ole32.ReleaseStgMedium.restype = None
    vtable = ctypes.cast(data_obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    get_data = _GetData(vtable[3])  # IUnknown(3) の次が GetData
    fmt = FORMATETC(cfFormat=CF_HDROP, ptd=None, dwAspect=DVASPECT_CONTENT,
                    lindex=-1, tymed=TYMED_HGLOBAL)
    stg = STGMEDIUM()
    if get_data(data_obj, ctypes.byref(fmt), ctypes.byref(stg)) != 0:
        return []
    try:
        if stg.tymed != TYMED_HGLOBAL or not stg.hGlobal:
            return []
        return _query_paths(stg.hGlobal)
    finally:
        ole32.ReleaseStgMedium(ctypes.byref(stg))


class _DropTarget:
    """IDropTarget の最小実装。Tk には触れない。"""

    def __init__(self, hwnd: int, store_paths):
        self.hwnd = int(hwnd)
        self._store_paths = store_paths
        self.refs = 1
        self._vtbl = _Vtbl(
            _QueryInterface(self._query_interface),
            _AddRef(self._add_ref),
            _Release(self._release),
            _DragEnter(self._drag_enter),
            _DragOver(self._drag_over),
            _DragLeave(self._drag_leave),
            _Drop(self._drop),
        )
        # COM インターフェース = 「vtable へのポインタ」へのポインタ
        self._iface = (ctypes.c_void_p * 1)(ctypes.cast(ctypes.byref(self._vtbl), ctypes.c_void_p))
        self.pointer = ctypes.cast(self._iface, ctypes.c_void_p)

    # --- IUnknown ---
    def _query_interface(self, this, riid, ppv):
        if riid and ppv:
            guid = riid.contents
            if _same_guid(guid, IID_IUNKNOWN) or _same_guid(guid, IID_IDROPTARGET):
                ppv[0] = self.pointer.value
                self.refs += 1
                return S_OK
        return E_NOINTERFACE

    def _add_ref(self, this):
        self.refs += 1
        return self.refs

    def _release(self, this):
        self.refs = max(0, self.refs - 1)
        return self.refs

    # --- IDropTarget ---
    def _drag_enter(self, this, data_obj, key_state, pt, effect):
        _drag_over[self.hwnd] = True
        if effect:
            effect[0] = DROPEFFECT_COPY
        return S_OK

    def _drag_over(self, this, key_state, pt, effect):
        _drag_over[self.hwnd] = True
        if effect:
            effect[0] = DROPEFFECT_COPY
        return S_OK

    def _drag_leave(self, this):
        _drag_over[self.hwnd] = False
        return S_OK

    def _drop(self, this, data_obj, key_state, pt, effect):
        _drag_over[self.hwnd] = False
        try:
            paths = _paths_from_data_object(data_obj)
            if paths:
                self._store_paths(paths)
        except Exception:
            pass
        if effect:
            effect[0] = DROPEFFECT_COPY
        return S_OK


def _ole32():
    ole32 = ctypes.windll.ole32
    ole32.OleInitialize.argtypes = [ctypes.c_void_p]
    ole32.OleInitialize.restype = HRESULT
    ole32.RegisterDragDrop.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    ole32.RegisterDragDrop.restype = HRESULT
    ole32.RevokeDragDrop.argtypes = [ctypes.c_void_p]
    ole32.RevokeDragDrop.restype = HRESULT
    return ole32


def register(hwnd: int, store_paths) -> bool:
    """hwnd に OLE ドロップターゲットを登録する。成功で True。

    store_paths(paths) はドロップされたパス列の受け渡し先 (Tk 非依存)。
    """
    if os.name != "nt" or not hwnd:
        return False
    if int(hwnd) in _targets:
        return True
    try:
        ole32 = _ole32()
        hr = ole32.OleInitialize(None)
        if hr not in (S_OK, S_FALSE):  # 既に初期化済みでも可
            return False
        target = _DropTarget(int(hwnd), store_paths)
        if ole32.RegisterDragDrop(int(hwnd), target.pointer) != S_OK:
            return False
        _targets[int(hwnd)] = target
        _drag_over[int(hwnd)] = False
        return True
    except Exception:
        return False


def revoke(hwnd: int) -> None:
    """登録を解除する。失敗しても無視。"""
    if os.name != "nt" or not hwnd:
        return
    try:
        ole32 = _ole32()
        ole32.RevokeDragDrop(int(hwnd))
    except Exception:
        pass
    _targets.pop(int(hwnd), None)
    _drag_over.pop(int(hwnd), None)


def has_target(hwnd: int) -> bool:
    return int(hwnd) in _targets


def is_drag_over(hwnd: int) -> bool:
    return bool(_drag_over.get(int(hwnd), False))

