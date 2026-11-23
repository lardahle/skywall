"""Command line: skywall render | enable | disable | autostart | open | install | settings."""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import config as config_mod
from .catalog import DataUnavailable, ensure_data, load_constellations, load_stars
from .config import Config, load_config
from .geomag import true_facing_deg
from .projection import StereographicProjection
from .render import render_sky
from .runner import run
from .sky import compute_scene
from .wallpaper import next_wallpaper_path, set_wallpaper

NO_LOCATION = "skywall: location not set — run `skywall settings`"


def config_path() -> Path:
    return Path(os.environ.get("SKYWALL_CONFIG") or config_mod.CONFIG_PATH)


def data_dir() -> Path:
    return Path(os.environ.get("SKYWALL_DATA") or config_mod.DATA_DIR)


def _has_location(cfg: Config) -> bool:
    return cfg.latitude is not None and cfg.longitude is not None


def render_to(cfg: Config, out: Path, data: Path) -> None:
    ensure_data(data, cfg.mag_limit)
    now = datetime.now(timezone.utc)
    scene = compute_scene(cfg.latitude, cfg.longitude, cfg.elevation_m, now, load_stars(data), data)
    proj = StereographicProjection(true_facing_deg(cfg, now), cfg.tilt_deg, cfg.fov_deg,
                                   cfg.width, cfg.height)
    surface = render_sky(scene, load_constellations(data), proj, cfg)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".tmp.png")
    surface.write_to_png(str(tmp))
    os.replace(tmp, out)


def cmd_render(args, runner=run) -> int:
    cfg = load_config(config_path())
    if not _has_location(cfg):
        print(NO_LOCATION, file=sys.stderr)
        return 2
    data = data_dir()
    out = Path(args.output) if args.output else next_wallpaper_path(data / "wallpaper")
    try:
        render_to(cfg, out, data)
    except DataUnavailable as e:
        print(f"skywall: star data unavailable: {e}", file=sys.stderr)
        return 3
    if not args.output:
        set_wallpaper(out, runner)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="skywall")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render", help="render the sky and set it as the wallpaper")
    r.add_argument("--output", help="write the PNG here instead of setting the wallpaper")
    r.set_defaults(func=cmd_render)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
