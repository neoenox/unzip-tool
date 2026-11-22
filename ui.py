"""Tk layout and visual design; all behavior is supplied by the application."""
import tkinter as tk
from tkinter import ttk
from version import VERSION


# --- Design tokens -------------------------------------------------------
# One palette for the whole app. Test-asserted colours are kept verbatim.
BG = "#f4f6f8"
SURFACE = "#ffffff"
INK = "#1e293b"
MUTED = "#526276"
SUBTLE = "#64748b"
BORDER = "#dce4ef"
PRIMARY = "#2563eb"
PRIMARY_DARK = "#1d4ed8"
SOFT_BLUE = "#eaf1ff"
SUCCESS = "#15803d"
WARNING = "#b45309"
DANGER = "#b91c1c"
FONT = "Yu Gothic UI"


def font(size=10, weight="normal"):
    return (FONT, size, weight)


def _configure_styles(view):
    style = ttk.Style(view)
    style.theme_use("clam")
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=INK, font=font())
    style.configure("Title.TLabel", font=font(20, "bold"), foreground=INK)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Field.TLabel", font=font(10, "bold"), foreground=INK)
    style.configure("Status.TLabel", font=font(10), foreground=MUTED)
    style.configure("TButton", font=font(), padding=(10, 6), foreground=INK)
    style.configure("Primary.TButton", background=PRIMARY, foreground="white",
                    font=font(11, "bold"), padding=(16, 9), borderwidth=0)
    style.map("Primary.TButton",
              background=[("disabled", "#d5dce5"), ("active", PRIMARY_DARK)],
              foreground=[("disabled", MUTED), ("active", "white")])
    style.configure("Quiet.TButton", background=SURFACE, foreground=INK,
                    font=font(), padding=(9, 5), borderwidth=1, bordercolor=BORDER)
    style.map("Quiet.TButton",
              background=[("disabled", "#e9edf3"), ("active", SOFT_BLUE)],
              foreground=[("disabled", "#9aa6b5")])
    # Card body is a plain white surface; state is shown by its border and accent.
    style.configure("CardInner.TFrame", background=SURFACE)
    style.configure("CardMuted.TLabel", background=SURFACE, foreground=SUBTLE, font=font(9))
    style.configure("Card.TLabel", background=SURFACE, foreground=INK, font=font(10))
    style.configure("TEntry", padding=7, font=font(), fieldbackground=SURFACE)
    style.configure("Card.Horizontal.TProgressbar", troughcolor="#e8eef7",
                    background=PRIMARY, borderwidth=0, thickness=7)
    style.configure("Overall.Horizontal.TProgressbar", troughcolor="#e2e9f4",
                    background=PRIMARY, borderwidth=0, thickness=9)
    style.configure("Treeview", rowheight=26, font=font(), background=SURFACE,
                    fieldbackground=SURFACE)
    style.configure("Treeview.Heading", font=font(9, "bold"), background="#eef3fa")
    style.map("Treeview", background=[("selected", SOFT_BLUE)])


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
            tk.Label(tip, text=text, bg="#1e293b", fg="white",
                     font=font(9), padx=9, pady=5).pack()
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


def _brand_icon(parent):
    canvas = tk.Canvas(parent, width=36, height=36, bg=PRIMARY,
                       highlightthickness=0, bd=0)
    canvas.create_rectangle(8, 11, 28, 27, fill="white", outline="white")
    canvas.create_polygon(8, 11, 13, 6, 23, 6, 28, 11, fill="white", outline="white")
    canvas.create_rectangle(15, 17, 21, 22, fill=PRIMARY, outline="")
    return canvas


def draw_drop_icon(view, active: bool) -> None:
    """Draw the drop-zone illustration with drag-state colours."""
    canvas = getattr(view, "drop_icon", None)
    if canvas is None:
        return
    accent = DROP_ACTIVE_BORDER if active else PRIMARY
    soft = "#dbeafe" if active else "#eaf1ff"
    try:
        canvas.configure(bg=soft)
        canvas.delete("all")
        canvas.create_rectangle(9, 21, 55, 49, fill="white", outline=accent, width=2)
        canvas.create_polygon(9, 21, 17, 11, 47, 11, 55, 21,
                              fill=accent, outline=accent)
        canvas.create_line(32, 26, 32, 40, fill=accent, width=3)
        canvas.create_line(26, 34, 32, 40, 38, 34, fill=accent, width=3)
    except Exception:
        pass


