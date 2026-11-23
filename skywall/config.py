"""Configuration: defaults, load/save (TOML in the XDG config dir)."""

import os
import tomllib
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path

import tomli_w


def _xdg(var: str, fallback: str) -> Path:
    return Path(os.environ.get(var) or Path.home() / fallback)


CONFIG_PATH = _xdg("XDG_CONFIG_HOME", ".config") / "skywall" / "config.toml"
DATA_DIR = _xdg("XDG_DATA_HOME", ".local/share") / "skywall"


@dataclass
class Config:
    latitude: float | None = None
    longitude: float | None = None
    elevation_m: float = 0.0
    facing_deg: float = 296.0
    facing_reference: str = "magnetic"
    tilt_deg: float = 0.0
    fov_deg: float = 60.0
    projection: str = "perspective"  # perspective (true window) | stereographic (better for wide FOV)
    width: int = 3440
    height: int = 1440
    mag_limit: float = 6.5
    show_constellation_lines: bool = True
    show_constellation_names: bool = True
    show_planet_labels: bool = True
    show_horizon: bool = True
    show_timestamp: bool = False
    live_wallpaper: bool = False
    autostart: bool = False
    saved_wallpaper: dict[str, str] = field(default_factory=dict)


def _normalise(cfg: Config) -> Config:
    cfg.fov_deg = float(min(180.0, max(20.0, cfg.fov_deg)))
    cfg.tilt_deg = float(min(90.0, max(-90.0, cfg.tilt_deg)))
    cfg.facing_deg = float(cfg.facing_deg) % 360.0
    if cfg.projection not in ("perspective", "stereographic"):
        cfg.projection = "perspective"
    if cfg.facing_reference not in ("magnetic", "true"):
        cfg.facing_reference = "magnetic"
    return cfg


def load_config(path: Path = CONFIG_PATH) -> Config:
    path = Path(path)
    if not path.exists():
        return Config()
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    known = {f.name for f in fields(Config)}
    return _normalise(Config(**{k: v for k, v in raw.items() if k in known}))


def save_config(cfg: Config, path: Path = CONFIG_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {k: v for k, v in asdict(cfg).items() if v is not None}
    tmp = path.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        tomli_w.dump(data, f)
    os.replace(tmp, path)


CLI_OWNED = ("live_wallpaper", "autostart", "saved_wallpaper")


def merge_owned(fresh: Config, edited: Config) -> Config:
    """`edited` (e.g. the settings window's copy) with the CLI-owned fields taken from `fresh`."""
    return replace(edited, **{k: getattr(fresh, k) for k in CLI_OWNED})
