"""手動Explorer検証用の書庫を作る（docs/manual-explorer-qa.md の「準備」3）。

使い方::

    python scripts/make_qa_archives.py
    python scripts/make_qa_archives.py --out D:\\qa\\archives

作るもの:

- `日本語 テスト 1.zip` ... 日本語名＋スペース。2階層のサブフォルダとUTF-8のテキスト
- `plain.zip`           ... ASCII名のみ。同じ構成
- `secret.zip`          ... ZipCrypto（パスワード `kantan`）。7-Zip の `7z.exe` が必要
- `test.7z`             ... py7zr で作成（ASCII名）
- `test.rar`            ... WinRAR の `Rar.exe` があれば作成（無ければ警告してスキップ）

既に同名のファイルがあれば作り直す。作成できなかったものは警告として表示し、
終了コードは0のまま返す（7-Zip や WinRAR が無い環境でも他の書庫は使えるため）。
"""
import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import py7zr  # noqa: E402

JA_TEXT = "かんたん解凍の手動検証用テキストです。\n文字化けしていないことを確認します。\n"
PLAIN_TEXT = "Plain archive for manual QA.\n"
SECRET_PASSWORD = "kantan"

SEVEN_ZIP_CANDIDATES = (
    r"C:\Program Files\7-Zip\7z.exe",
    r"C:\Program Files (x86)\7-Zip\7z.exe",
)
RAR_CANDIDATES = (
    r"C:\Program Files\WinRAR\Rar.exe",
    r"C:\Program Files (x86)\WinRAR\Rar.exe",
)


def find_tool(name, candidates):
    found = shutil.which(name)
    if found:
        return Path(found)
    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            return path
    return None


def write_tree(base, names, text):
    for name in names:
        path = base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def relative_files(source):
    return [p.relative_to(source).as_posix() for p in sorted(source.rglob("*")) if p.is_file()]


def make_zip(source, target):
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source).as_posix())


def make_secret_zip(source, target):
    seven = find_tool("7z", SEVEN_ZIP_CANDIDATES)
    if seven is None:
        return "7-Zip (7z.exe) が見つからないため secret.zip を作れませんでした"
    subprocess.run(
        [str(seven), "a", "-tzip", f"-p{SECRET_PASSWORD}", "-mem=ZipCrypto", str(target), *relative_files(source)],
        cwd=source, check=True, capture_output=True,
    )
    return None


def make_7z(source, target):
    with py7zr.SevenZipFile(target, "w") as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(source).as_posix())
    return None


def make_rar(source, target):
    rar = find_tool("rar", RAR_CANDIDATES)
    if rar is None:
        return "Rar.exe が見つからないため test.rar を作れませんでした（任意）"
    subprocess.run([str(rar), "a", "-idq", str(target), *relative_files(source)],
                   cwd=source, check=True, capture_output=True)
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="手動Explorer検証用の書庫を作る")
    parser.add_argument("--out", default=str(Path.home() / "kk-qa" / "archives"),
                        help="出力先（既定: %%USERPROFILE%%\\kk-qa\\archives）")
    args = parser.parse_args(argv)

    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    work = out / ".work"
    ja_tree = work / "ja"
    en_tree = work / "en"
    write_tree(ja_tree, ["readme.txt", "notes/メモ 1.txt", "notes/deep/さらに深い.txt"], JA_TEXT)
    write_tree(en_tree, ["readme.txt", "notes/memo.txt", "notes/deep/more.txt"], PLAIN_TEXT)

    targets = {
        "日本語 テスト 1.zip": lambda target: make_zip(ja_tree, target),
        "plain.zip": lambda target: make_zip(en_tree, target),
        "secret.zip": lambda target: make_secret_zip(en_tree, target),
        "test.7z": lambda target: make_7z(en_tree, target),
        "test.rar": lambda target: make_rar(en_tree, target),
    }

    warnings = []
    print(f"出力先: {out}")
    for name, build in targets.items():
        target = out / name
        target.unlink(missing_ok=True)
        try:
            warning = build(target)
        except subprocess.CalledProcessError as error:
            warnings.append(f"{name}: 作成に失敗しました（{error}）")
            continue
        if warning:
            warnings.append(f"{name}: {warning}")
            continue
        print(f"  {name}  {target.stat().st_size:,} bytes")

    shutil.rmtree(work, ignore_errors=True)
    for warning in warnings:
        print(f"WARNING: {warning}")
    print(f"完了: {len(list(out.glob('*.*'))) - len(warnings)} 個の書庫を作成しました"
          f"（パスワード付きは {SECRET_PASSWORD}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
