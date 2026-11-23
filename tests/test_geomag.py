from datetime import datetime, timezone

import pytest

from skywall.config import Config
from skywall.geomag import declination_deg, true_facing_deg

WHEN = datetime(2026, 11, 22, tzinfo=timezone.utc)


def test_declination_boulder_is_about_7_east():
    assert 6.0 < declination_deg(40.0, -105.3, WHEN) < 9.0


def test_true_reference_passthrough():
    cfg = Config(latitude=40.0, longitude=-105.3, facing_deg=296.0, facing_reference="true")
    assert true_facing_deg(cfg, WHEN) == 296.0


def test_magnetic_adds_declination():
    cfg = Config(latitude=40.0, longitude=-105.3, facing_deg=296.0)
    assert true_facing_deg(cfg, WHEN) == pytest.approx(296.0 + declination_deg(40.0, -105.3, WHEN))


def test_wraps_past_360():  # Review Focus 2
    cfg = Config(latitude=40.0, longitude=-105.3, facing_deg=355.0)
    assert 0.0 <= true_facing_deg(cfg, WHEN) < 10.0
