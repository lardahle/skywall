from conftest import FakeRunner

from skywall import cli
from skywall.config import Config, load_config, save_config
from skywall.scheduler import install_units, set_autostart, unit_texts


def test_unit_texts():
    u = unit_texts("/home/u/skywall/.venv/bin/skywall")
    assert "ExecStart=/home/u/skywall/.venv/bin/skywall render" in u["skywall.service"]
    assert "OnCalendar=*:*:00" in u["skywall.timer"] and "WantedBy=timers.target" in u["skywall.timer"]


def test_install_units_writes_and_reloads(tmp_path):
    r = FakeRunner()
    install_units(tmp_path, "/x/skywall", r)
    assert (tmp_path / "skywall.timer").exists() and (tmp_path / "skywall.service").exists()
    assert r.calls == [["systemctl", "--user", "daemon-reload"]]


def test_autostart_commands():
    r = FakeRunner()
    set_autostart(True, r)
    set_autostart(False, r)
    assert r.calls == [["systemctl", "--user", "enable", "skywall.timer"],
                       ["systemctl", "--user", "disable", "skywall.timer"]]


def test_disable_restores_and_stops(tmp_path, monkeypatch):
    cfg_path = tmp_path / "c.toml"
    monkeypatch.setenv("SKYWALL_CONFIG", str(cfg_path))
    save_config(Config(latitude=1.0, longitude=1.0, live_wallpaper=True, autostart=True,
                       saved_wallpaper={"picture-uri": "file:///old.png"}), cfg_path)
    r = FakeRunner()
    monkeypatch.setattr(cli, "RUNNER", r)
    assert cli.main(["disable"]) == 0
    assert ["systemctl", "--user", "stop", "skywall.timer"] in r.calls
    assert ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", "file:///old.png"] in r.calls
    cfg = load_config(cfg_path)
    assert cfg.live_wallpaper is False and cfg.autostart is False and cfg.saved_wallpaper == {}


def test_autostart_refused_while_live_off(tmp_path, monkeypatch):
    monkeypatch.setenv("SKYWALL_CONFIG", str(tmp_path / "c.toml"))
    r = FakeRunner()
    monkeypatch.setattr(cli, "RUNNER", r)
    assert cli.main(["autostart", "on"]) == 1 and r.calls == []