def build_widgets(view):
    _configure_styles(view)
    body = ttk.Frame(view, padding=(22, 16, 22, 14))
    body.pack(fill="both", expand=True)

    # Header: brand on the left, utility actions on the right.
    header = ttk.Frame(body)
    header.pack(fill="x")
    icon = _brand_icon(header)
    icon.pack(side="left")
    titles = ttk.Frame(header)
    titles.pack(side="left", padx=(12, 0))
    ttk.Label(titles, text=view.title(), style="Title.TLabel").pack(anchor="w")
    view.update_text = tk.StringVar(value=f"ZIP・7z・RAR・TAR  /  v{VERSION}")
    ttk.Label(titles, textvariable=view.update_text,
              style="Muted.TLabel", font=font(9)).pack(anchor="w", pady=(3, 0))
    header_actions = ttk.Frame(header)
    header_actions.pack(side="right")
    view.clear_btn = ttk.Button(header_actions, text="一覧をクリア",
                                style="Quiet.TButton", command=view.clear_jobs)
    view.clear_btn.pack(side="right")
    view.update_btn = ttk.Button(header_actions, text='更新を確認',
                                 style="Quiet.TButton", command=view.check_updates)
    view.update_btn.pack(side='right', padx=(0, 6))
    view.help_btn = ttk.Button(header_actions, text="ヘルプ",
                               style="Quiet.TButton", command=view.show_help)
    view.help_btn.pack(side='right', padx=(0, 6))
    Tooltip(view.help_btn, lambda: "対応形式・制限・ショートカット (F1)")

    # Three-step guide; colours are driven by App._sync_steps.
    view.steps_frame = ttk.Frame(body)
    view.steps_frame.pack(fill="x", pady=(18, 10))
    view.step_labels = []
    for i, text in enumerate(("① 書庫を追加", "② 内容を確認", "③ 解凍する")):
        if i:
            tk.Frame(view.steps_frame, bg=BORDER, width=22, height=2).pack(
                side="left", padx=(7, 7))
        lbl = tk.Label(view.steps_frame, text=text, bg=BG, fg=MUTED,
                       font=font(10, "bold"), padx=2)
        lbl.pack(side="left")
        view.step_labels.append(lbl)
    view.scan_progress = ttk.Progressbar(view.steps_frame, mode="indeterminate", length=100)
    view.scan_progress.pack(side="right")
    view.scan_progress.pack_forget()

    # Drop zone: illustration + copy + format chips + primary picker.
    view.drop_area = tk.Frame(body, bg=DROP_BG, highlightbackground=DROP_BORDER,
                              highlightthickness=2, bd=0)
    view.drop_area.pack(fill="x")
    drop_inner = tk.Frame(view.drop_area, bg=DROP_BG)
    # fill=x + expand centres the content in the large empty-state target.
    drop_inner.pack(fill="x", expand=True, padx=16, pady=12)
    view.drop_icon = tk.Canvas(drop_inner, width=64, height=52, bg=DROP_BG,
                               highlightthickness=0, bd=0)
    view.drop_icon.pack(side="left", padx=(2, 14))
    view.drop_text = tk.Frame(drop_inner, bg=DROP_BG)
    view.drop_text.pack(side="left", fill="x", expand=True)
    view.drop_title = tk.Label(view.drop_text, text="ここにファイルをドロップ",
                               bg=DROP_BG, fg=INK, font=font(14, "bold"), anchor="w")
    view.drop_title.pack(side="top", anchor="w")
    view.dnd_hint = tk.Label(view.drop_text, text="複数の書庫も、そのまま追加できます",
                             bg=DROP_BG, fg=MUTED, font=font(), anchor="w")
    view.dnd_hint.pack(side="top", anchor="w", pady=(4, 0))
    view.drop_pills = tk.Frame(view.drop_text, bg=DROP_BG)
    view.drop_pills.pack(side="top", anchor="w", pady=(9, 0))
    for text, color in (("ZIP", "#2563eb"), ("7z", "#7c3aed"),
                        ("RAR", "#c2410c"), ("TAR", "#0f766e")):
        tk.Label(view.drop_pills, text=text, bg=color, fg="white",
                 font=font(8, "bold"), padx=6, pady=1).pack(side="left", padx=(0, 5))
    view.choose_btn = ttk.Button(drop_inner, text="ファイルを選ぶ",
                                 style="Primary.TButton", command=view.choose_archive)
    view.choose_btn.pack(side="right", padx=(12, 2))
    def open_from_drop(_event):
        # The picker stays disabled while extraction is running, just like the button.
        if not getattr(view, "busy", False):
            view.choose_archive()

    for widget in (view.drop_area, drop_inner, view.drop_text,
                   view.drop_title, view.dnd_hint, view.drop_icon):
        widget.bind("<Button-1>", open_from_drop, add="+")
    draw_drop_icon(view, False)

    view.card_region = ttk.Frame(body)
    view.card_region.pack(fill="both", expand=True, pady=(14, 8))
    view.canvas = tk.Canvas(view.card_region, bg=BG, highlightthickness=0, height=1)
    scroll = ttk.Scrollbar(view.card_region, command=view.canvas.yview)
    view.canvas.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    view.canvas.pack(side="left", fill="both", expand=True)
    view.card_list = ttk.Frame(view.canvas)
    view._card_window = view.canvas.create_window(0, 0, window=view.card_list, anchor="nw")
    view.card_list.bind("<Configure>", lambda _e: view.canvas.configure(scrollregion=view.canvas.bbox("all")))
    view.canvas.bind("<Configure>", lambda e: view.canvas.itemconfigure(view._card_window, width=e.width))
    view.bind("<MouseWheel>", lambda e: view.canvas.yview_scroll(-int(e.delta / 120), "units"))

    # Destination panel.
    view.options = ttk.Frame(body)
    view.options.pack(fill="x")
    dest_row = ttk.Frame(view.options)
    dest_row.pack(fill="x")
    ttk.Label(dest_row, text="保存先", style="Field.TLabel").pack(side="left", padx=(0, 10))
    view.dest_entry = ttk.Entry(dest_row, textvariable=view.dest_var)
    view.dest_entry.pack(side="left", fill="x", expand=True)
    Tooltip(view.dest_entry, view.dest_var.get)
    view.dest_btn = ttk.Button(dest_row, text="変更", style="Quiet.TButton",
                               command=view.choose_dest)
    view.dest_btn.pack(side="left", padx=(8, 0))
    ttk.Label(view.options, text="書庫ごとのフォルダに保存。同名の場合は連番で作成します。",
              style="Muted.TLabel", font=font(9)).pack(anchor="w", pady=(6, 0))
    ttk.Label(view.options, text="「変更」は全未完了書庫に適用。欄の直接編集・カードの変更は個別のみ。",
              style="Muted.TLabel", font=font(9)).pack(anchor="w", pady=(2, 0))

    view.footer = ttk.Frame(body)
    view.footer.pack(fill="x", pady=(12, 0))
    view.cancel_btn = ttk.Button(view.footer, text="キャンセル", style="Quiet.TButton",
                                 command=view.cancel_extract, state="disabled")
    view.cancel_btn.pack(side="right", padx=(0, 8))
    view.extract_btn = ttk.Button(view.footer, text="解凍する", style="Primary.TButton",
                                  command=view.start_extract, state="disabled")
    view.extract_btn.pack(side="right")
    view.overall_frame = ttk.Frame(view.footer)
    view.overall_label = ttk.Label(view.overall_frame, text="", style="Muted.TLabel",
                                   font=font(9, "bold"))
    view.overall_label.pack(side="left", padx=(0, 8))
    view.overall_bar = ttk.Progressbar(view.overall_frame, mode="determinate",
                                       style="Overall.Horizontal.TProgressbar")
    view.overall_bar.pack(side="left", fill="x", expand=True)

    view.status_label = ttk.Label(body, textvariable=view.status,
                                  wraplength=650, style="Status.TLabel")
    view.status_label.pack(fill="x", pady=(10, 0))
    _bind_status_colour(view)
    view.bind("<Configure>", view._resize_text)


