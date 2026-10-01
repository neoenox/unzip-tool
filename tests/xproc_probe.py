"""別プロセスDnD回帰テスト用プローブ。実Appをそのまま起動する。"""
import sys
import time
from pathlib import Path
from tkinter import messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

messagebox.showinfo = lambda *a, **k: None
messagebox.showwarning = lambda *a, **k: None
messagebox.showerror = lambda *a, **k: None

from app import App

tmp = Path(sys.argv[1])
app = App()
app.withdraw()
(tmp / "hwnd.txt").write_text(str(app.winfo_id()))


def watch():
    # 生存＋イベントループ健全性の証拠
    (tmp / "heartbeat.txt").write_text(str(time.time()), encoding="utf-8")
    if app.archive_var.get():
        (tmp / "dropped.txt").write_text(app.archive_var.get(), encoding="utf-8")
    app.after(500, watch)


app.after(500, watch)
print("probe ready", flush=True)
app.mainloop()
