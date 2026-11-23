import subprocess

import pytest

from skywall.catalog import DataUnavailable, ensure_data, load_constellations, load_stars


@pytest.mark.network
def test_sirius_parsed(data):
    s = load_stars(data)
    i = list(s.hip).index(32349)
    assert s.mag[i] == pytest.approx(-1.44, abs=0.01) and s.bv[i] == pytest.approx(0.009, abs=0.01)


@pytest.mark.network
def test_magnitude_limit_applied(data):
    s = load_stars(data)
    line_stars = {h for c in load_constellations(data) for line in c.lines for h in line}
    faint = [h for h, m in zip(s.hip.tolist(), s.mag) if m > 6.5]
    assert set(faint) <= line_stars and 8000 < len(s.hip) < 10000


@pytest.mark.network
def test_orion_constellation(data):
    ori = next(c for c in load_constellations(data) if c.abbr == "Ori")
    assert ori.name == "Orion" and any(27989 in line for line in ori.lines)  # Betelgeuse


def test_missing_stellarium_raises(tmp_path):
    def runner(cmd):
        raise subprocess.CalledProcessError(1, cmd)
    with pytest.raises(DataUnavailable):
        ensure_data(tmp_path, runner=runner)


@pytest.mark.network
def test_every_constellation_line_star_present(data):
    hips = set(load_stars(data).hip.tolist())
    needed = {h for c in load_constellations(data) for line in c.lines for h in line}
    assert needed <= hips


@pytest.mark.network
def test_star_names(data):
    s = load_stars(data)
    assert s.name[list(s.hip).index(69673)] == "Arcturus"


@pytest.mark.network
def test_fainter_limit_gives_more_stars(data):
    assert len(load_stars(data, mag_limit=7.5).hip) > len(load_stars(data, mag_limit=6.5).hip) + 5000


def test_bayer_label():
    from skywall.catalog import bayer_label
    assert bayer_label("Zet", "Boo") == "ζ Boo"
    assert bayer_label("Kap-2", "Boo") == "κ² Boo"
    assert bayer_label("Omi", "Boo") == "ο Boo"
    assert bayer_label("", "Boo") == ""


@pytest.mark.network
def test_designations_loaded(data):
    s = load_stars(data)
    assert "ζ Boo" in set(s.designation.tolist()) and s.designation.dtype.kind == "U"