def _bind_status_colour(view):
    """Colour the status line by the icon App already puts in the text."""
    def update(*_):
        text = view.status.get()
        if text.startswith("✅"):
            colour = SUCCESS
        elif text.startswith("⚠"):
            colour = WARNING
        elif text.startswith("⏳"):
            colour = PRIMARY
        else:
            colour = MUTED
        try:
            view.status_label.configure(foreground=colour)
        except Exception:
            pass
    view.status.trace_add("write", update)
    update()


def set_drop_compact(view, compact: bool) -> None:
    """Switch between the large empty state and the compact 'add more' bar."""
    if compact:
        view.drop_area.configure(pady=5)
        view.drop_icon.pack_forget()
        view.drop_pills.pack_forget()
        view.dnd_hint.pack_forget()
        view.drop_title.pack_configure(side="left", padx=0, pady=0)
        view.choose_btn.pack_configure(side="right", padx=(12, 0), pady=0)
        view.drop_area.pack_configure(fill="x", expand=False)
    else:
        view.drop_area.configure(pady=16)
        view.drop_icon.pack(side="left", padx=(2, 14), before=view.drop_text)
        view.dnd_hint.pack(side="top", anchor="w", pady=(4, 0))
        view.drop_pills.pack(side="top", anchor="w", pady=(9, 0))
        view.drop_title.pack_configure(side="top", padx=0, pady=0)
        view.choose_btn.pack_configure(side="right", padx=(12, 2), pady=0)
        view.drop_area.pack_configure(fill="both", expand=True)


