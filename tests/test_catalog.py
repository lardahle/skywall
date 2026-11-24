import io
import json
import subprocess

import pytest

from skywall import catalog
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


def _no_flatpak(cmd):
    raise subprocess.CalledProcessError(1, cmd)


def _no_local_stellarium(monkeypatch):
    monkeypatch.setattr(catalog, "_windows_stellarium_dirs", lambda: [])


def test_missing_stellarium_and_offline_raises(tmp_path, monkeypatch):
    _no_local_stellarium(monkeypatch)

    def offline(*a, **k):
        raise OSError("offline")
    monkeypatch.setattr(catalog.urllib.request, "urlopen", offline)
    with pytest.raises(DataUnavailable):
        ensure_data(tmp_path, runner=_no_flatpak)


def test_missing_stellarium_downloads_sky_culture(tmp_path, monkeypatch):
    _no_local_stellarium(monkeypatch)
    index = {"constellations": [{"id": "CON modern Ori", "common_name": {"native": "Orion"},
                                 "lines": [[27989, 26727]]}]}

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    monkeypatch.setattr(catalog.urllib.request, "urlopen",
                        lambda url, timeout=0: Resp(json.dumps(index).encode()))
    path = catalog._stellarium_index(_no_flatpak, tmp_path)
    catalog._build_constellations(path, tmp_path / "constellations.json")
    assert [c.abbr for c in load_constellations(tmp_path)] == ["Ori"]


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
