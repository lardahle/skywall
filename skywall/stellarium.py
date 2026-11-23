"""Hand-off to Stellarium: read its location, aim it at Skywall's view."""

import configparser
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

from .catalog import STELLARIUM_APP
from .config import Config
from .projection import make_projection
from .runner import Runner, run

STELLARIUM_CONFIG = Path.home() / ".stellarium" / "config.ini"
SCRIPTS_DIR = Path.home() / ".stellarium" / "scripts"
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


def _running(runner: Runner) -> bool:
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
            subprocess.Popen(["notify-send", "Skywall",
                              "Stellarium is already open — enable its Remote Control plugin to re-aim it"])
        return
    scripts_dir = Path(scripts_dir)
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / SCRIPT_NAME).write_text(script)
    subprocess.Popen(["flatpak", "run", STELLARIUM_APP, "--startup-script", SCRIPT_NAME],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
