"""A small Windows archive extractor with a drop-first, non-modal interface."""
from __future__ import annotations

import multiprocessing
import os
import sys
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, ttk

from dnd import disable_drop, enable_drop, take_dropped_files
from jobs import BackgroundTask
from ui import build_widgets
from unzipper import Entry, available_dest, default_dest_for, is_supported

TITLE = "かんたん解凍"
FILTERS = [
    ("対応アーカイブ", "*.zip *.7z *.rar *.tar *.tar.gz *.tgz *.tar.bz2 *.tbz *.tar.xz *.txz"),
    ("ZIP", "*.zip"),
    ("7Z", "*.7z"),
    ("RAR", "*.rar"),
    ("TAR系", "*.tar *.tar.gz *.tgz *.tar.bz2 *.tbz *.tar.xz *.txz"),
    ("すべて", "*.*"),
]


@dataclass
class ArchiveJob:
    archive: Path
    dest: Path
    state: str = "scanning"
    entries: list[Entry] = field(default_factory=list)
    password: str = ""
    needs_password: bool = False
    result: str = ""
    revision: int = 0
    inspected: int = -1
    card: object = None
    summary: object = None
    message: object = None
    progress: object = None
    open_button: object = None


def readable_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:,.0f} {unit}" if unit == "B" else f"{value:,.1f} {unit}"
        value /= 1024


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(TITLE)
        self.geometry("760x720")
        self.minsize(600, 640)
        self.configure(bg="#f4f6f8")
        self.jobs: list[ArchiveJob] = []
        self.selected = None
        self.busy = False
        self._syncing = False
        self._closed = False
        self._listing = None
        self._extracting = None
        self._pending = []
        self._password_after = None
        self._custom_parent = None
        self.archive_var = tk.StringVar()
        self.dest_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.show_password = tk.BooleanVar()
        self.status = tk.StringVar(value="ファイルを選んで、解凍するだけ。")
        self._pw_visible = False
        build_widgets(self)
        self.archive_var.trace_add("write", self._archive_changed)
        self.password_var.trace_add("write", self._password_changed)
        self.dest_var.trace_add("write", self._dest_changed)
        self._dnd_enabled = enable_drop(self)
        if not self._dnd_enabled:
            self.dnd_hint.configure(text="「ファイルを選ぶ」から追加できます")
        self._poll_id = self.after(50, self._poll_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._empty_layout()

    def _new_card(self, job):
        job.card = ttk.Frame(self.card_list, style="Card.TFrame", padding=12)
        job.card.pack(fill="x", pady=(0, 8))
        row = ttk.Frame(job.card, style="Card.TFrame")
        row.pack(fill="x")
        name = job.archive.name
        short_name = name if len(name) <= 32 else name[:20] + "…" + name[-8:]
        ttk.Button(row, text=short_name, command=lambda: self.select_job(job)).pack(side="left")
        job.open_button = ttk.Button(job.card, text="フォルダを開く", command=lambda: self.open_result(job))
        job.summary = ttk.Label(job.card, text="内容を確認しています…", style="CardMuted.TLabel")
        job.summary.pack(anchor="w", pady=(8, 4))
        job.message = ttk.Label(job.card, text="確認中", style="Card.TLabel", wraplength=max(280, self.winfo_width() - 96))
        job.message.pack(anchor="w")
        job.progress = ttk.Progressbar(job.card, mode="determinate")

    def _resize_text(self, event):
        if event.widget is self:
            self.status_label.configure(wraplength=max(300, event.width - 48))
            for job in self.jobs:
                job.message.configure(wraplength=max(280, event.width - 96))

    def _empty_layout(self):
        self.card_region.pack_forget()
        self.drop_area.configure(pady=16)
        self.drop_title.pack_configure(side="top", padx=0, pady=(0, 6))
        self.dnd_hint.pack(before=self.choose_btn)
        self.choose_btn.pack_configure(side="top", padx=0, pady=(10, 0))
        self.drop_area.pack_configure(fill="both", expand=True)
        self.dest_var.set(str(self._custom_parent) if self._custom_parent else "元ファイルと同じ場所")
        self._update_buttons()

    def _archive_changed(self, *_):
        if not self._syncing:
            self.on_drop_files([self.archive_var.get()])

    def _dest_changed(self, *_):
        if not self._syncing and not self.busy and self.selected and self.dest_var.get().strip():
            self.selected.dest = Path(self.dest_var.get().strip().strip('"'))

    def _password_changed(self, *_):
        if self._syncing or self.busy or not self.selected:
            return
        job = self.selected
        job.password = self.password_var.get()
        job.revision += 1
        if self._password_after:
            self.after_cancel(self._password_after)
        self._password_after = self.after(350, self._request_inspection)

    def _request_inspection(self):
        self._password_after = None
        # The polling loop selects the most recent revision; no result can
        # mutate a different job or a newer password attempt.

    def choose_archive(self):
        paths = filedialog.askopenfilenames(title="解凍するファイルを選ぶ", filetypes=FILTERS)
        if paths:
            self.on_drop_files(list(paths))

    def choose_dest(self):
        folder = filedialog.askdirectory(title="保存先の親フォルダを選ぶ")
        if folder:
            self._custom_parent = Path(folder)
            for job in self.jobs:
                if job.state != "done":
                    job.dest = self._custom_parent / default_dest_for(job.archive).name
            if self.selected:
                self.select_job(self.selected)
            else:
                self.dest_var.set(folder)

    def on_drop_files(self, paths):
        if self.busy:
            self.status.set("解凍中です。追加や保存先の変更は完了後にできます。")
            return
        rejected = []
        for raw in paths:
            path = Path(raw.strip().strip('"'))
            if path.is_dir():
                self._custom_parent = path
                for job in self.jobs:
                    if job.state != "done":
                        job.dest = path / default_dest_for(job.archive).name
                continue
            if not path.is_file() or not is_supported(path):
                rejected.append(path.name or str(path))
                continue
            existing = next((j for j in self.jobs if j.archive == path), None)
            if existing:
                self.select_job(existing)
                continue
            destination = default_dest_for(path)
            if self._custom_parent:
                destination = self._custom_parent / destination.name
            job = ArchiveJob(path, destination)
            self.jobs.append(job)
            self.drop_area.configure(pady=8)
            self.dnd_hint.pack_forget()
            self.drop_title.pack_configure(side="left", padx=12, pady=0)
            self.choose_btn.pack_configure(side="right", padx=12, pady=0)
            self.drop_area.pack_configure(fill="x", expand=False)
            self.card_region.pack(fill="both", expand=True, pady=(16, 8), before=self.options)
            self._new_card(job)
            self.select_job(job)
        if self.selected:
            self.select_job(self.selected)
        self.drop_title.configure(text="ファイルを追加できます" if self.jobs else "ここにファイルをドロップ")
        if rejected:
            self.status.set("追加できません（未対応またはファイルがありません）: " + ", ".join(rejected))
        self._update_buttons()

    def select_job(self, job):
        self.selected = job
        self._syncing = True
        self.archive_var.set(str(job.archive))
        self.dest_var.set(job.result or str(available_dest(job.dest)))
        self.password_var.set(job.password)
        self.show_password.set(False)
        self.pw_entry.configure(show="●")
        self._syncing = False
        for item in self.jobs:
            item.card.configure(relief="solid" if item is job else "flat", borderwidth=1)
        self._show_password_row() if job.needs_password and job.state != "done" else self._hide_password_row()
        self._render_contents()

    def _show_password_row(self):
        if not self._pw_visible:
            self.pw_frame.pack(fill="x", pady=(4, 8))
            self._pw_visible = True

    def _hide_password_row(self):
        self.pw_frame.pack_forget()
        self._pw_visible = False

    def toggle_details(self):
        if self.details.winfo_manager():
            self.details.pack_forget()
            self.details_btn.configure(text="内容を見る")
        else:
            self.details.pack(fill="x", before=self.footer, pady=(8, 0))
            self.details_btn.configure(text="内容を閉じる")

    def _render_contents(self):
        self.tree.delete(*self.tree.get_children())
        if not self.selected:
            return
        nodes = {}
        for entry in self.selected.entries[:2000]:
            parts = entry.name.replace("\\", "/").split("/")
            parts = [p for p in parts if p and p != "."]
            parent = ""
            for index, part in enumerate(parts):
                key = "/".join(parts[:index + 1])
                if key not in nodes:
                    is_file = index == len(parts) - 1 and not entry.is_dir
                    nodes[key] = self.tree.insert(parent, "end", text=part, open=True,
                        values=(readable_size(entry.size) if is_file else "",))
                parent = nodes[key]

    def _update_buttons(self):
        candidates = any(j.state in ("ready", "password", "failed", "cancelled") for j in self.jobs)
        self.extract_btn.configure(state="normal" if candidates and not self.busy else "disabled",
                                   text="まとめて解凍する" if len(self.jobs) > 1 else "解凍する")
        self.cancel_btn.configure(state="normal" if self.busy else "disabled")
        self.details_btn.configure(state="normal" if self.jobs else "disabled")
        for widget in (self.choose_btn, self.dest_btn, self.dest_entry, self.pw_entry, self.clear_btn):
            widget.configure(state="disabled" if self.busy else "normal")

    def start_extract(self):
        if self.busy:
            return
        self._pending = [j for j in self.jobs if j.state in ("ready", "password", "failed", "cancelled")]
        if not self._pending:
            self.status.set("ファイルを追加し、内容の確認が終わるまでお待ちください。")
            return
        if self._listing:
            self._listing[0].cancel()
            self._listing = None
        self.busy = True
        self._update_buttons()
        self._start_next()

    def _start_next(self):
        while self._pending:
            job = self._pending.pop(0)
            if job.needs_password and not job.password:
                job.state = "password"
                job.message.configure(text="パスワードを入力して再試行してください。")
                continue
            try:
                task = BackgroundTask("extract", job.archive,
                                      job.password.encode("utf-8") if job.password else None, job.dest)
            except Exception as error:
                job.state = "failed"
                job.message.configure(text=f"解凍できません: {error}")
                continue
            self._extracting = task, job
            job.state = "extracting"
            job.message.configure(text="解凍中…")
            job.progress.configure(mode="indeterminate")
            job.progress.pack(fill="x", pady=(8, 0))
            job.progress.start(15)
            self.select_job(job)
            self.status.set(f"解凍中: {job.archive.name}")
            return
        self.busy = False
        self._extracting = None
        self._update_buttons()
        done = sum(j.state == "done" for j in self.jobs)
        remaining = len(self.jobs) - done
        self.status.set(f"完了: {done} 件" + (f" / 未完了 {remaining} 件。書庫のメッセージを確認してください。" if remaining else "。フォルダを開いて確認できます。"))
        password_job = next((j for j in self.jobs if j.state == "password"), None)
        if password_job:
            self.select_job(password_job)
            self.status.set(f"パスワードを入力して再試行してください。完了: {done} 件 / 未完了: {remaining} 件")
            self.pw_entry.focus_set()

    def cancel_extract(self):
        if self._extracting:
            task, job = self._extracting
            task.cancel()
            job.progress.stop()
            job.progress.pack_forget()
            job.state = "cancelled"
            job.message.configure(text="キャンセルしました。再試行できます。")
        self._extracting = None
        self._pending = []
        self.busy = False
        self.status.set("キャンセルしました。途中のファイルは保存していません。")
        self._update_buttons()

    def _poll_events(self):
        if self._closed:
            return
        for paths in take_dropped_files(self):
            self.on_drop_files(paths)
        if self._extracting:
            task, job = self._extracting
            for kind, payload in task.poll():
                if kind == "file":
                    job.message.configure(text=f"解凍中: {payload}")
                elif kind == "progress":
                    done, total = payload
                    if total:
                        job.progress.stop()
                        job.progress.configure(mode="determinate", maximum=total, value=done)
                else:
                    job.progress.stop()
                    job.progress.pack_forget()
                    job.inspected = job.revision
                    if kind == "done":
                        job.state = "done"
                        job.result = payload
                        job.message.configure(text=f"完了: {payload}")
                        job.open_button.pack(anchor="w", pady=(8, 0))
                        job.password = ""
                    else:
                        job.state = "password" if kind == "password" else "failed"
                        job.needs_password = kind == "password" or job.needs_password
                        job.message.configure(text=f"{'入力して再試行してください' if kind == 'password' else '解凍に失敗しました'}: {payload}")
                    self.select_job(job)
                    self._extracting = None
                    self._start_next()
                    break
        if not self.busy:
            self._poll_listing()
        self._poll_id = self.after(50, self._poll_events)

    def _poll_listing(self):
        if self._listing:
            task, job, revision = self._listing
            for kind, payload in task.poll():
                if kind not in ("done", "error", "password"):
                    continue
                self._listing = None
                if revision != job.revision or job.state == "done":
                    break
                job.inspected = revision
                if kind == "done":
                    job.entries, job.needs_password = payload
                    job.state = "password" if job.needs_password and not job.password else "ready"
                    size = sum(e.size for e in job.entries if not e.is_dir)
                    count = sum(not e.is_dir for e in job.entries)
                    extra = " / 内容は先頭2000件のみ表示" if len(job.entries) > 2000 else ""
                    job.summary.configure(text=f"{count:,} ファイル · 展開後 {readable_size(size)}{extra}")
                    job.message.configure(text="パスワードを入力してください。" if job.state == "password" else "解凍できます")
                    if self.selected is job:
                        self.status.set(f"{len(job.entries)} 件" + (" / パスワードを入力してください。" if job.needs_password else " / 解凍できます。"))
                else:
                    job.state = "password" if kind == "password" else "failed"
                    job.needs_password = kind == "password" or job.needs_password
                    job.message.configure(text=payload)
                    if self.selected is job:
                        self.status.set(payload)
                if self.selected is job:
                    self.select_job(job)
                self._update_buttons()
                break
        if not self._listing and not self._password_after:
            job = next((j for j in self.jobs if j.inspected != j.revision and j.state != "done"), None)
            if job:
                try:
                    task = BackgroundTask("list", job.archive, job.password.encode("utf-8") if job.password else None)
                    self._listing = task, job, job.revision
                except Exception as error:
                    job.inspected = job.revision
                    job.state = "failed"
                    job.message.configure(text=str(error))
                    self._update_buttons()

    def open_result(self, job):
        if job.result:
            try:
                os.startfile(job.result)
            except OSError as error:
                self.status.set(f"フォルダを開けません: {error}")

    def clear_jobs(self):
        if self.busy:
            return
        if self._listing:
            self._listing[0].cancel()
            self._listing = None
        if self._password_after:
            self.after_cancel(self._password_after)
            self._password_after = None
        for job in self.jobs:
            job.card.destroy()
        self.jobs.clear()
        self.selected = None
        self._syncing = True
        self.archive_var.set("")
        self.password_var.set("")
        self.dest_var.set("")
        self._syncing = False
        self._hide_password_row()
        self._render_contents()
        self.drop_title.configure(text="ここにファイルをドロップ")
        self.status.set("ファイルを選んで、解凍するだけ。")
        self.details.pack_forget()
        self.details_btn.configure(text="内容を見る")
        self._empty_layout()

    def _on_close(self):
        self._closed = True
        if self._poll_id:
            self.after_cancel(self._poll_id)
        if self._password_after:
            self.after_cancel(self._password_after)
        if self._listing:
            self._listing[0].cancel()
        if self._extracting:
            self._extracting[0].cancel()
        disable_drop(self)
        self.destroy()


def main(argv=None):
    multiprocessing.freeze_support()
    app = App()
    paths = sys.argv[1:] if argv is None else argv
    if paths:
        app.on_drop_files(paths)
    app.mainloop()


if __name__ == "__main__":
    main()
