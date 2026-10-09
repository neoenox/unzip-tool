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
    "RARの展開にはUnRARが必要です。「UnRARを取得」ボタンで自動取得するか、"
    "WinRARをインストールするか、UnRAR.exe を toolsフォルダに置くか、"
    "環境変数 KANTAN_UNRAR にパスを指定してください。"
)

# 自動取得の既定URL (自Releaseに添付したUnRAR.exe。環境変数で上書き可)。
UNRAR_RELEASE_URL = (
    "https://github.com/neoenox/unzip-tool/releases/latest/download/UnRAR.exe"
)
UNRAR_SFX_URL = "https://www.rarlab.com/rar/unrarw64.exe"


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


def user_tool_dir() -> Path:
    """実行時に自動取得したUnRAR.exeの配置先 (書き込み可能な場所)。"""
    appdata = os.environ.get("LOCALAPPDATA", "").strip().strip('"')
    if appdata:
        return Path(appdata) / "KantanKaiko" / "tools"
    return Path.home() / ".kantan-kaiko" / "tools"


def user_unrar_path() -> Path:
    return user_tool_dir() / "UnRAR.exe"


def find_unrar_tool() -> Path | None:
    """UnRAR.exe を探す。環境変数 > ユーザー取得分 > tools隣接 > WinRAR > PATH の順。"""
    cands: list[Path] = []
    env = os.environ.get("KANTAN_UNRAR", "").strip().strip('"')
    if env:
        cands.append(Path(env))
    cands.append(user_unrar_path())
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


def download_unrar(dest: str | os.PathLike | None = None,
                   url: str | None = None,
                   expected_sha256: str | None = None,
                   timeout: int = 60) -> Path:
    """UnRAR.exe をダウンロードして配置する (標準ライブラリのみ)。

    dest省略時は user_unrar_path()。Atomicに書き込み、MZヘッダと
    サイズで最低限検証する。expected_sha256指定時はハッシュも検証する。
    """
    import hashlib
    import urllib.request

    target = Path(dest) if dest else user_unrar_path()
    link = (url or os.environ.get("KANTAN_UNRAR_URL", "").strip()
            or UNRAR_RELEASE_URL)
    want = (expected_sha256 or os.environ.get("KANTAN_UNRAR_SHA256", "").strip()
            or None)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.parent / (target.name + ".download-tmp")
    try:
        request = urllib.request.Request(link, headers={"User-Agent": "KantanKaiko"})
        with urllib.request.urlopen(request, timeout=timeout) as response, \
                open(tmp, "wb") as fp:
            shutil.copyfileobj(response, fp, length=1024 * 256)
    except Exception as error:
        raise ValueError(f"UnRARをダウンロードできません: {link} ({error})")
    try:
        if tmp.stat().st_size < 100_000:
            raise ValueError(f"ダウンロードしたファイルが小さすぎます: {link}")
        with open(tmp, "rb") as fp:
            if fp.read(2) != b"MZ":
                raise ValueError(f"ダウンロードしたファイルが実行形式ではありません: {link}")
        if want:
            digest = hashlib.sha256()
            with open(tmp, "rb") as fp:
                for chunk in iter(lambda: fp.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest().lower() != want.lower():
                raise ValueError("ハッシュが一致しないため配置を中止しました。")
        os.replace(tmp, target)
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    global _rar_tool_ready
    _rar_tool_ready = False
    return target


def is_missing_unrar_error(message: str) -> bool:
    return "UnRAR" in (message or "")


def ensure_unrar_tool(auto_download: bool = False,
                      dest: str | os.PathLike | None = None) -> Path:
    """UnRAR.exe を返す。無ければ案内付きValueError。auto時は取得を試みる。"""
    tool = find_unrar_tool()
    if tool is not None:
        return tool
    if not auto_download:
        raise ValueError(RAR_TOOL_HELP)
    target = download_unrar(dest)
    if not target.is_file():
        raise ValueError(RAR_TOOL_HELP)
    return target


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


class _CountReader:
    """読み進めたバイト数を報告するラッパー (固めRARの停滞対策)。

    copyfileobjはread/readintoのどちらを使うか決め打ちできないため両方数える。
    """

    def __init__(self, raw, on_read: Callable[[int], None]):
        self._raw = raw
        self._on_read = on_read
        self._n = 0

    @property
    def n(self) -> int:
        return self._n

    def read(self, size: int = -1):
        data = self._raw.read(size)
        if data:
            self._n += len(data)
            self._on_read(self._n)
        return data

    def readinto(self, buf) -> int:
        readinto = getattr(self._raw, "readinto", None)
        if readinto is None:
            data = self._raw.read(len(buf))
            n = len(data)
            buf[:n] = data
        else:
            n = readinto(buf)
        if n:
            self._n += n
            self._on_read(self._n)
        return n

    def __getattr__(self, name: str):
        return getattr(self.__dict__["_raw"], name)


def _extract_into(archive: str | os.PathLike, dest: Path,
                  on_progress: ProgressCb | None = None, password: bytes | None = None,
                  on_file: Callable[[str], None] | None = None) -> None:
    """Write into a private staging directory; never publish from a worker.

    進捗はバイト単位 (done_bytes, total_bytes) で報告する。固めRARのように
    1ファイルの展開が長い場合でもバーが動き続ける。
    """
    kind = detect_kind(archive)
    entries = list_contents(archive, password)
    _validate_entries(dest, entries)
    total = sum(e.size for e in entries if not e.is_dir)
    def copy_members(members, open_member):
        completed = 0
        for entry, member in zip(entries, members):
            if on_file:
                on_file(entry.name)
            out = _safe_join(dest, entry.name)
            if entry.is_dir:
                out.mkdir(parents=True, exist_ok=True)
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                with open_member(member) as src, open(out, "xb") as fp:
                    if on_progress and total:
                        reader = _CountReader(src, lambda n: on_progress(completed + n, total))
                        shutil.copyfileobj(reader, fp, length=1024 * 1024)
                    else:
                        shutil.copyfileobj(src, fp, length=1024 * 1024)
                    completed += entry.size
            if on_progress:
                on_progress(completed, total)
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
                    on_progress(total, total)
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
                    password: bytes | None = None) -> Path:
    parent = Path(dest).absolute().parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".kantan-", dir=parent))
    try:
        _extract_into(archive, staging, on_progress, password)
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
