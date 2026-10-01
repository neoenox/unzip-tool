"""解凍ロジック。標準ライブラリのみ (zipfile / tarfile)。GUIから分離してテスト可能に。"""
from __future__ import annotations

import os
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

ArchiveKind = Literal["zip", "tar"]

SUPPORTED_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz", ".tar.xz", ".txz")


def is_supported(path: str | os.PathLike) -> bool:
    name = str(path).lower()
    return name.endswith(SUPPORTED_SUFFIXES)


def detect_kind(path: str | os.PathLike) -> ArchiveKind:
    name = str(path).lower()
    if name.endswith(".zip"):
        return "zip"
    if name.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz", ".tar.xz", ".txz")):
        return "tar"
    raise ValueError(f"未対応の形式です: {path}")


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


def list_contents(archive: str | os.PathLike) -> list[Entry]:
    kind = detect_kind(archive)
    entries: list[Entry] = []
    if kind == "zip":
        with zipfile.ZipFile(archive, "r") as zf:
            for info in zf.infolist():
                name = _decode_zip_name(info.filename)
                entries.append(
                    Entry(name=name, size=info.file_size, is_dir=info.is_dir())
                )
    else:
        with tarfile.open(archive, "r:*") as tf:
            for m in tf.getmembers():
                entries.append(Entry(name=m.name, size=m.size or 0, is_dir=m.isdir()))
    return entries


ProgressCb = Callable[[int, int], None]  # (完了件数, 全体件数)


def extract_archive(
    archive: str | os.PathLike,
    dest: str | os.PathLike,
    on_progress: ProgressCb | None = None,
    password: bytes | None = None,
) -> Path:
    """アーカイブを dest に解凍して dest の Path を返す。"""
    if not is_supported(archive):
        raise ValueError(f"未対応の形式です: {archive}")
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
                    with zf.open(info, pwd=password) as src, open(out, "wb") as fp:
                        fp.write(src.read())
                if on_progress:
                    on_progress(i, total)
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
    for suf in (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz", ".txz", ".zip", ".tar"):
        if lower.endswith(suf):
            name = name[: -len(suf)]
            break
    return p.parent / name