# Drop-zone colours are part of the module's public surface (QA + drag feedback).
DROP_BG = "white"
DROP_BORDER = "#64748b"
DROP_ACTIVE_BG = "#e0f3fe"
DROP_ACTIVE_BORDER = "#3b82f6"


def paint_drop_area(view, active: bool) -> None:
    """Toggle drag emphasis; visual only, never blocks a drop."""
    bg = DROP_ACTIVE_BG if active else DROP_BG
    border = DROP_ACTIVE_BORDER if active else DROP_BORDER
    try:
        view.drop_area.configure(bg=bg, highlightbackground=border)
    except Exception:
        return
    for widget in (view.drop_title, view.dnd_hint, view.drop_text):
        try:
            widget.configure(bg=bg)
        except Exception:
            pass
    draw_drop_icon(view, active)


# In-app help (#24). Keep the copy in sync with README's format/spec notes.
# tests/test_ui.py checks that every supported suffix appears here.
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
        "既存の保存先へマージしません。同名なら連番の新しいフォルダを作ります。",
        "更新の自動インストールは行いません。最新版は画面から確認して開きます。",
        "RARを開くにはUnRARが必要です（WinRAR、exeと同じ場所のtools\\UnRAR.exe、環境変数KANTAN_UNRAR）。",
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
        "↑ / ↓ — 書庫の選択を移動（選択したカードへフォーカスし、必要なら一覧をスクロール）",
        "F1 — このヘルプを開く",
        "Esc — このヘルプを閉じる",
    )),
    ("設定の記憶", (
        "前回の保存先とウィンドウ位置を %APPDATA%\\KantanKaiko\\settings.json に記録し、次回起動時に復元します。",
    )),
)


def build_help_window(view):
    """Build the single non-modal help window (#24)."""
    window = tk.Toplevel(view)
    window.title(f"ヘルプ — {view.title()}")
    window.configure(bg=BG)
    window.transient(view)
    try:
        window.withdraw()
    except Exception:
        pass
    try:
        window.iconbitmap(view.iconbitmap())
    except Exception:
        pass

    banner = tk.Frame(window, bg=PRIMARY, padx=20, pady=16)
    banner.pack(side="top", fill="x")
    tk.Label(banner, text=HELP_TITLE, bg=PRIMARY, fg="white",
             font=font(16, "bold"), anchor="w").pack(fill="x")
    tk.Label(banner, text="書庫の追加から解凍まで、このアプリの決まりごと",
             bg=PRIMARY, fg="#dbeafe", font=font(9), anchor="w").pack(fill="x", pady=(4, 0))

    footer = ttk.Frame(window, padding=(20, 10, 20, 16))
    footer.pack(side="bottom", fill="x")
    close_btn = ttk.Button(footer, text="閉じる", style="Quiet.TButton",
                           command=view.hide_help)
    close_btn.pack(anchor="e")

    holder = ttk.Frame(window)
    holder.pack(fill="both", expand=True)
    canvas = tk.Canvas(holder, bg=BG, highlightthickness=0)
    scroll = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set)
    canvas.pack(side="left", fill="both", expand=True)
    content = ttk.Frame(canvas, padding=(20, 6, 20, 0))
    _fill_help_sections(content)
    item = canvas.create_window(0, 0, window=content, anchor="nw")
    content.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item, width=e.width))
    canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-int(e.delta / 120), "units"))

    try:
        window.update_idletasks()
        content_height = content.winfo_reqheight()
        width = max(HELP_MIN_WIDTH, content.winfo_reqwidth())
        chrome = banner.winfo_reqheight() + footer.winfo_reqheight()
        top = _help_top(view)
        allowed = help_window_height(chrome + content_height, top, view.winfo_screenheight())
        if chrome + content_height > allowed:
            canvas_height = max(140, allowed - chrome)
            scroll.pack(side="right", fill="y", before=canvas)
        else:
            canvas_height = content_height
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
        if index:
            tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=(12, 2))
        heading_row = tk.Frame(parent, bg=BG)
        heading_row.pack(fill="x", pady=(8 if index == 0 else 10, 6))
        tk.Frame(heading_row, bg=PRIMARY, width=3).pack(side="left", fill="y", padx=(0, 8))
        tk.Label(heading_row, text=heading, bg=BG, fg=INK,
                 font=font(11, "bold"), anchor="w").pack(side="left")
        for line in lines:
            ttk.Label(parent, text=f"・{line}", style="Muted.TLabel",
                      wraplength=HELP_WRAP, justify="left").pack(anchor="w", pady=(0, 3))


def help_window_height(wanted: int, top: int, screen_height: int) -> int:
    """Keep the help window inside the screen (#24)."""
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
