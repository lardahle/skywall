from datetime import datetime, timezone

import pytest

from skywall.catalog import load_stars
from skywall.sky import compute_scene

GREENWICH = (51.4769, -0.0005)
pytestmark = pytest.mark.network


def test_polaris_altitude_equals_latitude(data):
    sc = compute_scene(*GREENWICH, 0.0, datetime(2026, 11, 22, 3, tzinfo=timezone.utc), load_stars(data), data)
    assert sc.star_alt[sc.hip_index[11767]] == pytest.approx(51.48, abs=1.0)


def test_midsummer_noon_sun(data):
    sc = compute_scene(*GREENWICH, 0.0, datetime(2026, 6, 21, 12, tzinfo=timezone.utc), load_stars(data), data)
    sun = sc.bodies[0]
    assert sun.name == "Sun" and sun.alt_deg == pytest.approx(61.96, abs=0.5) and sun.az_deg == pytest.approx(180, abs=3)


def test_below_horizon_stars_kept(data):
    sc = compute_scene(*GREENWICH, 0.0, datetime(2026, 11, 22, tzinfo=timezone.utc), load_stars(data), data)
    assert (sc.star_alt < 0).sum() > 3000  # see-through Earth
    assert sc.bodies[1].name == "Moon" and 0.0 <= sc.bodies[1].phase_fraction <= 1.0
