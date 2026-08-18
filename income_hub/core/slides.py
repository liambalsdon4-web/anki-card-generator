"""Generate caption slides (PNG) with Pillow — a gradient background, the channel
name, a big segment heading, and a wrapped narration excerpt. Zero paid assets.
"""
from __future__ import annotations

from pathlib import Path

# Deep gradients per slide index for visual variety.
_PALETTES = [
    ((14, 22, 40), (34, 60, 98)),
    ((30, 16, 44), (92, 40, 110)),
    ((10, 34, 34), (18, 90, 82)),
    ((40, 22, 14), (110, 60, 34)),
    ((16, 28, 44), (40, 92, 120)),
    ((28, 14, 30), (86, 40, 96)),
]


def _font(size: int):
    from PIL import ImageFont
    for name in ("seguisb.ttf", "seguisb.ttf", "arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def make_slide(index: int, heading: str, narration: str, channel: str,
               size: tuple[int, int], out_path: Path) -> Path:
    from PIL import Image, ImageDraw

    w, h = size
    top, bot = _PALETTES[index % len(_PALETTES)]
    img = Image.new("RGB", (w, h), top)
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top[0] + (bot[0] - top[0]) * t)
        g = int(top[1] + (bot[1] - top[1]) * t)
        b = int(top[2] + (bot[2] - top[2]) * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    draw = ImageDraw.Draw(img)

    # channel watermark
    small = _font(int(h * 0.03))
    draw.text((int(w * 0.05), int(h * 0.06)), channel.upper(),
              font=small, fill=(255, 255, 255))

    # big heading
    head_font = _font(int(h * 0.085))
    head_lines = _wrap(draw, heading, head_font, int(w * 0.86))
    y = int(h * 0.30)
    for line in head_lines:
        tw = draw.textlength(line, font=head_font)
        draw.text(((w - tw) / 2, y), line, font=head_font, fill=(255, 255, 255))
        y += int(h * 0.10)

    # narration excerpt
    body_font = _font(int(h * 0.042))
    body_lines = _wrap(draw, narration, body_font, int(w * 0.80))[:4]
    y = int(h * 0.62)
    for line in body_lines:
        tw = draw.textlength(line, font=body_font)
        draw.text(((w - tw) / 2, y), line, font=body_font, fill=(214, 226, 240))
        y += int(h * 0.06)

    img.save(out_path)
    return out_path
