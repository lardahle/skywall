"""Draw a SkyScene as a star chart onto a Cairo surface."""

import math

import cairo
import numpy as np

from .catalog import Constellation
from .config import Config
from .projection import PerspectiveProjection, StereographicProjection

Projection = StereographicProjection | PerspectiveProjection
from .sky import Body, SkyScene

BACKGROUND = (0.012, 0.016, 0.04)
BELOW_HORIZON_TINT = (0.03, 0.04, 0.03, 0.35)
LINE_COLOR = (0.37, 0.56, 0.84, 0.55)
LINE_WIDTH = 1.4
CONST_LABEL_COLOR = (0.56, 0.70, 1.0, 0.75)
CONST_LABEL_SIZE = 15
BODY_LABEL_SIZE = 15
HORIZON_COLOR = (0.45, 0.65, 0.45, 0.55)
COMPASS_SIZE = 14
FONT = "Sans"
SEGMENT_MARGIN = 200  # px; a segment is drawn only if an end lands within the image ± this

BODY_STYLE = {  # name: (radius px, rgb)
    "Sun": (8.0, (1.0, 0.85, 0.45)), "Moon": (10.0, (0.92, 0.92, 0.88)),
    "Mercury": (3.0, (0.80, 0.78, 0.74)), "Venus": (5.0, (1.0, 0.97, 0.86)),
    "Mars": (4.0, (1.0, 0.55, 0.38)), "Jupiter": (5.0, (1.0, 0.91, 0.70)),
    "Saturn": (4.5, (0.95, 0.85, 0.60)), "Uranus": (3.0, (0.68, 0.90, 0.92)),
    "Neptune": (3.0, (0.55, 0.65, 1.0)),
}
COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

_BV_STOPS = [(-0.3, (0.70, 0.80, 1.00)), (0.4, (1.0, 1.0, 1.0)), (0.9, (1.0, 0.92, 0.75)),
             (1.4, (1.0, 0.80, 0.55)), (2.0, (1.0, 0.68, 0.45))]


def bv_to_rgb(bv: float) -> tuple[float, float, float]:
    if not np.isfinite(bv):
        return (1.0, 1.0, 1.0)
    bv = min(max(bv, _BV_STOPS[0][0]), _BV_STOPS[-1][0])
    for (b0, c0), (b1, c1) in zip(_BV_STOPS, _BV_STOPS[1:]):
        if bv <= b1:
            t = (bv - b0) / (b1 - b0)
            return tuple(a + (b - a) * t for a, b in zip(c0, c1))
    return _BV_STOPS[-1][1]


def star_radius(mag: float) -> float:
    return max(0.5, 0.6 + (6.5 - mag) * (3.4 / 8.0))


def star_alpha(mag: float) -> float:
    return min(1.0, max(0.25, 0.35 + (6.5 - mag) / 6.0))


class _Labels:
    """Greedy label placement: a label is skipped if it overlaps one already placed."""

    def __init__(self, cr: cairo.Context):
        self.cr = cr
        self.boxes: list[tuple[float, float, float, float]] = []

    def place(self, text: str, x: float, y: float, size: float, rgba, spacing: float = 0.0,
              center: bool = False) -> bool:
        cr = self.cr
        cr.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(size)
        ext = cr.text_extents(text)
        w = ext.x_advance + spacing * max(0, len(text) - 1)
        x0 = x - w / 2 if center else x
        box = (x0 - 3, y - size - 2, x0 + w + 3, y + 4)
        if any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in self.boxes):
            return False
        self.boxes.append(box)
        cr.set_source_rgba(*rgba)
        cx = x0
        for ch in text:
            cr.move_to(cx, y)
            cr.show_text(ch)
            cx += cr.text_extents(ch).x_advance + spacing
        return True


def _on_screen(x: float, y: float, w: int, h: int, margin: float = 0.0) -> bool:
    return -margin <= x <= w + margin and -margin <= y <= h + margin


