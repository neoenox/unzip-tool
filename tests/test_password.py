"""パスワードUXのテスト。パスワードが必要な時だけ入力欄が出ること。

- tests/vendor/pw.zip: 自作のZipCrypto書庫 (パスワード testpw、中身 hello.txt)
- 7zは実行時に自作 (7za不要、py7zrで作成)
- rarの暗号書庫は作成手段が無いため、非暗号でのneeds_passwordのみ確認

実行: python tests/test_password.py
"""
import sys
import tempfile
from pathlib import Path

import py7zr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import test_e2e  # noqa: E402
from unzipper import PasswordRequiredError, archive_needs_password, extract_archive, list_contents  # noqa: E402

VENDOR = Path(__file__).resolve().parent / "vendor"
ZIP_PW = VENDOR / "pw.zip"
ZIP_PW_TEXT = "hello pw"


def test_zip_password_flow() -> None:
    assert [e.name for e in list_contents(ZIP_PW)] == ["hello.txt"]  # 一覧はPW不要
    assert archive_needs_password(ZIP_PW) is True
    for pwd in (None, "bad".encode()):
        for fn in (lambda d: extract_archive(ZIP_PW, d),
                   lambda d: extract_archive(ZIP_PW, d, password=pwd)):
            try:
                fn(Path(tempfile.mkdtemp()))
            except PasswordRequiredError:
                pass
            else:
                raise AssertionError(f"expected PasswordRequiredError (pwd={pwd})")
    dest = Path(tempfile.mkdtemp()) / "ok"
    extract_archive(ZIP_PW, dest, password="testpw".encode())
    assert (dest / "hello.txt").read_text() == ZIP_PW_TEXT


def test_7z_password_flow() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="pw7z-"))
    src = tmp / "src"
    src.mkdir()
    (src / "a.txt").write_text("secret data", encoding="utf-8")
    zpath = tmp / "pw.7z"
    with py7zr.SevenZipFile(zpath, "w", password="s3cret") as a:
        a.writeall(src, ".")
    assert archive_needs_password(zpath) is True
    try:
        extract_archive(zpath, tmp / "nope")
    except PasswordRequiredError:
        pass
    else:
        raise AssertionError("expected PasswordRequiredError without password")
    try:
        extract_archive(zpath, tmp / "bad", password="wrong".encode())
    except PasswordRequiredError:
        pass
    else:
        raise AssertionError("expected PasswordRequiredError with wrong password")
    dest = tmp / "ok"
    extract_archive(zpath, dest, password="s3cret".encode())
    assert (dest / "a.txt").read_text(encoding="utf-8") == "secret data"


def test_no_password_archives() -> None:
    assert archive_needs_password(VENDOR / "testfile.rar5.rar") is False


def test_gui_password_ondemand() -> None:
    from tkinter import messagebox  # noqa: E402

    from app import App  # noqa: E402

    app = App()
    app.withdraw()
    orig = test_e2e.mute_dialogs()
    # messageboxは参照渡しで差し替えるため、app側の参照も黙らせる
    messagebox.showinfo = lambda *a, **k: None
    try:
        app.archive_var.set(str(ZIP_PW))
        job = app.jobs[0]
        assert test_e2e.pump(app, lambda: job.pw_frame.winfo_manager(), timeout=10), "PW欄が出ない"
        assert "パスワード" in app.status.get(), app.status.get()
        # 正PWを入力→一覧が自動表示される (内容表示を開いて確認)
        job.details_btn.invoke()
        job.pw_var.set("testpw")
        assert test_e2e.pump(
            app, lambda: any(job.tree.item(i)["text"] == "hello.txt" for i in job.tree.get_children()),
            timeout=10,
        ), "正PWで一覧が出ない"
        # 誤PWで解凍→欄が出たまま、ダイアログ無しで促される
        job.pw_var.set("bad")
        app.dest_var.set(str(Path(tempfile.mkdtemp()) / "out"))
        app.start_extract()
        assert test_e2e.pump(app, lambda: "入力して" in app.status.get(), timeout=20), app.status.get()
        assert job.pw_frame.winfo_manager()
        # 正PWで解凍→完了
        job.pw_var.set("testpw")
        app.start_extract()
        assert test_e2e.pump(app, lambda: app.status.get().startswith("完了"), timeout=20), app.status.get()
    finally:
        test_e2e.restore_dialogs(orig)
        app._on_close()
    print("PASS test_gui_password_ondemand")


def main() -> int:
    test_zip_password_flow()
    print("PASS test_zip_password_flow")
    test_7z_password_flow()
    print("PASS test_7z_password_flow")
    test_no_password_archives()
    print("PASS test_no_password_archives")
    test_gui_password_ondemand()
    print("PASS test_gui_password_ondemand")
    print("ALL PASSWORD PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
