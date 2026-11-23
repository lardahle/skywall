import math

import numpy as np
import pytest

from skywall.projection import PerspectiveProjection, StereographicProjection, make_projection


def P(tilt=0.0, fov=60.0):
    return PerspectiveProjection(296.0, tilt, fov, 3440, 1440)


def test_centre_on_horizon_at_screen_centre_when_level():
    assert P().project(296.0, 0.0) == pytest.approx((1720.0, 720.0))


def test_half_fov_hits_right_edge():
    assert P().project(326.0, 0.0)[0] == pytest.approx(3440.0, abs=0.5)


def test_horizon_is_straight():
    ys = [P(tilt=3.3, fov=44.9).project(296.0 + d, 0.0)[1] for d in (-20, -10, 0, 10, 20)]
    assert max(ys) - min(ys) < 1e-6


def test_vertical_lines_stay_vertical():
    p = P()
    assert p.project(306.0, 0.0)[0] == pytest.approx(p.project(306.0, 25.0)[0])


def test_tilt_moves_horizon_to_eye_line():
    # 38" from a 797x334 mm screen, eyes on the lower third line
    p = P(tilt=math.degrees(math.atan((334 / 6) / 965)), fov=math.degrees(2 * math.atan(398.5 / 965)))
    assert p.project(296.0, 0.0)[1] == pytest.approx(960.0, abs=1.0)


def test_behind_the_window_is_invalid():
    assert P().project(296.0 + 95.0, 0.0) is None


def test_vfov_for_ultrawide():
    assert P().vfov_deg == pytest.approx(2 * math.degrees(math.atan(1440 / 3440 * math.tan(math.radians(30)))))


def test_project_many_matches_project():
    p = P()
    x, y, ok = p.project_many(np.array([296.0, 116.0]), np.array([0.0, 0.0]))
    assert ok.tolist() == [True, False] and (x[0], y[0]) == pytest.approx((1720.0, 720.0))


def test_factory():
    assert isinstance(make_projection("perspective", 0, 0, 60, 3440, 1440), PerspectiveProjection)
    assert isinstance(make_projection("stereographic", 0, 0, 60, 3440, 1440), StereographicProjection)
