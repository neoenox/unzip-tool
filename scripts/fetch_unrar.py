"""UnRAR.exe を自動取得する (標準ライブラリのみ)。

優先順位:
  1. raw バイナリの直接DL (--url / 環境変数 KANTAN_UNRAR_URL / 既定の自Release)
  2. 公式SFX (https://www.rarlab.com/rar/unrarw64.exe) を手元の展開手段で抜き出す
     (既存UnRAR > WinRAR > 7z系)。展開手段が無ければ exit 2 で案内を出す。

配置先の既定は tools/UnRAR.exe (リポジトリ直下)。アプリ実行時は
%LOCALAPPDATA%\\KantanKaiko\\tools への配置を unzipper.download_unrar() が担う。
こちらは主に build.bat / CI のビルド時取得用。

使用例:
  python scripts/fetch_unrar.py
  python scripts/fetch_unrar.py --url https://example/UnRAR.exe --sha256 <hex>
  KANTAN_UNRAR_URL=... KANTAN_UNRAR_SHA256=... python scripts/fetch_unrar.py
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OFFICIAL_SFX_URL = "https://www.rarlab.com/rar/unrarw64.exe"
DEFAULT_RAW_URL = (
    "https://github.com/neoenox/unzip-tool/releases/latest/download/UnRAR.exe"
)
MIN_EXE_SIZE = 100_000


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def looks_like_exe(path: Path) -> bool:
    try:
        if path.stat().st_size < MIN_EXE_SIZE:
            return False
        with open(path, "rb") as fp:
            return fp.read(2) == b"MZ"
    except OSError:
        return False


def download(url: str, dest_tmp: Path, timeout: int = 60) -> None:
    dest_tmp.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "KantanKaiko-fetch"})
    with urllib.request.urlopen(request, timeout=timeout) as response, open(dest_tmp, "wb") as fp:
        shutil.copyfileobj(response, fp, length=1024 * 256)


def fetch_raw(url: str, dest: Path, expected_sha256: str | None, timeout: int = 60) -> Path:
    tmp = dest.parent / (dest.name + ".download-tmp")
    if tmp.exists():
        tmp.unlink()
    try:
        download(url, tmp, timeout=timeout)
    except Exception as error:
        raise ValueError(f"UnRARをダウンロードできません: {url} ({error})")
    if not looks_like_exe(tmp):
        tmp.unlink(missing_ok=True)
        raise ValueError(f"ダウンロードしたファイルがUnRAR.exeらしくありません: {url}")
    if expected_sha256:
        actual = sha256_of(tmp)
        if actual.lower() != expected_sha256.lower():
            tmp.unlink(missing_ok=True)
            raise ValueError(
                "ハッシュが一致しません。"
                f"期待={expected_sha256} 実際={actual}"
            )
    os.replace(tmp, dest)
    return dest


def _extractor_candidates() -> list[list[str]]:
    """利用可能な展開コマンドの候補 (SFX抜き出し用)。"""
    cands: list[list[str]] = []
    try:
        from unzipper import find_unrar_tool  # rarfile不要・遅延importのみ

        found = find_unrar_tool()
        if found:
            cands.append([str(found)])
    except Exception:
        pass
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pfx = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    for base in (pf, pfx):
        winrar = Path(base) / "WinRAR" / "UnRAR.exe"
        if winrar.is_file():
            cands.append([str(winrar)])
    for name in ("7z", "7za", "7zr"):
        found = shutil.which(name)
        if found:
            cands.append([found])
    return cands


def extract_sfx(sfx: Path, dest: Path) -> Path:
    out_dir = Path(tempfile.mkdtemp(prefix="unrar-sfx-"))
    try:
        errors: list[str] = []
        for cmd in _extractor_candidates():
            try:
                if Path(cmd[0]).name.lower().startswith("7z"):
                    subprocess.run(
                        [*cmd, "x", f"-o{out_dir}", str(sfx), "UnRAR.exe", "license.txt"],
                        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        timeout=120,
                    )
                else:
                    subprocess.run(
                        [*cmd, "x", "-o+", str(sfx), "UnRAR.exe"],
                        cwd=out_dir, check=True,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        timeout=120,
                    )
                got = out_dir / "UnRAR.exe"
                if looks_like_exe(got):
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    tmp = dest.parent / (dest.name + ".download-tmp")
                    shutil.copyfile(got, tmp)
                    os.replace(tmp, dest)
                    return dest
                errors.append(f"{cmd[0]}: 展開後の検証に失敗")
            except Exception as error:
                errors.append(f"{cmd[0]}: {error}")
        detail = "; ".join(errors) if errors else "利用可能な展開手段がありません"
        raise ValueError(
            "公式SFXからUnRAR.exeを抜き出せませんでした。"
            f"({detail}) 7-ZipかWinRARを入れるか、--url で直接取得してください。"
        )
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch UnRAR.exe")
    parser.add_argument("--dest", default=str(ROOT / "tools" / "UnRAR.exe"))
    parser.add_argument("--url", default=os.environ.get("KANTAN_UNRAR_URL", ""))
    parser.add_argument("--sha256", default=os.environ.get("KANTAN_UNRAR_SHA256", ""))
    parser.add_argument("--sfx-url", default=OFFICIAL_SFX_URL)
    parser.add_argument("--no-sfx-fallback", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--timeout", type=int, default=60)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dest = Path(args.dest)
    if dest.is_file() and not args.force:
        print(f"OK (already present): {dest}")
        return 0
    raw_url = args.url.strip() or DEFAULT_RAW_URL
    expected = args.sha256.strip() or None
    try:
        fetch_raw(raw_url, dest, expected, timeout=args.timeout)
        print(f"OK (downloaded): {dest}")
        if expected:
            print(f"SHA256: {sha256_of(dest)}")
        return 0
    except ValueError as error:
        print(f"raw取得に失敗: {error}")
        if args.no_sfx_fallback:
            return 1
        # 既定URLが未整備 (初回Release前など) でもSFXへ進む
    print(f"公式SFXから取得を試みます: {args.sfx_url}")
    tmp_sfx = Path(tempfile.gettempdir()) / "unrarw64.exe"
    try:
        download(args.sfx_url, tmp_sfx, timeout=args.timeout)
    except Exception as error:
        print(f"SFXのダウンロードに失敗: {error}")
        return 1
    try:
        extract_sfx(tmp_sfx, dest)
    except ValueError as error:
        print(str(error))
        return 2
    finally:
        try:
            tmp_sfx.unlink()
        except OSError:
            pass
    print(f"OK (extracted from SFX): {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