def _draw_tint(cr, proj: Projection, facing: float):
    W, H = proj.width, proj.height
    span = min(179.0, proj.hfov / 2 + 40)
    az = np.arange(facing - span, facing + span + 0.01, 0.5)
    x, y, ok = proj.project_many(az, np.zeros_like(az))
    x, y = x[ok], y[ok]
    if len(x) < 2 or x[0] > 0 or x[-1] < W:
        return  # horizon does not cross the screen left to right
    cr.move_to(x[0], y[0])
    for xi, yi in zip(x[1:], y[1:]):
        cr.line_to(xi, yi)
    bottom = max(H, float(y.max())) + 10
    cr.line_to(x[-1], bottom)
    cr.line_to(x[0], bottom)
    cr.close_path()
    cr.set_source_rgba(*BELOW_HORIZON_TINT)
    cr.fill()


def _draw_horizon(cr, proj: Projection, facing: float, labels: _Labels):
    W, H = proj.width, proj.height
    span = min(179.0, proj.hfov / 2 + 40)
    az = np.arange(facing - span, facing + span + 0.01, 0.5)
    x, y, ok = proj.project_many(az, np.zeros_like(az))
    cr.set_source_rgba(*HORIZON_COLOR)
    cr.set_line_width(1.2)
    cr.set_dash([8, 10])
    started = False
    for xi, yi, oki in zip(x, y, ok):
        if not oki:
            started = False
            continue
        if started:
            cr.line_to(xi, yi)
        else:
            cr.move_to(xi, yi)
            started = True
    cr.stroke()
    cr.set_dash([])
    for a in range(0, 360, 15):
        p = proj.project(float(a), 0.0)
        if p is None or not _on_screen(*p, W, H):
            continue
        tick = 10 if a % 45 == 0 else 5
        cr.set_source_rgba(*HORIZON_COLOR)
        cr.move_to(p[0], p[1] - tick)
        cr.line_to(p[0], p[1] + tick)
        cr.stroke()
        text = COMPASS[a // 45] if a % 45 == 0 else f"{a}°"
        size = COMPASS_SIZE if a % 45 == 0 else COMPASS_SIZE - 3
        labels.place(text, p[0], p[1] + tick + size + 4, size, HORIZON_COLOR, center=True)


def _draw_moon(cr, x: float, y: float, r: float, body: Body, sun_xy, rgb):
    cr.set_source_rgba(*rgb, 0.12)
    cr.arc(x, y, r, 0, 2 * math.pi)
    cr.fill()
    f = body.phase_fraction if body.phase_fraction is not None else 1.0
    if sun_xy is not None:
        theta = math.atan2(sun_xy[1] - y, sun_xy[0] - x)
    else:
        theta = 0.0 if body.waxing else math.pi
    cr.save()
    cr.translate(x, y)
    cr.rotate(theta)
    cr.arc(0, 0, r, -math.pi / 2, math.pi / 2)  # lit limb, sun side = +x
    k = 1 - 2 * f
    for i in range(41):
        phi = math.pi / 2 - math.pi * i / 40
        cr.line_to(k * r * math.cos(phi), r * math.sin(phi))
    cr.close_path()
    cr.set_source_rgb(*rgb)
    cr.fill()
    cr.restore()


def render_sky(scene: SkyScene, constellations: list[Constellation],
               proj: Projection, cfg: Config) -> cairo.ImageSurface:
    W, H = proj.width, proj.height
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    cr = cairo.Context(surface)
    cr.set_source_rgb(*BACKGROUND)
    cr.paint()
    labels = _Labels(cr)
    facing = proj.center_az

    _draw_tint(cr, proj, facing)

    sx, sy, sok = proj.project_many(scene.star_az, scene.star_alt)

    name_spots: list[tuple[str, float, float]] = []  # labelled after stars/bodies so those win
    if cfg.show_constellation_lines or cfg.show_constellation_names:
        cr.set_line_width(LINE_WIDTH)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        for con in constellations:
            pts = []
            for line in con.lines:
                for a, b in zip(line, line[1:]):
                    ia, ib = scene.hip_index.get(a), scene.hip_index.get(b)
                    if ia is None or ib is None or not (sok[ia] and sok[ib]):
                        continue
                    pa, pb = (sx[ia], sy[ia]), (sx[ib], sy[ib])
                    if not (_on_screen(*pa, W, H, SEGMENT_MARGIN) or _on_screen(*pb, W, H, SEGMENT_MARGIN)):
                        continue
                    pts += [p for p in (pa, pb) if _on_screen(*p, W, H)]
                    if cfg.show_constellation_lines:
                        cr.move_to(*pa)
                        cr.line_to(*pb)
            if cfg.show_constellation_lines:
                cr.set_source_rgba(*LINE_COLOR)
                cr.stroke()
            if cfg.show_constellation_names and pts:
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                name_spots.append((con.name.upper(), cx, cy))

    order = np.argsort(scene.star_mag)[::-1]  # faint first, bright on top
    for i in order:
        if not sok[i] or not _on_screen(sx[i], sy[i], W, H, 10):
            continue
        mag = float(scene.star_mag[i])
        r, g, b = bv_to_rgb(float(scene.star_bv[i]))
        rad = star_radius(mag)
        if mag < 1.5:
            glow = cairo.RadialGradient(sx[i], sy[i], 0, sx[i], sy[i], rad * 4)
            glow.add_color_stop_rgba(0, r, g, b, 0.25)
            glow.add_color_stop_rgba(1, r, g, b, 0.0)
            cr.set_source(glow)
            cr.arc(sx[i], sy[i], rad * 4, 0, 2 * math.pi)
            cr.fill()
        cr.set_source_rgba(r, g, b, star_alpha(mag))
        cr.arc(sx[i], sy[i], rad, 0, 2 * math.pi)
        cr.fill()

    sun_xy = None
    for body in scene.bodies:
        if body.name == "Sun":
            sun_xy = proj.project(body.az_deg, body.alt_deg)
    for body in scene.bodies:
        p = proj.project(body.az_deg, body.alt_deg)
        if p is None or not _on_screen(*p, W, H, 20):
            continue
        rad, rgb = BODY_STYLE.get(body.name, (3.0, (1, 1, 1)))
        if body.name == "Moon":
            _draw_moon(cr, p[0], p[1], rad, body, sun_xy, rgb)
        else:
            glow = cairo.RadialGradient(p[0], p[1], 0, p[0], p[1], rad * 3)
            glow.add_color_stop_rgba(0, *rgb, 0.35)
            glow.add_color_stop_rgba(1, *rgb, 0.0)
            cr.set_source(glow)
            cr.arc(p[0], p[1], rad * 3, 0, 2 * math.pi)
            cr.fill()
            cr.set_source_rgb(*rgb)
            cr.arc(p[0], p[1], rad, 0, 2 * math.pi)
            cr.fill()
        if cfg.show_planet_labels:
            labels.place(body.name, p[0] + rad + 6, p[1] + BODY_LABEL_SIZE / 3,
                         BODY_LABEL_SIZE, (*rgb, 0.9))

    if cfg.show_constellation_names:
        for name, cx, cy in name_spots:
            labels.place(name, cx, cy, CONST_LABEL_SIZE, CONST_LABEL_COLOR, spacing=3.0, center=True)

    if cfg.show_horizon:
        _draw_horizon(cr, proj, facing, labels)

    if cfg.show_timestamp:
        local = scene.when.astimezone()
        labels.place(f"updated {local:%H:%M}", W - 140, H - 20, 12, (0.6, 0.6, 0.7, 0.5))

    surface.flush()
    return surface
