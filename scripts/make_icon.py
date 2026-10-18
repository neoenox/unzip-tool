"""Generate assets/icon.ico (multi-size) with PIL. Reproducible: run this script."""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

BLUE = (23, 103, 206)       # app primary #1767ce
DARK = (15, 74, 158)        # interior shade
WHITE = (255, 255, 255)
SIZE = 256


def draw_icon(size: int = SIZE) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = size / 256  # unit scale
    # Background: rounded blue square.
    d.rounded_rectangle([8 * u, 8 * u, 248 * u, 248 * u], radius=56 * u, fill=BLUE)
    # Open box: dark interior, white body, open flaps.
    d.rectangle([92 * u, 150 * u, 164 * u, 176 * u], fill=DARK)  # interior
    d.polygon([(64 * u, 150 * u), (28 * u, 104 * u), (76 * u, 104 * u), (104 * u, 150 * u)], fill=WHITE)  # left flap
    d.polygon([(192 * u, 150 * u), (228 * u, 104 * u), (180 * u, 104 * u), (152 * u, 150 * u)], fill=WHITE)  # right flap
    d.rectangle([64 * u, 150 * u, 192 * u, 224 * u], fill=WHITE)  # body
    d.rectangle([122 * u, 150 * u, 134 * u, 224 * u], fill=BLUE)  # tape
    # Down arrow above the box (into the box).
    d.rectangle([114 * u, 44 * u, 142 * u, 118 * u], fill=WHITE)  # shaft
    d.polygon([(88 * u, 112 * u), (168 * u, 112 * u), (128 * u, 158 * u)], fill=WHITE)  # head
    return img


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "assets" / "icon.ico"))
    parser.add_argument("--preview", default="")
    args = parser.parse_args()
    img = draw_icon()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    if args.preview:
        img.save(args.preview)
    print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
