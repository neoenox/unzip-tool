"""解凍ロジック。GUIから分離してテスト可能に。
zip/tarは標準ライブラリのみ。rarは rarfile + 外部UnRARが必要。
"""
from __future__ import annotations

import os
import shutil
import sys
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

ArchiveKind = Literal["zip", "tar", "rar", "7z"]

SUPPORTED_SUFFIXES = (".zip", ".7z", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz", ".tar.xz", ".txz", ".rar")

RAR_TOOL_HELP = (
    "RARの展開には別途 UnRAR が必要です。"
    "WinRARをインストールするか、UnRAR.exe を toolsフォルダに置くか、"
    "環境変数 KANTAN_UNRAR にパスを指定してください。"
)


class PasswordRequiredError(ValueError):
    """パスワードが必要、または間違っている。GUIは入力欄を出して再試行させる。"""


def is_supported(path: str | os.PathLike) -> bool:
    name = str(path).lower()
    return name.endswith(SUPPORTED_SUFFIXES)


def detect_kind(path: str | os.PathLike) -> ArchiveKind:
    name = str(path).lower()
    if name.endswith(".zip"):
        return "zip"
    if name.endswith(".rar"):
        return "rar"
    if name.endswith(".7z"):
        return "7z"
    if name.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz", ".tar.xz", ".txz")):
        return "tar"
    raise ValueError(f"未対応の形式です: {path}")


def _base_dirs() -> list[Path]:
    """アプリ基点の探索場所。exe化時はexe隣と展開先も見る。"""
    dirs = [Path(__file__).resolve().parent]
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        dirs.append(exe_dir)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            dirs.append(Path(meipass))
    return dirs


def find_unrar_tool() -> Path | None:
    """UnRAR.exe を探す。環境変数 > tools隣接 > WinRAR > PATH の順。"""
    cands: list[Path] = []
    env = os.environ.get("KANTAN_UNRAR", "").strip().strip('"')
    if env:
        cands.append(Path(env))
    for base in _base_dirs():
        cands.append(base / "tools" / "UnRAR.exe")
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pfx = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    cands.append(Path(pf) / "WinRAR" / "UnRAR.exe")
    cands.append(Path(pfx) / "WinRAR" / "UnRAR.exe")
    for c in cands:
        try:
            if c.is_file():
                return c
        except OSError:
            continue
    for name in ("UnRAR.exe", "unrar.exe", "unrar"):
        w = shutil.which(name)
        if w:
            return Path(w)
    return None


_rar_tool_ready = False


def _setup_rar_tool() -> None:
    """rarfileにUnRARを設定する (プロセス毎に1回)。無ければ案内付きで失敗する。"""
    global _rar_tool_ready
    if _rar_tool_ready:
        return
    try:
        import rarfile
    except ImportError:
        raise ValueError("rarfile がありません (pip install -r requirements.txt)")
    tool = find_unrar_tool()
    if tool is None:
        raise ValueError(RAR_TOOL_HELP)
    rarfile.UNRAR_TOOL = str(tool)
    try:
        rarfile.tool_setup()
    except Exception:
        raise ValueError(RAR_TOOL_HELP + f" (検出: {tool})")
    _rar_tool_ready = True


def _is_zip_password_error(e: Exception) -> bool:
    msg = str(e).lower()
    return isinstance(e, RuntimeError) and ("password" in msg or "encrypted" in msg)


def archive_needs_password(archive: str | os.PathLike) -> bool:
    """展開にパスワードが要るか。壊れた書庫ではFalseを返し、後段の本処理に任せる。"""
    kind = detect_kind(archive)
    try:
        if kind == "zip":
            with zipfile.ZipFile(archive, "r") as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    try:
                        zf.open(info).close()
                    except RuntimeError as e:
                        if _is_zip_password_error(e):
                            return True
                        raise
                return False
        elif kind == "rar":
            import rarfile

            _setup_rar_tool()
            try:
                with rarfile.RarFile(archive) as rf:
                    return bool(rf.needs_password())
            except (rarfile.PasswordRequired, rarfile.RarWrongPassword):
                return True
        elif kind == "7z":
            import py7zr

            try:
                with py7zr.SevenZipFile(archive, mode="r") as sf:
                    return bool(sf.needs_password())
            except py7zr.exceptions.PasswordRequired:
                return True
    except PasswordRequiredError:
        return True
    except Exception:
        return False
    return False


def _decode_zip_name(raw: str) -> str:
    """日本語zipの文字化け対策。

    Windows製zipは UTF-8フラグ無しで Shift_JIS(cp932) のまま cp437 として
    デコードされることが多い。復元を試み、ダメなら元の名前を返す。
    """
    try:
        raw.encode("cp437")
    except UnicodeEncodeError:
        # 既に正しくデコードされている (UTF-8フラグ付き等)
        return raw
    for enc in ("cp932", "shift_jis", "utf-8"):
        try:
            return raw.encode("cp437").decode(enc)
        except (UnicodeDecodeError, UnicodeEncodeError):
            continue
    return raw


def _safe_join(base: Path, *parts: str) -> Path:
    """Zip Slip対策: base 配下に収まらないパスは拒否する。"""
    target = (base.joinpath(*parts)).resolve()
    base_resolved = base.resolve()
    if target != base_resolved and base_resolved not in target.parents:
        raise ValueError(f"危険なパスをスキップしました: {os.path.join(*parts)}")
    return target


@dataclass
class Entry:
    name: str
    size: int
    is_dir: bool


def _as_str_pwd(password: bytes | str | None) -> str | None:
    if isinstance(password, bytes):
        return password.decode("utf-8", "ignore")
    return password


def list_contents(
    archive: str | os.PathLike,
    password: bytes | None = None,
) -> list[Entry]:
    kind = detect_kind(archive)
    entries: list[Entry] = []
    if kind == "zip":
        with zipfile.ZipFile(archive, "r") as zf:
            for info in zf.infolist():
                name = _decode_zip_name(info.filename)
                entries.append(
                    Entry(name=name, size=info.file_size, is_dir=info.is_dir())
                )
    elif kind == "rar":
        import rarfile

        _setup_rar_tool()
        try:
            with rarfile.RarFile(archive) as rf:
                for info in rf.infolist():
                    entries.append(Entry(name=info.filename, size=info.file_size, is_dir=info.is_dir()))
        except (rarfile.PasswordRequired, rarfile.RarWrongPassword) as e:
            raise PasswordRequiredError("パスワードが必要です") from e
    elif kind == "7z":
        import py7zr

        try:
            with py7zr.SevenZipFile(archive, mode="r", password=_as_str_pwd(password)) as sf:
                for info in sf.list():
                    size = getattr(info, "uncompressed", 0) or 0
                    entries.append(Entry(name=info.filename, size=size, is_dir=bool(info.is_directory)))
        except py7zr.exceptions.PasswordRequired as e:
            raise PasswordRequiredError("パスワードが必要です") from e
    else:
        with tarfile.open(archive, "r:*") as tf:
            for m in tf.getmembers():
                entries.append(Entry(name=m.name, size=m.size or 0, is_dir=m.isdir()))
    return entries


def _check_names_safe(base: Path, names: list[str]) -> None:
    """展開前に全名を検査する (7zは一括展開のため事前検査)。1つでも危険なら全体を拒否。"""
    for name in names:
        _safe_join(base, Path(name).as_posix().lstrip("/"))


ProgressCb = Callable[[int, int], None]  # (完了件数, 全体件数)


def extract_archive(
    archive: str | os.PathLike,
    dest: str | os.PathLike,
    on_progress: ProgressCb | None = None,
    password: bytes | None = None,
) -> Path:
    """アーカイブを dest に解凍して dest の Path を返す。
    パスワード不足・誤りの場合は PasswordRequiredError を投げる (中途半端な
    展開で止めず、呼び出し側で入力を求めて再試行させるため、事前に検出する)。
    """
    if not is_supported(archive):
        raise ValueError(f"未対応の形式です: {archive}")
    if not password and archive_needs_password(archive):
        raise PasswordRequiredError("パスワードが必要です")
    dest_path = Path(dest)
    dest_path.mkdir(parents=True, exist_ok=True)
    kind = detect_kind(archive)

    if kind == "zip":
        with zipfile.ZipFile(archive, "r") as zf:
            infos = zf.infolist()
            total = len(infos)
            for i, info in enumerate(infos, 1):
                fixed = _decode_zip_name(info.filename)
                out = _safe_join(dest_path, Path(fixed).as_posix().lstrip("/"))
                if info.is_dir():
                    out.mkdir(parents=True, exist_ok=True)
                else:
                    out.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        with zf.open(info, pwd=password) as src, open(out, "wb") as fp:
                            fp.write(src.read())
                    except RuntimeError as e:
                        if _is_zip_password_error(e):
                            raise PasswordRequiredError("パスワードが必要か、間違っています") from e
                        raise
                if on_progress:
                    on_progress(i, total)
    elif kind == "rar":
        import rarfile

        _setup_rar_tool()
        pwd = _as_str_pwd(password)
        try:
            with rarfile.RarFile(archive) as rf:
                infos = rf.infolist()
                total = len(infos)
                for i, info in enumerate(infos, 1):
                    out = _safe_join(dest_path, Path(info.filename).as_posix().lstrip("/"))
                    if info.is_dir():
                        out.mkdir(parents=True, exist_ok=True)
                    else:
                        out.parent.mkdir(parents=True, exist_ok=True)
                        with rf.open(info, pwd=pwd) as src, open(out, "wb") as fp:
                            shutil.copyfileobj(src, fp)
                    if on_progress:
                        on_progress(i, total)
        except (rarfile.PasswordRequired, rarfile.RarWrongPassword) as e:
            raise PasswordRequiredError("パスワードが必要か、間違っています") from e
    elif kind == "7z":
        import py7zr

        pwd = _as_str_pwd(password)
        try:
            with py7zr.SevenZipFile(archive, mode="r", password=pwd) as sf:
                names = [info.filename for info in sf.list()]
                _check_names_safe(dest_path, names)
                if on_progress:
                    on_progress(0, max(len(names), 1))
                sf.extractall(path=dest_path)
                if on_progress:
                    on_progress(max(len(names), 1), max(len(names), 1))
        except py7zr.exceptions.PasswordRequired as e:
            raise PasswordRequiredError("パスワードが必要です") from e
        except Exception as e:
            # 誤パスワード時はLZMAError等で失敗する。暗号書庫ならPW誤り扱い。
            if pwd and archive_needs_password(archive):
                raise PasswordRequiredError("パスワードが違うか、ファイルが壊れています") from e
            raise
    else:
        with tarfile.open(archive, "r:*") as tf:
            members = tf.getmembers()
            total = len(members)
            for i, m in enumerate(members, 1):
                out = _safe_join(dest_path, m.name.lstrip("/"))
                if m.isdir():
                    out.mkdir(parents=True, exist_ok=True)
                elif m.isfile():
                    out.parent.mkdir(parents=True, exist_ok=True)
                    src = tf.extractfile(m)
                    if src is None:
                        continue
                    with src, open(out, "wb") as fp:
                        fp.write(src.read())
                # シンボリックリンク等はセキュリティのためスキップ (シンプル版)
                if on_progress:
                    on_progress(i, total)

    return dest_path


def default_dest_for(archive: str | os.PathLike) -> Path:
    """アーカイブと同じ場所に「名前のみ」のフォルダを切る場合の既定値。"""
    p = Path(archive)
    name = p.name
    lower = name.lower()
    for suf in (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz", ".txz", ".zip", ".rar", ".7z", ".tar"):
        if lower.endswith(suf):
            name = name[: -len(suf)]
            break
    return p.parent / name
