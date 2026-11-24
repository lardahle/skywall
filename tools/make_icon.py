"""Generate Skywall's app icon (data/icons/): a window onto the night sky in the wallpaper's own palette.

    python tools/make_icon.py

Writes skywall.ico (16–256 px, PNG-compressed entries) and skywall-256.png. Sizes up to 32 px
are drawn from a simplified design (no thin lines) so they stay legible in title bars and menus.
"""

import io
import math
import struct
from pathlib import Path

import cairo

OUT = Path(__file__).resolve().parent.parent / "data" / "icons"
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)

SKY_TOP = (0.035, 0.055, 0.15)
SKY_BOTTOM = (0.09, 0.13, 0.30)
LINE = (0.45, 0.64, 0.95, 0.85)
HORIZON = (0.50, 0.75, 0.52, 0.85)
STAR = (0.95, 0.96, 1.0)
WARM = (1.0, 0.86, 0.62)

# A five-star asterism (unit coordinates), its links, and which star is the bright one.
STARS = [(0.22, 0.30), (0.40, 0.22), (0.58, 0.36), (0.78, 0.26), (0.66, 0.56)]
LINKS = [(0, 1), (1, 2), (2, 3), (2, 4)]
BRIGHT = 2
DUST = [(0.15, 0.55, 0.9), (0.30, 0.48, 0.7), (0.86, 0.46, 0.8), (0.48, 0.60, 0.6), (0.88, 0.14, 0.7),
        (0.12, 0.14, 0.6), (0.52, 0.10, 0.6), (0.34, 0.70, 0.5), (0.74, 0.70, 0.6)]


def _rounded(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _sparkle(cr, x, y, r, rgb):
    """Four-point star with a soft glow."""
    glow = cairo.RadialGradient(x, y, 0, x, y, r * 2.2)
    glow.add_color_stop_rgba(0, *rgb, 0.55)
    glow.add_color_stop_rgba(1, *rgb, 0)
    cr.set_source(glow)
    cr.arc(x, y, r * 2.2, 0, 2 * math.pi)
    cr.fill()
    cr.set_source_rgb(*rgb)
    w = r * 0.28
    cr.move_to(x, y - r)
    for a, b in ((x + w, y - w), (x + r, y), (x + w, y + w), (x, y + r),
                 (x - w, y + w), (x - r, y), (x - w, y - w)):
        cr.line_to(a, b)
    cr.close_path()
    cr.fill()


def draw(size: int) -> cairo.ImageSurface:
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(s)
    small = size <= 32
    pad = size * (0.04 if small else 0.06)
    inner = size - 2 * pad
    ux = lambda u: pad + u * inner  # noqa: E731
    uy = lambda v: pad + v * inner  # noqa: E731

    _rounded(cr, pad, pad, inner, inner, inner * 0.22)
    sky = cairo.LinearGradient(0, pad, 0, pad + inner)
    sky.add_color_stop_rgb(0, *SKY_TOP)
    sky.add_color_stop_rgb(1, *SKY_BOTTOM)
    cr.set_source(sky)
    cr.fill_preserve()
    cr.save()
    cr.clip()

    # Below the horizon: the faint see-through-Earth tint the wallpaper uses.
    hy = uy(0.74)
    cr.set_source_rgba(0.03, 0.06, 0.04, 0.55)
    cr.rectangle(pad, hy, inner, inner)
    cr.fill()
    cr.set_source_rgba(*HORIZON)
    cr.set_line_width(max(1.0, size / 64))
    if not small:
        cr.set_dash([size / 22, size / 36])
    cr.move_to(pad, hy)
    cr.line_to(pad + inner, hy)
    cr.stroke()
    cr.set_dash([])

    if not small:
        for u, v, a in DUST:
            cr.set_source_rgba(*STAR, a * 0.8)
            cr.arc(ux(u), uy(v), max(0.6, size / 170), 0, 2 * math.pi)
            cr.fill()
        cr.set_source_rgba(*LINE)
        cr.set_line_width(max(1.0, size / 80))
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        for a, b in LINKS:
            cr.move_to(ux(STARS[a][0]), uy(STARS[a][1]))
            cr.line_to(ux(STARS[b][0]), uy(STARS[b][1]))
        cr.stroke()

    for i, (u, v) in enumerate(STARS):
        if i == BRIGHT:
            continue
        cr.set_source_rgb(*STAR)
        cr.arc(ux(u), uy(v), max(0.9, size / (42 if small else 52)), 0, 2 * math.pi)
        cr.fill()
    bx, by = STARS[BRIGHT]
    _sparkle(cr, ux(bx), uy(by), size * (0.17 if small else 0.11), WARM)
    cr.restore()

    # Window frame: a thin light edge, so the tile reads on dark taskbars and title bars.
    _rounded(cr, pad + 0.5, pad + 0.5, inner - 1, inner - 1, inner * 0.22)
    cr.set_source_rgba(0.72, 0.80, 1.0, 0.35 if small else 0.28)
    cr.set_line_width(max(1.0, size / 96))
    cr.stroke()
    s.flush()
    return s


def _png_bytes(surface: cairo.ImageSurface) -> bytes:
    buf = io.BytesIO()
    surface.write_to_png(buf)
    return buf.getvalue()


def write_ico(path: Path, sizes=SIZES) -> None:
    """ICO with PNG-compressed entries (Windows Vista and later)."""
    images = [(sz, _png_bytes(draw(sz))) for sz in sizes]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, blobs = b"", b""
    for sz, data in images:
        dim = 0 if sz >= 256 else sz
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset + len(blobs))
        blobs += data
    path.write_bytes(header + entries + blobs)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write_ico(OUT / "skywall.ico")
    draw(256).write_to_png(str(OUT / "skywall-256.png"))
    print(f"wrote {OUT / 'skywall.ico'} and skywall-256.png")


if __name__ == "__main__":
    main()
