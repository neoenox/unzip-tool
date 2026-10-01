"""シンプルな解凍ソフト (Windows / tkinter, 標準ライブラリのみ)。"""
from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from unzipper import default_dest_for, extract_archive, is_supported, list_contents

TITLE = "かんたん解凍"
FILTERS = [
    ("対応アーカイブ", "*.zip *.tar *.tar.gz *.tgz *.tar.bz2 *.tbz *.tar.xz *.txz"),
    ("ZIP", "*.zip"),
    ("TAR系", "*.tar *.tar.gz *.tgz *.tar.bz2 *.tbz *.tar.xz *.txz"),
    ("すべて", "*.*"),
]


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(TITLE)
        self.geometry("640x480")
        self.minsize(540, 420)
        try:
            self.tk.call("tk", "windowingsystem")  # Windowsでは win32
        except tk.TclError:
            pass

        self.archive_var = tk.StringVar()
        self.dest_var = tk.StringVar()

        self._build_widgets()

    def _build_widgets(self) -> None:
        pad = {"padx": 8, "pady": 4}

        # --- アーカイブ選択 ---
        frm = ttk.LabelFrame(self, text="1. アーカイブを選択")
        frm.pack(fill="x", **pad)
        ttk.Entry(frm, textvariable=self.archive_var).pack(side="left", fill="x", expand=True, padx=(8, 4), pady=8)
        ttk.Button(frm, text="参照…", command=self.choose_archive).pack(side="left", padx=(0, 8))

        # --- 解凍先 ---
        frm2 = ttk.LabelFrame(self, text="2. 解凍先フォルダ")
        frm2.pack(fill="x", **pad)
        ttk.Entry(frm2, textvariable=self.dest_var).pack(side="left", fill="x", expand=True, padx=(8, 4), pady=8)
        ttk.Button(frm2, text="参照…", command=self.choose_dest).pack(side="left", padx=(0, 8))

        # --- 内容一覧 ---
        frm3 = ttk.LabelFrame(self, text="内容")
        frm3.pack(fill="both", expand=True, **pad)
        cols = ("size",)
        self.tree = ttk.Treeview(frm3, columns=cols, show="tree headings", height=8)
        self.tree.heading("#0", text="ファイル名")
        self.tree.heading("size", text="サイズ")
        self.tree.column("size", width=100, anchor="e")
        vsb = ttk.Scrollbar(frm3, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # --- 実行部 ---
        frm4 = ttk.Frame(self)
        frm4.pack(fill="x", **pad)
        self.extract_btn = ttk.Button(frm4, text="解凍する", command=self.start_extract)
        self.extract_btn.pack(side="right")
        self.progress = ttk.Progressbar(frm4, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.status = tk.StringVar(value="待機中")
        ttk.Label(self, textvariable=self.status).pack(fill="x", padx=8, pady=(0, 8))

        self.archive_var.trace_add("write", lambda *_: self.refresh_list())

    def choose_archive(self) -> None:
        path = filedialog.askopenfilename(title="アーカイブを選択", filetypes=FILTERS)
        if not path:
            return
        self.archive_var.set(path)
        # 解凍先が空なら既定値を入れる
        if not self.dest_var.get().strip():
            self.dest_var.set(str(default_dest_for(path)))

    def choose_dest(self) -> None:
        d = filedialog.askdirectory(title="解凍先フォルダを選択")
        if d:
            self.dest_var.set(d)

    def refresh_list(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        archive = self.archive_var.get().strip().strip('"')
        if not archive or not Path(archive).is_file():
            return
        if not is_supported(archive):
            self.status.set("未対応の形式です (.zip / .tar系のみ)")
            return
        try:
            entries = list_contents(archive)
        except Exception as e:  # noqa: BLE001 - GUI表示のため
            self.status.set(f"一覧取得に失敗: {e}")
            return
        for e in entries[:2000]:
            size = "" if e.is_dir else f"{e.size:,}"
            self.tree.insert("", "end", text=e.name, values=(size,))
        extra = len(entries) - 2000
        self.status.set(f"{len(entries)} 件" + (f" (先頭2000件のみ表示)" if extra > 0 else ""))

    def start_extract(self) -> None:
        archive = self.archive_var.get().strip().strip('"')
        dest = self.dest_var.get().strip().strip('"')
        if not archive or not Path(archive).is_file():
            messagebox.showwarning(TITLE, "アーカイブファイルを指定してください。")
            return
        if not is_supported(archive):
            messagebox.showwarning(TITLE, "未対応の形式です (.zip / .tar系のみ)。")
            return
        if not dest:
            dest = str(default_dest_for(archive))
            self.dest_var.set(dest)
        self.extract_btn.config(state="disabled")
        self.progress["value"] = 0
        self.status.set("解凍中…")
        threading.Thread(target=self._extract_worker, args=(archive, dest), daemon=True).start()

    def _extract_worker(self, archive: str, dest: str) -> None:
        try:
            def cb(done: int, total: int) -> None:
                self.after(0, lambda: self._on_progress(done, total))
            extract_archive(archive, dest, on_progress=cb)
            self.after(0, lambda: self._on_done(dest))
        except Exception as e:  # noqa: BLE001
            self.after(0, lambda: self._on_error(str(e)))

    def _on_progress(self, done: int, total: int) -> None:
        self.progress["maximum"] = max(total, 1)
        self.progress["value"] = done
        self.status.set(f"解凍中… {done}/{total}")

    def _on_done(self, dest: str) -> None:
        self.extract_btn.config(state="normal")
        self.status.set(f"完了: {dest}")
        messagebox.showinfo(TITLE, f"解凍しました。\n{dest}")

    def _on_error(self, msg: str) -> None:
        self.extract_btn.config(state="normal")
        self.status.set("エラーが発生しました")
        messagebox.showerror(TITLE, f"解凍に失敗しました。\n{msg}")


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
