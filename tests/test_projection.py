import numpy as np
import pytest

from skywall.projection import StereographicProjection


def P():
    return StereographicProjection(296.0, 0.0, 60.0, 3440, 1440)


def test_centre_maps_to_screen_centre():
    assert P().project(296.0, 0.0) == pytest.approx((1720.0, 720.0))


def test_half_fov_on_horizon_hits_right_edge():
    x, y = P().project(326.0, 0.0)
    assert x == pytest.approx(3440.0, abs=0.5) and y == pytest.approx(720.0)


def test_east_is_right_and_up_is_up():
    p = P()
    assert p.project(300.0, 0.0)[0] > 1720 and p.project(296.0, 10.0)[1] < 720


def test_wraps_across_north():
    p = StereographicProjection(355.0, 0.0, 60.0, 3440, 1440)
    assert p.project(5.0, 0.0)[0] > 1720


def test_antipode_is_invalid():
    assert P().project(116.0, 0.0) is None


def test_vfov_for_ultrawide():
    assert P().vfov_deg == pytest.approx(25.6, abs=0.1)


def test_project_many_matches_project():
    p = P()
    x, y, ok = p.project_many(np.array([296.0, 116.0]), np.array([0.0, 0.0]))
    assert ok.tolist() == [True, False] and (x[0], y[0]) == pytest.approx((1720.0, 720.0))
