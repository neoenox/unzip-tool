"""解凍ロジック。GUIから分離してテスト可能に。
zip/tarは標準ライブラリのみ。rarは rarfile + 外部UnRARが必要。
"""
from __future__ import annotations

import os
import errno
import lzma
import shutil
import stat
import tempfile
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


class PasswordRequiredError(ValueError):
    """A password is missing or incorrect."""


def error_message(error: Exception) -> str:
    """Translate actionable filesystem/archive failures at the UI boundary."""
    if isinstance(error, OSError):
        if error.errno == errno.ENOSPC or getattr(error, 'winerror', None) == 112:
            return '保存先の空き容量が不足しています。空き容量を増やすか、別の保存先を選んで再試行してください。'
        if error.errno in (errno.EACCES, errno.EPERM) or getattr(error, 'winerror', None) == 5:
            return 'ファイルにアクセスできません。書庫や保存先のアクセス権を確認し、別の保存先で再試行してください。'
    import py7zr
    import rarfile
    if isinstance(error, (zipfile.BadZipFile, tarfile.ReadError, lzma.LZMAError,
                          py7zr.exceptions.Bad7zFile, py7zr.exceptions.CrcError,
                          rarfile.BadRarFile, rarfile.RarCRCError)):
        return '書庫が壊れているか、形式が正しくありません。ファイルを再取得してお試しください。'
    return str(error)


def _password_error(error: Exception) -> bool:
    return isinstance(error, RuntimeError) and any(
        word in str(error).lower() for word in ("password", "encrypted"))


def _password_text(password: bytes | None) -> str | None:
    return password.decode("utf-8") if password else None


def _safe_join(base: Path, *parts: str) -> Path:
    name = "/".join(parts).replace("\\", "/")
    if name.startswith("/") or ":" in name:
        raise ValueError(f"危険なパスです: {name}")
    segments = name.split("/")
    reserved = {"con", "prn", "aux", "nul", "conin$", "conout$"}
    reserved.update(f"{prefix}{i}" for prefix in ("com", "lpt") for i in "123456789¹²³")
    for segment in segments:
        if segment in ("", "."):
            continue
        if (segment == ".." or segment.endswith((".", " "))
                or any(ord(c) < 32 or c in '<>"|?*' for c in segment)
                or segment.split(".")[0].casefold() in reserved):
            raise ValueError(f"Windowsで安全に保存できない名前です: {name}")
    target = base.joinpath(*[x for x in segments if x not in ("", ".")]).resolve()
    root = base.resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"危険なパスです: {name}")
    return target


@dataclass
class Entry:
    name: str
    size: int
    is_dir: bool


def _zip_name(info) -> str:
    return info.filename if info.flag_bits & 0x800 else _decode_zip_name(info.filename)


def list_contents(archive: str | os.PathLike, password: bytes | None = None) -> list[Entry]:
    kind = detect_kind(archive)
    if kind == "zip":
        with zipfile.ZipFile(archive) as zf:
            return [Entry(_zip_name(i), i.file_size, i.is_dir()) for i in zf.infolist()]
    if kind == "tar":
        with tarfile.open(archive, "r:*") as tf:
            return [Entry(i.name, i.size, i.isdir()) for i in tf.getmembers()]
    if kind == "rar":
        import rarfile
        _setup_rar_tool()
        try:
            with rarfile.RarFile(archive) as rf:
                if password:
                    rf.setpassword(_password_text(password))
                return [Entry(i.filename, i.file_size, i.is_dir()) for i in rf.infolist()]
        except (rarfile.PasswordRequired, rarfile.RarWrongPassword) as e:
            raise PasswordRequiredError("パスワードを入力してください。") from e
    import py7zr
    try:
        with py7zr.SevenZipFile(archive, password=_password_text(password)) as sf:
            return [Entry(i.filename, i.uncompressed or 0, i.is_directory) for i in sf.list()]
    except py7zr.exceptions.PasswordRequired as e:
        raise PasswordRequiredError("パスワードを入力してください。") from e
    except (py7zr.exceptions.Bad7zFile, TypeError, ValueError, EOFError, lzma.LZMAError) as e:
        if password and archive_needs_password(archive):
            raise PasswordRequiredError("パスワードが違うか、書庫が壊れています。入力して再試行してください。") from e
        raise


