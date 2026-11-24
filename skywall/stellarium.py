"""Hand-off to Stellarium: read its location, aim it at Skywall's view."""

import configparser
import os
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

from .catalog import STELLARIUM_APP
from .config import Config
from .projection import make_projection
from .runner import Runner, run

if os.name == "nt":
    _USER_DIR = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "Stellarium"
else:
    _USER_DIR = Path.home() / ".stellarium"
STELLARIUM_CONFIG = _USER_DIR / "config.ini"
SCRIPTS_DIR = _USER_DIR / "scripts"
SCRIPT_NAME = "skywall.ssc"
REMOTE_URL = "http://localhost:8090/api/scripts/direct"


def read_stellarium_location(config_ini: Path = STELLARIUM_CONFIG) -> tuple[float, float] | None:
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        cp.read(config_ini, encoding="utf-8")
        lat, lon = (float(v) for v in cp["init_location"]["last_location"].split(","))
        return lat, lon
    except (KeyError, ValueError, configparser.Error):
        return None


def stellarium_fov_deg(hfov_deg: float, width: int, height: int, projection: str = "stereographic") -> float:
    """Stellarium's FOV spans the screen's shorter (vertical) side."""
    return make_projection(projection, 0.0, 0.0, hfov_deg, width, height).vfov_deg


def build_script(lat: float, lon: float, elevation_m: float, true_az: float, tilt: float,
                 fov_deg: float, projection: str = "stereographic") -> str:
    mode = "ProjectionPerspective" if projection == "perspective" else "ProjectionStereographic"
    return "\n".join([
        f'core.setObserverLocation({lon}, {lat}, {elevation_m}, 0, "Skywall", "Earth");',
        'core.setDate("now");',
        "core.setTimeRate(1);",
        "LandscapeMgr.setFlagLandscape(false);",
        "LandscapeMgr.setFlagAtmosphere(false);",
        "LandscapeMgr.setFlagFog(false);",
        "ConstellationMgr.setFlagLines(true);",
        "ConstellationMgr.setFlagLabels(true);",
        f'core.setProjectionMode("{mode}");',
        f'core.moveToAltAzi("{tilt:g}", "{true_az:g}", 0);',
        f"StelMovementMgr.zoomTo({fov_deg:.3f}, 0);",
        "",
    ])


def _windows_exe() -> Path | None:
    from .catalog import _windows_stellarium_dirs
    return next((d / "stellarium.exe" for d in _windows_stellarium_dirs() if (d / "stellarium.exe").exists()), None)


def _running(runner: Runner) -> bool:
    if os.name == "nt":
        try:
            return "stellarium.exe" in runner(["tasklist", "/FI", "IMAGENAME eq stellarium.exe", "/NH"]).lower()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    try:
        return STELLARIUM_APP in runner(["flatpak", "ps", "--columns=application"])
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def open_in_stellarium(cfg: Config, true_az: float, scripts_dir: Path = SCRIPTS_DIR,
                       runner: Runner = run) -> None:
    script = build_script(cfg.latitude, cfg.longitude, cfg.elevation_m, true_az, cfg.tilt_deg,
                          stellarium_fov_deg(cfg.fov_deg, cfg.width, cfg.height, cfg.projection),
                          cfg.projection)
    if _running(runner):
        try:
            body = urllib.parse.urlencode({"code": script}).encode()
            urllib.request.urlopen(REMOTE_URL, data=body, timeout=3)
        except OSError:
            msg = "Stellarium is already open — enable its Remote Control plugin to re-aim it"
            if os.name == "nt":
                from .windows import notify
                notify(msg)
            else:
                subprocess.Popen(["notify-send", "Skywall", msg])
        return
    scripts_dir = Path(scripts_dir)
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / SCRIPT_NAME).write_text(script, encoding="utf-8")
    if os.name == "nt":
        exe = _windows_exe()
        if exe is None:
            from .windows import notify
            notify("Stellarium isn't installed — winget install Stellarium.Stellarium")
            return
        subprocess.Popen([str(exe), "--startup-script", SCRIPT_NAME], cwd=exe.parent,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=subprocess.DETACHED_PROCESS)
        return
    subprocess.Popen(["flatpak", "run", STELLARIUM_APP, "--startup-script", SCRIPT_NAME],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
