from datetime import datetime, timezone

import numpy as np
import pytest

from skywall.catalog import Constellation
from skywall.config import Config
from skywall.projection import StereographicProjection
from skywall.render import BACKGROUND, render_sky
from skywall.sky import SkyScene


def P():
    return StereographicProjection(296.0, 0.0, 60.0, 3440, 1440)


def scene(star_az=(), star_alt=(), star_mag=(), star_bv=(), hips=None, bodies=()):
    hips = list(hips) if hips is not None else list(range(1, len(star_az) + 1))
    return SkyScene(when=datetime(2026, 11, 22, tzinfo=timezone.utc),
                    star_az=np.array(star_az, float), star_alt=np.array(star_alt, float),
                    star_mag=np.array(star_mag, float), star_bv=np.array(star_bv, float),
                    hip_index={h: i for i, h in enumerate(hips)}, bodies=list(bodies))


def px(surface, x, y):
    surface.flush()
    buf = surface.get_data()
    o = y * surface.get_stride() + x * 4
    b, g, r = buf[o], buf[o + 1], buf[o + 2]
    return (r / 255, g / 255, b / 255)


def window_sum(surface, x, y, r=1):
    return sum(sum(px(surface, x + dx, y + dy)) for dx in range(-r, r + 1) for dy in range(-r, r + 1))


def test_empty_scene_is_background_above_horizon():
    s = render_sky(scene(), [], P(), Config(show_horizon=False))
    assert px(s, 1720, 100) == pytest.approx(BACKGROUND, abs=0.01)


def test_bright_star_drawn_at_projected_position():
    s = render_sky(scene([296.0], [10.0], [0.0], [0.0]), [], P(), Config())
    x, y = P().project(296.0, 10.0)
    assert sum(px(s, round(x), round(y))) > 1.5


def test_below_horizon_is_tinted():
    s = render_sky(scene(), [], P(), Config(show_horizon=False))
    assert px(s, 1720, 1400) != pytest.approx(px(s, 1720, 100), abs=0.005)


def test_segment_to_star_behind_viewer_not_drawn():  # Review Focus 3
    sc = scene([296.0, 116.0], [0.0, 0.0], [7.0, 7.0], [0, 0], hips=[1, 2])
    cfg = Config(show_constellation_names=False, show_horizon=False)
    with_line = render_sky(sc, [Constellation("Tst", "Test", [[1, 2]])], P(), cfg)
    without = render_sky(sc, [], P(), cfg)
    for x in (100, 900, 2600, 3300):
        assert px(with_line, x, 720) == px(without, x, 720)


def test_lines_toggle_off():
    sc = scene([290.0, 302.0], [10.0, 10.0], [7.0, 7.0], [0, 0], hips=[1, 2])
    c = [Constellation("Tst", "Test", [[1, 2]])]
    on = render_sky(sc, c, P(), Config(show_constellation_names=False))
    off = render_sky(sc, c, P(), Config(show_constellation_lines=False, show_constellation_names=False))
    (x1, y1), (x2, y2) = P().project(290.0, 10.0), P().project(302.0, 10.0)
    mx, my = round((x1 + x2) / 2), round((y1 + y2) / 2)
    assert window_sum(on, mx, my) > window_sum(off, mx, my)
