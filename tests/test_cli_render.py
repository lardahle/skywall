import cairo
import pytest

from skywall import cli
from skywall.catalog import DataUnavailable
from skywall.config import Config, save_config


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SKYWALL_CONFIG", str(tmp_path / "c.toml"))
    monkeypatch.setenv("SKYWALL_DATA", str(tmp_path / "data"))
    return tmp_path


def test_location_not_set_exits_2(env, capsys):  # Review Focus 1
    assert cli.main(["render", "--output", str(env / "o.png")]) == 2
    assert "location not set" in capsys.readouterr().err and not (env / "o.png").exists()


def test_data_unavailable_exits_3(env, monkeypatch, capsys):  # Review Focus 4
    save_config(Config(latitude=51.48, longitude=0.0), env / "c.toml")

    def boom(*a, **k):
        raise DataUnavailable("download failed: offline")
    monkeypatch.setattr(cli, "ensure_data", boom)
    assert cli.main(["render", "--output", str(env / "o.png")]) == 3
    assert "offline" in capsys.readouterr().err and not (env / "o.png").exists()


@pytest.mark.network
def test_render_writes_png(env, monkeypatch, data):
    save_config(Config(latitude=51.48, longitude=0.0), env / "c.toml")
    monkeypatch.setenv("SKYWALL_DATA", str(data))
    assert cli.main(["render", "--output", str(env / "o.png")]) == 0
    assert cairo.ImageSurface.create_from_png(str(env / "o.png")).get_width() == 3440


def test_open_without_location_exits_2(env, capsys):
    assert cli.main(["open"]) == 2
    assert "location not set" in capsys.readouterr().err
