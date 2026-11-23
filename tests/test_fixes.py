import subprocess

import pytest
from conftest import FakeRunner

from skywall import cli
from skywall.catalog import DataUnavailable
from skywall.config import Config, load_config, merge_owned, save_config
from skywall.wallpaper import restore


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SKYWALL_CONFIG", str(tmp_path / "c.toml"))
    monkeypatch.setenv("SKYWALL_DATA", str(tmp_path / "data"))
    r = FakeRunner({"picture-uri": "'file:///old.png'", "picture-uri-dark": "'file:///old-d.png'",
                    "picture-options": "'zoom'"})
    monkeypatch.setattr(cli, "RUNNER", r)
    return tmp_path, r


def sets(r):
    return [c for c in r.calls if c[:2] == ["gsettings", "set"]]


def test_render_is_noop_when_live_off(env, monkeypatch):  # I1 / I2
    tmp, r = env
    save_config(Config(latitude=1.0, longitude=1.0, live_wallpaper=False), tmp / "c.toml")
    monkeypatch.setattr(cli, "render_to", lambda *a, **k: pytest.fail("rendered while live is off"))
    assert cli.main(["render"]) == 0 and sets(r) == []


def test_disable_stops_running_service(env):  # I1
    tmp, r = env
    save_config(Config(live_wallpaper=True), tmp / "c.toml")
    cli.main(["disable"])
    assert ["systemctl", "--user", "stop", "skywall.service"] in r.calls


def test_enable_failure_rolls_back(env, monkeypatch):  # I4 / M4
    tmp, r = env
    save_config(Config(latitude=1.0, longitude=1.0), tmp / "c.toml")

    def boom(*a, **k):
        raise DataUnavailable("offline")
    monkeypatch.setattr(cli, "ensure_data", boom)
    assert cli.main(["enable"]) == 3
    assert ["systemctl", "--user", "start", "skywall.timer"] not in r.calls
    cfg = load_config(tmp / "c.toml")
    assert cfg.live_wallpaper is False and cfg.saved_wallpaper == {} and sets(r) == []


def test_enable_starts_timer_only_after_render(env, monkeypatch):  # I4
    tmp, r = env
    save_config(Config(latitude=1.0, longitude=1.0), tmp / "c.toml")
    order = []
    monkeypatch.setattr(cli, "render_to", lambda *a, **k: order.append("render"))
    real = cli.RUNNER

    def rec(cmd):
        if cmd[:3] == ["systemctl", "--user", "start"]:
            order.append("start")
        return real(cmd)
    monkeypatch.setattr(cli, "RUNNER", rec)
    assert cli.main(["enable"]) == 0 and order == ["render", "start"]


def test_render_lock_is_exclusive(tmp_path):  # I4
    with cli.render_lock(tmp_path):
        with pytest.raises(BlockingIOError):
            with cli.render_lock(tmp_path, blocking=False):
                pass


def test_disable_restores_even_if_systemctl_fails(env, monkeypatch):  # M3
    tmp, r = env
    save_config(Config(live_wallpaper=True, saved_wallpaper={"picture-uri": "file:///old.png",
                "picture-uri-dark": "file:///old-d.png", "picture-options": "zoom"}), tmp / "c.toml")

    def flaky(cmd):
        if cmd[0] == "systemctl":
            raise subprocess.CalledProcessError(1, cmd)
        return r(cmd)
    monkeypatch.setattr(cli, "RUNNER", flaky)
    assert cli.main(["disable"]) == 0
    assert ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", "file:///old.png"] in r.calls
    assert load_config(tmp / "c.toml").live_wallpaper is False


def test_restore_resets_keys_that_were_empty():  # M8
    r = FakeRunner()
    cfg = Config(saved_wallpaper={"picture-uri": "file:///old.png", "picture-uri-dark": "", "picture-options": "zoom"})
    restore(cfg, r)
    assert ["gsettings", "reset", "org.gnome.desktop.background", "picture-uri-dark"] in r.calls
    assert not any(c[:2] == ["gsettings", "set"] and c[4] == "" for c in r.calls)


def test_merge_owned_keeps_cli_fields():  # I3
    fresh = Config(live_wallpaper=True, autostart=True, saved_wallpaper={"picture-uri": "file:///old.png"})
    edited = Config(fov_deg=90.0, latitude=5.0, live_wallpaper=False, autostart=False, saved_wallpaper={})
    m = merge_owned(fresh, edited)
    assert m.fov_deg == 90.0 and m.latitude == 5.0
    assert m.live_wallpaper is True and m.autostart is True and m.saved_wallpaper == {"picture-uri": "file:///old.png"}
