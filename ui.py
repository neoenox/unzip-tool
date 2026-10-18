"""Tk layout and styling; all behavior is supplied by the application."""
import tkinter as tk
from tkinter import ttk
from version import VERSION


class Tooltip:
    """Hover tooltip with dynamic text (#32, #33, #35)."""

    def __init__(self, widget, textfunc, delay=500):
        self.widget = widget
        self.textfunc = textfunc
        self.delay = delay
        self._after = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._hide()
        try:
            self._after = self.widget.after(self.delay, self._show)
        except Exception:
            pass

    def _show(self):
        try:
            text = self.textfunc()
        except Exception:
            return
        if not text:
            return
        try:
            x = self.widget.winfo_rootx() + 16
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
            tip = tk.Toplevel(self.widget)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{x}+{y}")
            tk.Label(tip, text=text, bg="#1e293b", fg="#ffffff",
                     font=("Yu Gothic UI", 9), padx=8, pady=4).pack()
            self._tip = tip
        except Exception:
            pass

    def _hide(self, _event=None):
        if self._after:
            try:
                self.widget.after_cancel(self._after)
            except Exception:
                pass
            self._after = None
        if self._tip:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


def build_widgets(view):
    style = ttk.Style(view)
    style.theme_use("clam")
    style.configure("TFrame", background="#f4f6f8")
    style.configure("TLabel", background="#f4f6f8", foreground="#243447", font=("Yu Gothic UI", 10))
    style.configure("Title.TLabel", font=("Yu Gothic UI", 21, "bold"))
    style.configure("Muted.TLabel", foreground="#526276")
    style.configure("TButton", font=("Yu Gothic UI", 10), padding=(12, 8))
    style.configure("Primary.TButton", background="#1767ce", foreground="white", font=("Yu Gothic UI", 11, "bold"))
    style.map("Primary.TButton", background=[("disabled", "#d5dce5"), ("active", "#1255ab")], foreground=[("disabled", "#526276")])
    style.configure("Card.TFrame", background="white")
    style.configure("CardSel.TFrame", background="#eff6ff")
    style.configure("CardFailed.TFrame", background="#fef2f2")
    style.configure("CardPassword.TFrame", background="#fffbeb")
    style.configure("CardDone.TFrame", background="#f0fdf4")
    style.configure("Card.TLabel", background="white")
    style.configure("CardMuted.TLabel", background="white", foreground="#526276")
    style.configure("TEntry", padding=7, font=("Yu Gothic UI", 10))
    style.configure("Treeview", rowheight=28, font=("Yu Gothic UI", 10))
    style.configure("Treeview.Heading", font=("Yu Gothic UI", 10, "bold"))
    body = ttk.Frame(view, padding=24)
    body.pack(fill="both", expand=True)
    header = ttk.Frame(body)
    header.pack(fill="x")
    ttk.Label(header, text=view.title(), style="Title.TLabel").pack(side="left")
    view.clear_btn = ttk.Button(header, text="一覧をクリア", command=view.clear_jobs)
    view.clear_btn.pack(side="right")
    view.update_btn = ttk.Button(header, text='更新を確認', command=view.check_updates)
    view.update_btn.pack(side='right', padx=(0, 8))
    view.help_btn = ttk.Button(header, text="ヘルプ", command=view.show_help)
    view.help_btn.pack(side='right', padx=(0, 8))
    Tooltip(view.help_btn, lambda: "対応形式・制限・ショートカット (F1)")
    view.update_text = tk.StringVar(value=f'ZIP・7z・RAR・TAR  /  v{VERSION}')
    ttk.Label(body, textvariable=view.update_text, style='Muted.TLabel').pack(anchor='w', pady=(4, 8))
    view.steps_frame = ttk.Frame(body)
    view.steps_frame.pack(fill="x", pady=(0, 8))
    view.step_labels = []
    for i, text in enumerate(("① 書庫を追加", "② 内容を確認", "③ 解凍する")):
        lbl = tk.Label(view.steps_frame, text=text, bg="#f4f6f8", fg="#526276",
                       font=("Yu Gothic UI", 10, "bold"))
        lbl.pack(side="left")
        view.step_labels.append(lbl)
        if i < 2:
            tk.Label(view.steps_frame, text="  →  ", bg="#f4f6f8", fg="#526276",
                     font=("Yu Gothic UI", 10)).pack(side="left")
    # Scanning progress spinner (shown during listing phase)
    view.scan_progress = ttk.Progressbar(view.steps_frame, mode="indeterminate", length=120)
    view.scan_progress.pack(side="right")
    view.scan_progress.pack_forget()  # hidden by default
    view.drop_area = tk.Frame(body, bg="white", highlightbackground="#64748b", highlightthickness=1, pady=16)
    view.drop_area.pack(fill="x")
    view.drop_title = tk.Label(view.drop_area, text="ここにファイルをドロップ", bg="white", fg="#243447", font=("Yu Gothic UI", 14, "bold"))
    view.drop_title.pack(pady=(0, 6))
    view.dnd_hint = tk.Label(view.drop_area, text="複数の書庫も、そのまま追加できます", bg="white", fg="#526276", font=("Yu Gothic UI", 10))
    view.dnd_hint.pack()
    view.choose_btn = ttk.Button(view.drop_area, text="ファイルを選ぶ", command=view.choose_archive)
    view.choose_btn.pack(pady=(10, 0))
    view.card_region = ttk.Frame(body)
    view.card_region.pack(fill="both", expand=True, pady=(16, 8))
    view.canvas = tk.Canvas(view.card_region, bg="#f4f6f8", highlightthickness=0, height=1)
    scroll = ttk.Scrollbar(view.card_region, command=view.canvas.yview)
    view.canvas.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    view.canvas.pack(side="left", fill="both", expand=True)
    view.card_list = ttk.Frame(view.canvas)
    view._card_window = view.canvas.create_window(0, 0, window=view.card_list, anchor="nw")
    view.card_list.bind("<Configure>", lambda _e: view.canvas.configure(scrollregion=view.canvas.bbox("all")))
    view.canvas.bind("<Configure>", lambda e: view.canvas.itemconfigure(view._card_window, width=e.width))
    view.bind("<MouseWheel>", lambda e: view.canvas.yview_scroll(-int(e.delta / 120), "units"))
    view.options = ttk.Frame(body)
    view.options.pack(fill="x")
    dest_row = ttk.Frame(view.options)
    dest_row.pack(fill="x")
    ttk.Label(dest_row, text="保存先").pack(side="left", padx=(0, 10))
    view.dest_entry = ttk.Entry(dest_row, textvariable=view.dest_var)
    view.dest_entry.pack(side="left", fill="x", expand=True)
    Tooltip(view.dest_entry, view.dest_var.get)
    view.dest_btn = ttk.Button(dest_row, text="変更", command=view.choose_dest)
    view.dest_btn.pack(side="left", padx=(8, 0))
    ttk.Label(view.options, text="書庫ごとのフォルダに保存。同名の場合は連番で作成します。", style="Muted.TLabel").pack(anchor="w", pady=(6, 8))
    ttk.Label(view.options, text="「変更」は全未完了書庫に適用。欄の直接編集・カードの変更は個別のみ。", style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
    view.footer = ttk.Frame(body)
    view.footer.pack(fill="x", pady=(16, 0))
    view.extract_btn = ttk.Button(view.footer, text="解凍する", style="Primary.TButton", command=view.start_extract, state="disabled")
    view.extract_btn.pack(side="right")
    view.cancel_btn = ttk.Button(view.footer, text="キャンセル", command=view.cancel_extract, state="disabled")
    view.cancel_btn.pack(side="right", padx=(0, 8))
    view.overall_frame = ttk.Frame(view.footer)
    view.overall_label = ttk.Label(view.overall_frame, text="")
    view.overall_label.pack(side="left", padx=(0, 8))
    view.overall_bar = ttk.Progressbar(view.overall_frame, mode="determinate")
    view.overall_bar.pack(side="left", fill="x", expand=True)
    view.status_label = ttk.Label(body, textvariable=view.status, wraplength=650)
    view.status_label.pack(fill="x", pady=(8, 0))
    view.bind("<Configure>", view._resize_text)


# ドロップ領域の見た目 (#29)。ドラッグ中だけ強調する。
DROP_BG = "white"
DROP_BORDER = "#64748b"
DROP_ACTIVE_BG = "#e0f3fe"
DROP_ACTIVE_BORDER = "#3b82f6"


def paint_drop_area(view, active: bool) -> None:
    """ドロップ領域の強調を切り替える。失敗しても動作は継続する。"""
    bg = DROP_ACTIVE_BG if active else DROP_BG
    border = DROP_ACTIVE_BORDER if active else DROP_BORDER
    try:
        view.drop_area.configure(bg=bg, highlightbackground=border)
    except Exception:
        return
    for widget in (view.drop_title, view.dnd_hint):
        try:
            widget.configure(bg=bg)
        except Exception:
            pass


# アプリ内ヘルプ (#24)。README の「対応形式」「仕様メモ」と同じ内容を保つこと。
# 形式の一覧が実際の対応拡張子とずれていないかは tests/test_ui.py が検証する。
HELP_TITLE = "かんたん解凍の使い方"
HELP_WRAP = 460
HELP_MIN_WIDTH = 500
HELP_MAX_WIDTH = 720
HELP_MIN_HEIGHT = 320
HELP_MARGIN = 40
HELP_SECTIONS = (
    ("対応形式", (
        ".zip — パスワード対応",
        ".7z — パスワード対応",
        ".rar — RAR4/5、パスワード対応（要UnRAR）",
        ".tar / .tar.gz / .tgz / .tar.bz2 / .tbz / .tar.xz / .txz",
    )),
    ("できないこと", (
        "分割アーカイブ（.part1.rar など）と自己解凍形式（.exe）は開けません。",
        "AES暗号化ZIPは開けません（対応するのは標準のZipCryptoのみ）。",
        "RARを開くにはUnRARが必要です（WinRAR、tools\\UnRAR.exe、環境変数KANTAN_UNRAR）。",
    )),
    ("保存先の決まり", (
        "書庫ごとに「書庫名」フォルダを作って保存します。",
        "同名がある場合は「書庫名 (2)」のように連番になり、既存ファイルは上書きしません。",
        "「変更」やフォルダのドロップは全未完了書庫に効き、カードで個別に変えた書庫は上書きしません。",
    )),
    ("ショートカット", (
        "Enter — 解凍する（実行中は無効）",
        "Delete — 選択中の書庫を一覧から外す（ファイル自体は消しません）",
        "Ctrl+O — 書庫を追加",
        "↑ / ↓ — 書庫の選択を移動",
        "F1 — このヘルプを開く",
        "Esc — このヘルプを閉じる",
    )),
    ("設定の記憶", (
        "前回の保存先とウィンドウ位置を %APPDATA%\\KantanKaiko\\settings.json に記録し、次回起動時に復元します。",
    )),
)


def build_help_window(view):
    """ヘルプ窓を組み立てて返す。モーダルにせず、既存の1枚だけを使う (#24)。

    位置と大きさは mapping 前に決める（表示後に動かすと 0,0 のままになる環境がある）。
    本文は canvas の子にして、画面に収まらないときだけスクロールさせる。
    """
    window = tk.Toplevel(view)
    window.title(f"ヘルプ — {view.title()}")
    window.configure(bg="#f4f6f8")
    window.transient(view)
    try:
        window.withdraw()
    except Exception:
        pass
    try:
        window.iconbitmap(view.iconbitmap())
    except Exception:
        pass

    header = ttk.Frame(window, padding=(20, 18, 20, 6))
    header.pack(side="top", fill="x")
    ttk.Label(header, text=HELP_TITLE, style="Title.TLabel").pack(anchor="w")
    footer = ttk.Frame(window, padding=(20, 10, 20, 16))
    footer.pack(side="bottom", fill="x")
    close_btn = ttk.Button(footer, text="閉じる", command=view.hide_help)
    close_btn.pack(anchor="e")

    holder = ttk.Frame(window)
    holder.pack(fill="both", expand=True)
    canvas = tk.Canvas(holder, bg="#f4f6f8", highlightthickness=0)
    scroll = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set)
    canvas.pack(side="left", fill="both", expand=True)
    # 本文は canvas の子にしないと切り取られない（canvas が clip する）
    content = ttk.Frame(canvas, padding=(20, 6, 20, 0))
    _fill_help_sections(content)
    item = canvas.create_window(0, 0, window=content, anchor="nw")
    content.bind("<Configure>",
                 lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item, width=e.width))
    canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-int(e.delta / 120), "units"))

    try:
        window.update_idletasks()
        content_height = content.winfo_reqheight()
        width = max(HELP_MIN_WIDTH, content.winfo_reqwidth())
        chrome = header.winfo_reqheight() + footer.winfo_reqheight()
        top = _help_top(view)
        allowed = help_window_height(chrome + content_height, top, view.winfo_screenheight())
        if chrome + content_height > allowed:
            canvas_height = max(140, allowed - chrome)
            # canvas より先に詰めないと、expand する canvas が幅を全部取ってしまう
            scroll.pack(side="right", fill="y", before=canvas)
            width += scroll.winfo_reqwidth()
        else:
            canvas_height = content_height  # 収まるのでスクロールバーは出さない
            canvas.configure(yscrollcommand="")
        canvas.configure(width=width, height=canvas_height,
                         scrollregion=(0, 0, width, content_height))
        window.geometry(f"{width}x{chrome + canvas_height}+{max(0, _help_left(view, width))}+{top}")
        window.minsize(min(width, HELP_MAX_WIDTH), min(HELP_MIN_HEIGHT, chrome + canvas_height))
    except Exception:
        pass
    try:
        window.deiconify()
        close_btn.focus_set()
    except Exception:
        pass
    window.bind("<Escape>", lambda _e: view.hide_help())
    window.bind("<F1>", lambda _e: "break")
    return window


def _fill_help_sections(parent) -> None:
    for index, (heading, lines) in enumerate(HELP_SECTIONS):
        ttk.Label(parent, text=heading, font=("Yu Gothic UI", 11, "bold")).pack(
            anchor="w", pady=(16 if index == 0 else 14, 4))
        for line in lines:
            ttk.Label(parent, text=f"・{line}", style="Muted.TLabel",
                      wraplength=HELP_WRAP, justify="left").pack(anchor="w", pady=(0, 2))


def help_window_height(wanted: int, top: int, screen_height: int) -> int:
    """ヘルプ窓の高さ。小さい画面では画面内に収まる高さまで詰める (#24)。"""
    return max(HELP_MIN_HEIGHT, min(wanted, screen_height - top - HELP_MARGIN))


def _help_top(view) -> int:
    try:
        return max(0, view.winfo_rooty() + 48)
    except Exception:
        return 0


def _help_left(view, width: int) -> int:
    try:
        return view.winfo_rootx() + max(0, (view.winfo_width() - width) // 2)
    except Exception:
        return 0

