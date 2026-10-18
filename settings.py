"""起動をまたいで覚えておく設定 (#24)。

保存先は `%APPDATA%\\KantanKaiko\\settings.json`。読めない・書けない場合は
既定値にフォールバックし、起動や終了を止めない。テストは環境変数
`KANTAN_SETTINGS_DIR` で実フォルダから切り離す。
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

APP_DIR_NAME = "KantanKaiko"
SETTINGS_FILENAME = "settings.json"
ENV_DIR = "KANTAN_SETTINGS_DIR"

# メインウィンドウの最小サイズ (app.py の minsize と揃える)
MIN_WIDTH = 640
MIN_HEIGHT = 560

# 「幅x高さ」＋任意の「±X±Y」。位置を省略した場合はウィンドウマネージャに任せる。
_GEOMETRY_RE = re.compile(r"^(\d{2,5})x(\d{2,5})(?:([+-]\d{1,5})([+-]\d{1,5}))?$")

# 画面内にこれだけ残っていれば「戻せる」とみなす。
MIN_VISIBLE_X = 80
MIN_VISIBLE_Y = 40


def config_dir() -> Path:
    """設定フォルダ。`KANTAN_SETTINGS_DIR` があればそれを優先する。"""
    override = os.environ.get(ENV_DIR, "").strip()
    if override:
        return Path(override)
    base = os.environ.get("APPDATA", "").strip() or os.environ.get("XDG_CONFIG_HOME", "").strip()
    if base:
        return Path(base) / APP_DIR_NAME
    return Path.home() / ".config" / APP_DIR_NAME


def settings_path() -> Path:
    return config_dir() / SETTINGS_FILENAME


def parse_geometry(text: str) -> tuple[int, int, int | None, int | None] | None:
    """`820x700+40+40` を (幅, 高さ, X, Y) に分解する。位置が無ければ X,Y は None。"""
    match = _GEOMETRY_RE.match((text or "").strip())
    if not match:
        return None
    width, height = int(match.group(1)), int(match.group(2))
    if match.group(3) is None:
        return width, height, None, None
    return width, height, int(match.group(3)), int(match.group(4))


def valid_geometry(text: str) -> bool:
    """壊れた値・小さすぎる値を読み込まない。"""
    parsed = parse_geometry(text)
    if parsed is None:
        return False
    width, height = parsed[0], parsed[1]
    return width >= MIN_WIDTH and height >= MIN_HEIGHT


def placeable_geometry(text: str, area: tuple[int, int, int, int]) -> bool:
    """保存された位置にタイトルバーが残るか。`area` は (X, Y, 幅, 高さ)。"""
    parsed = parse_geometry(text)
    if parsed is None:
        return False
    width, height, x, y = parsed
    if x is None or y is None:
        return True  # 位置未指定なら WM が画面内に置く
    area_x, area_y, area_width, area_height = area
    overlap_x = min(x + width, area_x + area_width) - max(x, area_x)
    overlap_y = min(y + height, area_y + area_height) - max(y, area_y)
    return overlap_x >= MIN_VISIBLE_X and overlap_y >= MIN_VISIBLE_Y


def virtual_screen() -> tuple[int, int, int, int] | None:
    """全モニタを囲む領域 (X, Y, 幅, 高さ)。取得できなければ None。"""
    if os.name != "nt":
        return None
    try:
        import ctypes

        metrics = ctypes.windll.user32.GetSystemMetrics
        x, y = metrics(76), metrics(77)  # SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN
        width, height = metrics(78), metrics(79)  # SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN
    except Exception:
        return None
    if width <= 0 or height <= 0:
        return None
    return x, y, width, height


@dataclass
class Settings:
    """保存する値はこの2つだけ。増やすときは `_load_field` を併せて直す。"""

    geometry: str = ""
    last_dest: str = field(default="")

    @staticmethod
    def load(path: Path | None = None) -> "Settings":
        target = Path(path) if path is not None else settings_path()
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return Settings()
        if not isinstance(raw, dict):
            return Settings()
        return Settings(
            geometry=_load_text(raw, "geometry", valid_geometry),
            last_dest=_load_text(raw, "last_dest"),
        )

    def save(self, path: Path | None = None) -> bool:
        target = Path(path) if path is not None else settings_path()
        payload = {"version": 1, "geometry": self.geometry, "last_dest": self.last_dest}
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".tmp")
            temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
            os.replace(temporary, target)
        except OSError:
            return False
        return True


def _load_text(raw: dict, key: str, validator=None) -> str:
    value = raw.get(key)
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if validator is not None and not validator(value):
        return ""
    return value