def archive_needs_password(archive: str | os.PathLike) -> bool:
    kind = detect_kind(archive)
    if kind == "zip":
        with zipfile.ZipFile(archive) as zf:
            return any(i.flag_bits & 1 for i in zf.infolist())
    if kind == "rar":
        import rarfile
        with rarfile.RarFile(archive) as rf:
            return rf.needs_password()
    if kind == "7z":
        import py7zr
        try:
            with py7zr.SevenZipFile(archive) as sf:
                return sf.needs_password()
        except py7zr.exceptions.PasswordRequired:
            return True
    return False


def _archive_needs_password_quiet(archive: str | os.PathLike) -> bool:
    try:
        return archive_needs_password(archive)
    except Exception:
        return False


def _validate_entries(base: Path, entries: list[Entry]) -> None:
    seen: dict[str, bool] = {}
    for entry in entries:
        target = _safe_join(base, entry.name)
        key = target.relative_to(base.resolve()).as_posix().casefold()
        if key == "." and entry.is_dir:
            continue
        if key == "." or key in seen:
            raise ValueError(f"名前が重複しています: {entry.name}")
        seen[key] = entry.is_dir
    for key in seen:
        parent = Path(key).parent
        while str(parent) != ".":
            if seen.get(parent.as_posix()) is False:
                raise ValueError(f"ファイルとフォルダの名前が衝突しています: {key}")
            parent = parent.parent


def _check_names_safe(base: Path, names: list[str]) -> None:
    for name in names:
        _safe_join(base, name)


ProgressCb = Callable[[int, int], None]


