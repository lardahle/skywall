import pytest

from skywall.stellarium import build_script, read_stellarium_location, stellarium_fov_deg


def test_reads_location(tmp_path):
    p = tmp_path / "config.ini"
    p.write_text("[init_location]\nlast_location = 51.4769, -0.0005\nlocation = auto\n")
    assert read_stellarium_location(p) == pytest.approx((51.4769, -0.0005))


def test_missing_location(tmp_path):
    p = tmp_path / "config.ini"
    p.write_text("[init_location]\nlocation = auto\n")
    assert read_stellarium_location(p) is None


def test_missing_file(tmp_path):
    assert read_stellarium_location(tmp_path / "nope.ini") is None


def test_fov_matches_projection():
    assert stellarium_fov_deg(60.0, 3440, 1440) == pytest.approx(25.6, abs=0.1)


def test_script_contents():
    s = build_script(51.48, 0.0, 0.0, 303.5, 0.0, 25.6)
    assert "setFlagLandscape(false)" in s and "setFlagAtmosphere(false)" in s
    assert 'core.moveToAltAzi("0", "303.5", 0)' in s
    assert "core.setObserverLocation(0.0, 51.48, 0.0, 0" in s  # longitude first
