import sys
import xml.etree.ElementTree as ET

import pytest
from conftest import FakeRunner

from skywall import cli, windows
from skywall.config import Config, load_config, save_config

pytestmark = pytest.mark.windows
NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}


def test_task_runs_every_minute_windowless_on_battery():
    root = ET.fromstring(windows.task_xml([r"C:\py\pythonw.exe", "-m", "skywall.cli", "render"],
                                          r"PC\me", enabled=True).split("\n", 1)[1])
    assert root.findtext(".//t:Repetition/t:Interval", namespaces=NS) == "PT1M"
    assert root.findtext(".//t:DisallowStartIfOnBatteries", namespaces=NS) == "false"
    assert root.findtext(".//t:MultipleInstancesPolicy", namespaces=NS) == "IgnoreNew"
    assert root.findtext(".//t:LogonType", namespaces=NS) == "InteractiveToken"
    assert root.findtext(".//t:Exec/t:Command", namespaces=NS) == r"C:\py\pythonw.exe"
    assert root.findtext(".//t:Exec/t:Arguments", namespaces=NS) == "-m skywall.cli render"
    assert root.findtext("t:Settings/t:Enabled", namespaces=NS) == "true"


@pytest.fixture
def win(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "IS_WINDOWS", True)
    monkeypatch.setenv("SKYWALL_CONFIG", str(tmp_path / "c.toml"))
    monkeypatch.setenv("SKYWALL_DATA", str(tmp_path / "data"))
    r = FakeRunner()
    monkeypatch.setattr(cli, "RUNNER", r)
    state = {"wallpaper": r"C:\old.jpg", "applied": []}
    monkeypatch.setattr(windows, "_get_wallpaper_path", lambda: state["wallpaper"])
    monkeypatch.setattr(windows, "_read_desktop", lambda name, default: {"WallpaperStyle": "6"}.get(name, default))
    monkeypatch.setattr(windows, "_apply_wallpaper", lambda *a: state["applied"].append(a))
    monkeypatch.setattr(cli, "render_to", lambda cfg, out, data: out.parent.mkdir(parents=True, exist_ok=True))
    return tmp_path, r, state


def test_enable_then_disable_round_trips_wallpaper(win):
    tmp, r, state = win
    save_config(Config(latitude=37.1, longitude=-113.6), tmp / "c.toml")
    assert cli.main(["enable"]) == 0
    assert state["applied"][-1][1:] == ("10", "0") and "sky-" in state["applied"][-1][0]
    assert ["schtasks", "/Change", "/TN", "Skywall", "/ENABLE"] in r.calls
    assert load_config(tmp / "c.toml").saved_wallpaper["path"] == r"C:\old.jpg"

    assert cli.main(["disable"]) == 0
    assert state["applied"][-1] == (r"C:\old.jpg", "6", "0")
    assert ["schtasks", "/Change", "/TN", "Skywall", "/DISABLE"] in r.calls
    assert load_config(tmp / "c.toml").saved_wallpaper == {}


@pytest.mark.skipif(sys.platform != "win32", reason="msvcrt locking")
def test_render_lock_is_exclusive_on_windows(tmp_path):
    with cli.render_lock(tmp_path):
        with pytest.raises(BlockingIOError):
            with cli.render_lock(tmp_path, blocking=False):
                pass
    with cli.render_lock(tmp_path, blocking=False):
        pass  # released