def _extract_into(archive: str | os.PathLike, dest: Path,
                  on_progress: ProgressCb | None = None, password: bytes | None = None,
                  on_file: Callable[[str], None] | None = None,
                  on_bytes: ProgressCb | None = None) -> None:
    """Write into a private staging directory; never publish from a worker."""
    kind = detect_kind(archive)
    entries = list_contents(archive, password)
    _validate_entries(dest, entries)
    if not entries and not password and _archive_needs_password_quiet(archive):
        # ヘッダ暗号化RAR等: 一覧が空でもPW要求ありなら空フォルダを作らず促す
        raise PasswordRequiredError("パスワードを入力してください。")
    total_bytes = sum(entry.size for entry in entries if not entry.is_dir)
    copied = 0
    class ProgressReader:
        def __init__(self, source):
            self.source = source
        def read(self, size):
            nonlocal copied
            data = self.source.read(size)
            copied += len(data)
            if on_bytes:
                on_bytes(copied, total_bytes)
            return data
    def copy_members(members, open_member):
        for i, (entry, member) in enumerate(zip(entries, members), 1):
            if on_file:
                on_file(entry.name)
            out = _safe_join(dest, entry.name)
            if entry.is_dir:
                out.mkdir(parents=True, exist_ok=True)
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                with open_member(member) as src, open(out, "xb") as fp:
                    shutil.copyfileobj(ProgressReader(src), fp, length=1024 * 1024)
            if on_progress:
                on_progress(i, len(entries))
    if kind == "zip":
        with zipfile.ZipFile(archive) as zf:
            infos = zf.infolist()
            if any(stat.S_IFMT(i.external_attr >> 16) not in (0, stat.S_IFREG, stat.S_IFDIR) for i in infos):
                raise ValueError("リンクや特殊ファイルを含む書庫は解凍できません。")
            try:
                copy_members(infos, lambda i: zf.open(i, pwd=password))
            except RuntimeError as e:
                if _password_error(e):
                    raise PasswordRequiredError("パスワードが必要か、間違っています。入力して再試行してください。") from e
                raise
    elif kind == "tar":
        with tarfile.open(archive, "r:*") as tf:
            members = tf.getmembers()
            if any(not (m.isdir() or m.isfile()) for m in members):
                raise ValueError("リンクや特殊ファイルを含む書庫は解凍できません。")
            copy_members(members, tf.extractfile)
    elif kind == "rar":
        import rarfile
        _setup_rar_tool()
        try:
            with rarfile.RarFile(archive) as rf:
                if password:
                    rf.setpassword(_password_text(password))
                members = rf.infolist()
                if any(i.is_symlink() or getattr(i, "file_redir", None) for i in members):
                    raise ValueError("リンクを含む書庫は解凍できません。")
                copy_members(members, lambda i: rf.open(i, pwd=_password_text(password)))
        except (rarfile.PasswordRequired, rarfile.RarWrongPassword) as e:
            raise PasswordRequiredError("パスワードが必要か、間違っています。入力して再試行してください。") from e
        except (rarfile.BadRarFile, rarfile.RarCRCError) as e:
            # 誤PWでは復号結果が壊れてCRC/読み切り失敗になる。PW付きで
            # 暗号書庫なら「違うか壊れている」に寄せ、素の破損はそのまま。
            if password and _archive_needs_password_quiet(archive):
                raise PasswordRequiredError("パスワードが違うか、書庫が壊れています。入力して再試行してください。") from e
            raise
    else:
        import py7zr
        try:
            with py7zr.SevenZipFile(archive, password=_password_text(password)) as sf:
                if any(not (i.is_directory or i.is_file) or i.is_symlink or i.is_junction for i in sf.files):
                    raise ValueError("リンクや特殊ファイルを含む書庫は解凍できません。")
                if on_progress:
                    on_progress(0, 0)  # indeterminate, not a misleading percentage
                sf.extractall(path=dest)
                if on_progress:
                    on_progress(len(entries), len(entries))
        except py7zr.exceptions.PasswordRequired as e:
            raise PasswordRequiredError("パスワードを入力してください。") from e
        except (py7zr.exceptions.CrcError, EOFError) as e:
            if password and archive_needs_password(archive):
                raise PasswordRequiredError("パスワードが違うか、書庫が壊れています。") from e
            raise
        except Exception as e:
            if isinstance(e, lzma.LZMAError) and password:
                raise PasswordRequiredError("パスワードが違うか、書庫が壊れています。") from e
            raise


def available_dest(dest: str | os.PathLike) -> Path:
    original = Path(dest)
    candidate = original
    index = 2
    while candidate.exists() or candidate.is_symlink():
        candidate = original.with_name(f"{original.name} ({index})")
        index += 1
    return candidate


def publish_staging(staging: Path, dest: str | os.PathLike) -> Path:
    """Windows rename refuses existing targets, including race-time collisions."""
    while True:
        target = available_dest(dest)
        try:
            staging.rename(target)
            return target
        except FileExistsError:
            continue


def clean_staging(staging: Path) -> None:
    def writable_remove(function, path, _error):
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        function(path)
    if staging.exists():
        shutil.rmtree(staging, onerror=writable_remove)


def extract_archive(archive: str | os.PathLike, dest: str | os.PathLike,
                    on_progress: ProgressCb | None = None,
                    password: bytes | None = None,
                    on_bytes: ProgressCb | None = None) -> Path:
    parent = Path(dest).absolute().parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".kantan-", dir=parent))
    try:
        _extract_into(archive, staging, on_progress, password, on_bytes=on_bytes)
        return publish_staging(staging, dest)
    finally:
        clean_staging(staging)


def default_dest_for(archive: str | os.PathLike) -> Path:
    p = Path(archive)
    name = p.name
    for suffix in sorted(SUPPORTED_SUFFIXES, key=len, reverse=True):
        if name.lower().endswith(suffix):
            name = name[:-len(suffix)]
            break
    # A name consisting only of a suffix must not select the source parent itself.
    return p.parent / (name or "解凍したファイル")
