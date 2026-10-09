"""A small Windows archive extractor with a drop-first, non-modal interface."""
from __future__ import annotations

import multiprocessing
import os
import sys
import time
import webbrowser
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, ttk

from dnd import disable_drop, enable_drop, take_dropped_files
from jobs import BackgroundTask
from ui import build_widgets
from unzipper import Entry, available_dest, default_dest_for, error_message, is_supported
from unzipper import detect_kind as _detect_kind
from version import VERSION

STATE_BADGE = {
    "scanning": ("確認中", "#64748b", "#f1f5f9"),
    "ready": ("解凍できます", "#15803d", "#dcfce7"),
    "password": ("PW必要", "#b45309", "#fef3c7"),
    "extracting": ("解凍中…", "#1d4ed8", "#dbeafe"),
    "done": ("完了", "#15803d", "#dcfce7"),
    "failed": ("失敗", "#b91c1c", "#fee2e2"),
    "cancelled": ("中断", "#64748b", "#f1f5f9"),
}

FORMAT_BADGE = {
    "zip": ("ZIP", "#ffffff", "#2563eb"),
    "7z": ("7z", "#ffffff", "#7c3aed"),
    "rar": ("RAR", "#ffffff", "#ea580c"),
    "tar": ("TAR", "#ffffff", "#0d9488"),
}

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
    dest_customized: bool = False
    state: str = "scanning"
    entries: list[Entry] = field(default_factory=list)
    password: str = ""
    needs_password: bool = False
    result: str = ""
    revision: int = 0
    inspected: int = -1
    started: float = 0
    byte_done: int = 0
    byte_total: int = 0
    elapsed: int = -1
    card: object = None
    summary: object = None
    message: object = None
    progress: object = None
    open_button: object = None
    state_badge: object = None
    fmt_badge: object = None
    remove_btn: object = None
    retry_btn: object = None
    action_btn: object = None
    dest_label: object = None
    dest_row: object = None
    dest_btn: object = None
    pw_frame: object = None
    pw_var: object = None
    pw_entry: object = None
    show_pw: object = None
    details_btn: object = None
    details_wrap: object = None
    tree: object = None
    last_file: str = ""


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
        self._updating = None
        self._update_url = None
        self._pending = []
        self._password_after = None
        self._custom_parent = None
        self._extract_total = 0
        self.archive_var = tk.StringVar()
        self.dest_var = tk.StringVar()
        self.status = tk.StringVar(value="ファイルを選んで、解凍するだけ。")
        build_widgets(self)
        self.archive_var.trace_add("write", self._archive_changed)
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
        job.card.configure(cursor="hand2")
        row = ttk.Frame(job.card, style="Card.TFrame")
        row.pack(fill="x")
        try:
            fmt = _detect_kind(job.archive)
        except ValueError:
            fmt = "zip"
        fmt_text, fmt_fg, fmt_bg = FORMAT_BADGE.get(fmt, (fmt.upper(), "#ffffff", "#64748b"))
        job.fmt_badge = tk.Label(row, text=fmt_text, fg=fmt_fg, bg=fmt_bg,
                                 font=("Yu Gothic UI", 9, "bold"), padx=6, pady=2)
        job.fmt_badge.pack(side="left")
        name = job.archive.name
        short_name = name if len(name) <= 32 else name[:20] + "…" + name[-8:]
        ttk.Button(row, text=short_name, command=lambda: self.select_job(job)).pack(side="left", padx=(8, 0))
        job.remove_btn = ttk.Button(row, text="×", width=3, command=lambda: self.remove_job(job))
        job.remove_btn.pack(side="right")
        job.state_badge = tk.Label(row, text="確認中", fg="#64748b", bg="#f1f5f9",
                                   font=("Yu Gothic UI", 9, "bold"), padx=6, pady=2)
        job.state_badge.pack(side="right", padx=(0, 6))
        job.open_button = ttk.Button(job.card, text="フォルダを開く", command=lambda: self.open_result(job))
        job.summary = ttk.Label(job.card, text="内容を確認しています…", style="CardMuted.TLabel")
        job.summary.pack(anchor="w", pady=(8, 4))
        job.message = ttk.Label(job.card, text="確認中", style="Card.TLabel", wraplength=max(280, self.winfo_width() - 96))
        job.message.pack(anchor="w")
        job.dest_row = ttk.Frame(job.card, style="Card.TFrame")
        job.dest_row.pack(fill="x", pady=(4, 0))
        job.dest_label = ttk.Label(job.dest_row, text="", style="CardMuted.TLabel", font=("Yu Gothic UI", 9))
        job.dest_label.pack(side="left", fill="x", expand=True)
        job.dest_btn = ttk.Button(job.dest_row, text="変更", width=6,
                                  command=lambda: self.choose_dest_for(job))
        job.dest_btn.pack(side="left", padx=(8, 0))
        job.progress = ttk.Progressbar(job.card, mode="determinate")
        # パスワード欄 (必要な書庫のカード内にだけ表示)
        job.pw_var = tk.StringVar()
        job.pw_frame = ttk.Frame(job.card, style="Card.TFrame")
        ttk.Label(job.pw_frame, text="パスワード", style="Card.TLabel").pack(side="left", padx=(0, 10))
        job.pw_entry = ttk.Entry(job.pw_frame, textvariable=job.pw_var, show="●", width=24)
        job.pw_entry.pack(side="left", fill="x", expand=True)
        job.pw_entry.bind("<Return>", lambda _e: self.start_extract())
        job.show_pw = tk.BooleanVar()
        ttk.Checkbutton(job.pw_frame, text="表示", variable=job.show_pw,
                        command=lambda: job.pw_entry.configure(show="" if job.show_pw.get() else "●")).pack(side="left", padx=(8, 0))
        job.pw_var.trace_add("write", lambda *_a, j=job: self._on_card_password(j))
        # 内容表示 (書庫ごと)
        job.details_btn = ttk.Button(job.card, text="内容を見る",
                                     command=lambda: self.toggle_card_details(job))
        job.details_btn.pack(anchor="w", pady=(8, 0))
        job.details_wrap = ttk.Frame(job.card, style="Card.TFrame")
        job.tree = ttk.Treeview(job.details_wrap, columns=("size",), show="tree headings", height=5)
        job.tree.heading("#0", text="フォルダ / ファイル")
        job.tree.heading("size", text="サイズ")
        job.tree.column("size", width=100, anchor="e", stretch=False)
        tree_scroll = ttk.Scrollbar(job.details_wrap, command=job.tree.yview)
        job.tree.configure(yscrollcommand=tree_scroll.set)
        job.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        job.retry_btn = ttk.Button(job.card, text="再試行", command=lambda: self.retry_job(job))
        job.action_btn = ttk.Button(job.card, text="", command=lambda: self.invoke_card_action(job))
        # カードのどこをクリックしてもその書庫を選択する
        for widget in (job.card, row, job.summary, job.message, job.dest_label):
            widget.bind("<Button-1>", lambda _e, j=job: self.select_job(j))

    def _sync_card_chrome(self, job):
        """状態バッジ・再試行/削除ボタン・保存先表示を状態に合わせる。"""
        text, fg, bg = STATE_BADGE.get(job.state, ("", "#243447", "#f4f6f8"))
        try:
            job.state_badge.configure(text=text, foreground=fg, background=bg)
        except Exception:
            pass
        try:
            show_retry = job.state in ("failed", "password", "cancelled") and not self.busy
            if show_retry and not job.retry_btn.winfo_manager():
                job.retry_btn.pack(anchor="w", pady=(8, 0))
            elif not show_retry and job.retry_btn.winfo_manager():
                job.retry_btn.pack_forget()
            action = self._card_action(job) if not self.busy else None
            if action and not job.action_btn.winfo_manager():
                job.action_btn.configure(text=action[0])
                job.action_btn.pack(anchor="w", pady=(8, 0))
            elif action:
                job.action_btn.configure(text=action[0])
            elif job.action_btn.winfo_manager():
                job.action_btn.pack_forget()
            job.remove_btn.configure(state="disabled" if self.busy else "normal")
            dest_text = f"保存先: {job.result or job.dest}"
            if job.dest_customized and not job.result:
                dest_text += "（個別）"
            job.dest_label.configure(text=dest_text)
        except Exception:
            pass

    def _card_action(self, job) -> tuple | None:
        """エラー種別ごとの回復操作 (表示文言, 種別)。無ければNone。"""
        if job.state == "password":
            return ("パスワードを入力", "password")
        if job.state == "failed":
            try:
                text = job.message.cget("text")
            except Exception:
                text = ""
            if "空き容量" in text:
                return ("保存先を変更して再試行", "diskfull")
        return None

    def invoke_card_action(self, job):
        if self.busy or job not in self.jobs:
            return
        action = self._card_action(job)
        if action is None:
            return
        if action[1] == "password":
            self._sync_card_pw_row(job)
            self.select_job(job)
            try:
                if job.pw_frame.winfo_manager():
                    job.pw_entry.focus_set()
            except Exception:
                pass
        elif action[1] == "diskfull":
            if self.choose_dest_for(job):
                self.retry_job(job)

    def remove_job(self, job):
        if self.busy or job not in self.jobs:
            return
        if self._listing and self._listing[1] is job:
            try:
                self._listing[0].cancel()
            except Exception:
                pass
            self._listing = None
        job.card.destroy()
        self.jobs.remove(job)
        if self.selected is job:
            self.selected = None
            if self.jobs:
                self.select_job(self.jobs[0])
            else:
                self._syncing = True
                self.archive_var.set("")
                self.dest_var.set("")
                self._syncing = False
        if not self.jobs:
            self._empty_layout()
        else:
            self._update_buttons()

    def retry_job(self, job):
        if self.busy or job not in self.jobs:
            return
        if job.needs_password and not job.password:
            job.state = "password"
            job.message.configure(text="パスワードを入力して再試行してください。")
            self._sync_card_pw_row(job)
            self._sync_card_chrome(job)
            self.select_job(job)
            try:
                if job.pw_frame.winfo_manager():
                    job.pw_entry.focus_set()
            except Exception:
                pass
            return
        if self._listing:
            try:
                self._listing[0].cancel()
            except Exception:
                pass
            self._listing = None
        self._pending = [job]
        self._extract_total = 1
        self.busy = True
        self._update_buttons()
        self._start_next()

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
            self.selected.dest_customized = True
            self._sync_card_chrome(self.selected)

    def _on_card_password(self, job):
        if self.busy or job.state == "done":
            return
        job.password = job.pw_var.get()
        job.revision += 1
        if self._password_after:
            self.after_cancel(self._password_after)
        self._password_after = self.after(350, self._request_inspection)

    def _sync_card_pw_row(self, job):
        if job.needs_password and job.state != "done":
            if not job.pw_frame.winfo_manager():
                job.pw_frame.pack(fill="x", pady=(8, 0))
        elif job.pw_frame.winfo_manager():
            job.pw_frame.pack_forget()

    def toggle_card_details(self, job):
        if job.details_wrap.winfo_manager():
            job.details_wrap.pack_forget()
            job.details_btn.configure(text="内容を見る")
        else:
            self._render_card_tree(job)
            job.details_wrap.pack(fill="both", expand=True, pady=(4, 0))
            job.details_btn.configure(text="内容を閉じる")

    def _render_card_tree(self, job):
        job.tree.delete(*job.tree.get_children())
        nodes = {}
        for entry in job.entries[:2000]:
            parts = entry.name.replace("\\", "/").split("/")
            parts = [p for p in parts if p and p != "."]
            parent = ""
            for index, part in enumerate(parts):
                key = "/".join(parts[:index + 1])
                if key not in nodes:
                    is_file = index == len(parts) - 1 and not entry.is_dir
                    nodes[key] = job.tree.insert(parent, "end", text=part, open=True,
                        values=(readable_size(entry.size) if is_file else "",))
                parent = nodes[key]

    def _request_inspection(self):
        self._password_after = None
        # The polling loop selects the most recent revision; no result can
        # mutate a different job or a newer password attempt.

    def choose_archive(self):
        paths = filedialog.askopenfilenames(title="解凍するファイルを選ぶ", filetypes=FILTERS)
        if paths:
            self.on_drop_files(list(paths))

    def choose_dest_for(self, job) -> bool:
        """カード単位の保存先変更。個別設定として記録し、一括変更では上書きしない。"""
        if self.busy or job not in self.jobs:
            return False
        folder = filedialog.askdirectory(title="この書庫の保存先フォルダを選ぶ")
        if folder:
            job.dest = Path(folder) / default_dest_for(job.archive).name
            job.dest_customized = True
            self._sync_card_chrome(job)
            if self.selected is job:
                self.select_job(job)
            return True
        return False

    def choose_dest(self):
        folder = filedialog.askdirectory(title="保存先の親フォルダを選ぶ")
        if folder:
            self._custom_parent = Path(folder)
            for job in self.jobs:
                if job.state != "done" and not job.dest_customized:
                    job.dest = self._custom_parent / default_dest_for(job.archive).name
                self._sync_card_chrome(job)
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
                    if job.state != "done" and not job.dest_customized:
                        job.dest = path / default_dest_for(job.archive).name
                    self._sync_card_chrome(job)
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
        self._syncing = False
        for item in self.jobs:
            item.card.configure(relief="solid" if item is job else "flat", borderwidth=1)

    def _update_buttons(self):
        candidates = any(j.state in ("ready", "password", "failed", "cancelled") for j in self.jobs)
        self.extract_btn.configure(state="normal" if candidates and not self.busy else "disabled",
                                   text="まとめて解凍する" if len(self.jobs) > 1 else "解凍する")
        self.cancel_btn.configure(state="normal" if self.busy else "disabled")
        for widget in (self.choose_btn, self.dest_btn, self.dest_entry, self.clear_btn):
            widget.configure(state="disabled" if self.busy else "normal")
        for job in self.jobs:
            self._sync_card_chrome(job)
        self._sync_overall()
        self._sync_steps()

    def _sync_steps(self):
        """手順表示 (①追加→②確認→③解凍) の現在位置を常設ハイライトする。"""
        if not self.jobs:
            active = 0
        elif any(j.state == "scanning" for j in self.jobs) or self._listing:
            active = 1
        else:
            active = 2
        try:
            for i, lbl in enumerate(self.step_labels):
                lbl.configure(foreground="#1d4ed8" if i == active else "#94a3b8")
        except Exception:
            pass

    def _sync_overall(self):
        """フッターの全体バー (○/○件)。解凍中だけ表示する。"""
        try:
            if self.busy and self._extract_total:
                done = sum(1 for j in self.jobs if j.state == "done")
                if not self.overall_frame.winfo_manager():
                    self.overall_frame.pack(side="left")
                self.overall_bar.configure(maximum=self._extract_total, value=done)
                self.overall_label.configure(text=f"全体 {done}/{self._extract_total}")
            elif self.overall_frame.winfo_manager():
                self.overall_frame.pack_forget()
        except Exception:
            pass

    def _notify_done(self, done: int) -> None:
        if done <= 0:
            return
        try:
            self.bell()
        except Exception:
            pass
        if os.name != "nt":
            return
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            hwnd = wintypes.HWND(self.winfo_id())

            class FLASHWINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint),
                            ("hwnd", wintypes.HWND),
                            ("dwFlags", ctypes.c_uint),
                            ("uCount", ctypes.c_uint),
                            ("dwTimeout", ctypes.c_uint)]

            info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 3, 3, 0)
            user32.FlashWindowEx(ctypes.byref(info))
        except Exception:
            pass

    def start_extract(self):
        if self.busy:
            return
        self._pending = [j for j in self.jobs if j.state in ("ready", "password", "failed", "cancelled")]
        if not self._pending:
            self.status.set("ファイルを追加し、内容の確認が終わるまでお待ちください。")
            return
        self._extract_total = len(self._pending)
        if self._listing:
            self._listing[0].cancel()
            self._listing = None
        self.busy = True
        self._update_buttons()
        self._start_next()

    def _extract_progress_text(self, job) -> str:
        total = job.byte_total or 0
        if total:
            pct = min(100, job.byte_done * 100 // total)
            base = (f"解凍中 ({readable_size(job.byte_done)}/{readable_size(total)} {pct}%)")
        else:
            base = "解凍中…"
        if job.last_file:
            base += f": {job.last_file}"
        if job.started:
            sec = time.monotonic() - job.started
            if sec >= 3 and job.byte_done > 0:
                speed = job.byte_done / sec
                if speed > 0:
                    if total and total > job.byte_done:
                        eta = int((total - job.byte_done) / speed)
                        eta_text = f"残り約{eta // 60}分" if eta >= 60 else f"残り約{eta}秒"
                        base += f" {readable_size(speed)}/s {eta_text}"
                    else:
                        base += f" {readable_size(speed)}/s"
            elif int(sec) >= 2:
                base += f" [{int(sec)}秒]"
        return base

    def _start_next(self):
        while self._pending:
            job = self._pending.pop(0)
            if job.needs_password and not job.password:
                job.state = "password"
                job.message.configure(text="パスワードを入力して再試行してください。")
                self._sync_card_pw_row(job)
                self._sync_card_chrome(job)
                continue
            try:
                task = BackgroundTask("extract", job.archive,
                                      job.password.encode("utf-8") if job.password else None, job.dest)
            except Exception as error:
                job.state = "failed"
                job.message.configure(text=f"解凍できません: {error_message(error)}")
                self._sync_card_chrome(job)
                continue
            self._extracting = task, job
            job.state = "extracting"
            job.started = time.monotonic()
            job.byte_done = job.byte_total = 0
            job.elapsed = -1
            job.last_file = ""
            self._sync_card_chrome(job)
            job.message.configure(text=self._extract_progress_text(job))
            job.progress.configure(mode="indeterminate")
            job.progress.pack(fill="x", pady=(8, 0))
            job.progress.start(15)
            self.select_job(job)
            current = self._extract_total - len(self._pending)
            self.status.set(f"解凍中 ({current}/{self._extract_total}): {job.archive.name}")
            return
        self.busy = False
        self._extracting = None
        self._update_buttons()
        done = sum(j.state == "done" for j in self.jobs)
        remaining = len(self.jobs) - done
        self.status.set(f"完了: {done} 件" + (f" / 未完了 {remaining} 件。書庫のメッセージを確認してください。" if remaining else "。フォルダを開いて確認できます。"))
        self._notify_done(done)
        password_job = next((j for j in self.jobs if j.state == "password"), None)
        if password_job:
            self.select_job(password_job)
            self.status.set(f"パスワードを入力して再試行してください。完了: {done} 件 / 未完了: {remaining} 件")
            self._sync_card_pw_row(password_job)
            try:
                if password_job.pw_frame.winfo_manager():
                    password_job.pw_entry.focus_set()
            except Exception:
                pass

    def cancel_extract(self):
        if self._extracting:
            task, job = self._extracting
            task.cancel()
            job.progress.stop()
            job.progress.pack_forget()
            job.state = "cancelled"
            job.summary.configure(text="中止しました")
            job.message.configure(text="キャンセルしました。再試行できます。")
        self._extracting = None
        self._pending = []
        self.busy = False
        self.status.set("キャンセルしました。途中のファイルは保存していません。")
        self._update_buttons()

    def _poll_events(self):
        if self._closed:
            return
        self._poll_update()
        for paths in take_dropped_files(self):
            self.on_drop_files(paths)
        if self._extracting:
            task, job = self._extracting
            for kind, payload in task.poll():
                if kind == "file":
                    job.last_file = payload
                    job.message.configure(text=self._extract_progress_text(job))
                elif kind == "progress":
                    done, total = payload
                    if total and not job.byte_total:
                        job.progress.stop()
                        job.progress.configure(mode="determinate", maximum=total, value=done)
                    if job.last_file:
                        job.message.configure(text=self._extract_progress_text(job))
                elif kind == "bytes":
                    job.byte_done, job.byte_total = payload
                    if job.byte_total:
                        job.progress.stop()
                        job.progress.configure(mode="determinate", maximum=job.byte_total, value=job.byte_done)
                    job.elapsed = -1
                    if job.last_file:
                        job.message.configure(text=self._extract_progress_text(job))
                else:
                    job.progress.stop()
                    job.progress.pack_forget()
                    job.inspected = job.revision
                    if kind == "done":
                        job.state = "done"
                        job.summary.configure(text=f"解凍完了 · 経過 {int(time.monotonic() - job.started)} 秒")
                        job.result = payload
                        job.message.configure(text=f"完了: {payload}")
                        job.open_button.pack(anchor="w", pady=(8, 0))
                        job.password = ""
                        job.pw_var.set("")
                        self._sync_card_pw_row(job)
                    else:
                        job.state = "password" if kind == "password" else "failed"
                        job.summary.configure(text="パスワードが必要です" if kind == "password" else "解凍できません")
                        job.needs_password = kind == "password" or job.needs_password
                        job.message.configure(text=f"{'入力して再試行してください' if kind == 'password' else '解凍に失敗しました'}: {payload}")
                    self._sync_card_chrome(job)
                    self._sync_overall()
                    self.select_job(job)
                    self._extracting = None
                    self._start_next()
                    break
            if self._extracting and self._extracting[1] is job:
                elapsed = int(time.monotonic() - job.started)
                if elapsed != job.elapsed:
                    job.elapsed = elapsed
                    percent = min(99, int(job.byte_done * 100 / job.byte_total)) if job.byte_total else 0
                    size = f"{readable_size(job.byte_done)} / {readable_size(job.byte_total)} ({percent}%) · " if job.byte_total else "処理中 · "
                    job.summary.configure(text=f"{size}経過 {elapsed} 秒")
        if not self.busy:
            self._poll_listing()
        self._poll_id = self.after(50, self._poll_events)

    def check_updates(self):
        if self._updating:
            return
        if self._update_url:
            webbrowser.open(self._update_url)
            return
        try:
            self._updating = BackgroundTask('update', '')
            self.update_btn.configure(text='確認中…', state='disabled')
        except Exception:
            self.update_text.set('更新を確認できませんでした。もう一度お試しください。')

    def _poll_update(self):
        if not self._updating:
            return
        for kind, payload in self._updating.poll():
            if kind not in ('done', 'error'):
                continue
            self._updating = None
            self.update_btn.configure(text='更新を確認', state='normal')
            if kind == 'done':
                if payload['newer']:
                    self._update_url = payload['url']
                    self.update_btn.configure(text='新版を開く')
                    self.update_text.set(f"新版 v{payload['version']} があります")
                else:
                    self.update_text.set(f"最新公開版 v{payload['version']} · このアプリ v{VERSION}")
            else:
                self.update_text.set('更新を確認できません。接続を確認して再試行してください。')
            break

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
                    self._sync_card_pw_row(job)
                    if job.details_wrap.winfo_manager():
                        self._render_card_tree(job)
                    if self.selected is job:
                        self.status.set(f"{len(job.entries)} 件" + (" / パスワードを入力してください。" if job.needs_password else " / 解凍できます。"))
                else:
                    job.state = "password" if kind == "password" else "failed"
                    job.summary.configure(text="パスワードが必要です" if kind == "password" else "内容を確認できません")
                    job.needs_password = kind == "password" or job.needs_password
                    job.message.configure(text=payload)
                    self._sync_card_pw_row(job)
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
                    job.summary.configure(text="内容を確認できません")
                    job.message.configure(text=error_message(error))
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
        self.dest_var.set("")
        self._syncing = False
        self.drop_title.configure(text="ここにファイルをドロップ")
        self.status.set("ファイルを選んで、解凍するだけ。")
        self._empty_layout()

    def _on_close(self):
        self._closed = True
        if self._poll_id:
            self.after_cancel(self._poll_id)
        if self._password_after:
            self.after_cancel(self._password_after)
        for running in (self._listing, self._extracting):
            if running:
                try:
                    running[0].cancel()
                except Exception:
                    pass  # closing the window must not depend on worker cleanup
        if self._updating:
            self._updating.cancel()
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
