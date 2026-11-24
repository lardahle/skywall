"""Command line: skywall render | enable | disable | autostart | open | install | settings."""

import argparse
import contextlib
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import config as config_mod
from .catalog import DataUnavailable, ensure_data, load_constellations, load_stars
from .config import Config, load_config, save_config
from .geomag import true_facing_deg
from .projection import make_projection
from .render import render_sky
from .runner import run
from .sky import compute_scene
from . import scheduler
from .extension import enable_extension, install_extension
from .keybinding import add_custom_keybinding
from .stellarium import open_in_stellarium
from . import wallpaper
from .wallpaper import next_wallpaper_path

RUNNER = run  # replaced in tests
IS_WINDOWS = sys.platform == "win32"  # tests pin this to exercise one backend
NO_LOCATION = "skywall: location not set — run `skywall settings`"


def config_path() -> Path:
    return Path(os.environ.get("SKYWALL_CONFIG") or config_mod.CONFIG_PATH)


def data_dir() -> Path:
    return Path(os.environ.get("SKYWALL_DATA") or config_mod.DATA_DIR)


def _wallpaper():
    """Module providing set_wallpaper / save_current / restore for this platform."""
    if IS_WINDOWS:
        from . import windows
        return windows
    return wallpaper


def _scheduler():
    """Module providing start / stop / stop_service / set_autostart for this platform."""
    if IS_WINDOWS:
        from . import windows
        return windows
    return scheduler


def _has_location(cfg: Config) -> bool:
    return cfg.latitude is not None and cfg.longitude is not None


def render_to(cfg: Config, out: Path, data: Path) -> None:
    ensure_data(data, cfg.mag_limit)
    now = datetime.now(timezone.utc)
    scene = compute_scene(cfg.latitude, cfg.longitude, cfg.elevation_m, now, load_stars(data, cfg.mag_limit), data)
    proj = make_projection(cfg.projection, true_facing_deg(cfg, now), cfg.tilt_deg, cfg.fov_deg,
                           cfg.width, cfg.height)
    surface = render_sky(scene, load_constellations(data), proj, cfg)
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=out.stem + ".", suffix=".tmp.png", dir=out.parent)
    os.close(fd)
    try:
        surface.write_to_png(tmp)
        os.replace(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextlib.contextmanager
def render_lock(data: Path, blocking: bool = True):
    """One render/download at a time (timer, settings window and CLI share the data dir)."""
    data = Path(data)
    data.mkdir(parents=True, exist_ok=True)
    with open(data / ".lock", "w") as f:
        _lock(f, blocking)
        try:
            yield
        finally:
            _unlock(f)


def _lock(f, blocking: bool) -> None:
    if os.name == "nt":
        import msvcrt
        import time
        while True:
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                if not blocking:
                    raise BlockingIOError("another skywall render holds the lock")
                time.sleep(0.1)
    import fcntl
    fcntl.flock(f, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))


def _unlock(f) -> None:
    if os.name == "nt":
        import msvcrt
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl
    fcntl.flock(f, fcntl.LOCK_UN)


def _render_wallpaper(cfg: Config, data: Path) -> int:
    with render_lock(data):
        out = next_wallpaper_path(data / "wallpaper")
        try:
            render_to(cfg, out, data)
        except DataUnavailable as e:
            print(f"skywall: star data unavailable: {e}", file=sys.stderr)
            return 3
        _wallpaper().set_wallpaper(out, RUNNER)
    return 0


def cmd_render(args) -> int:
    cfg = load_config(config_path())
    if not args.output and not cfg.live_wallpaper:
        return 0  # live wallpaper is off: never touch the desktop
    if not _has_location(cfg):
        print(NO_LOCATION, file=sys.stderr)
        return 2
    data = data_dir()
    if not args.output:
        return _render_wallpaper(cfg, data)
    try:
        with render_lock(data):
            render_to(cfg, Path(args.output), data)
    except DataUnavailable as e:
        print(f"skywall: star data unavailable: {e}", file=sys.stderr)
        return 3
    return 0


def _quietly(fn, *a) -> None:
    try:
        fn(*a)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"skywall: {e}", file=sys.stderr)


def cmd_enable(args) -> int:
    path = config_path()
    cfg = load_config(path)
    if not _has_location(cfg):
        print(NO_LOCATION, file=sys.stderr)
        return 2
    _wallpaper().save_current(cfg, data_dir() / "wallpaper", RUNNER)
    cfg.live_wallpaper = True
    save_config(cfg, path)
    code = _render_wallpaper(cfg, data_dir())
    if code:  # wallpaper was never changed: just roll the config back
        cfg = load_config(path)
        cfg.live_wallpaper = False
        cfg.saved_wallpaper = {}
        save_config(cfg, path)
        return code
    _scheduler().start(RUNNER)
    return 0


def cmd_disable(args) -> int:
    path = config_path()
    cfg = load_config(path)
    cfg.live_wallpaper = False  # saved first: any render still in flight becomes a no-op
    cfg.autostart = False
    save_config(cfg, path)
    with render_lock(data_dir()):
        _wallpaper().restore(cfg, RUNNER)
    save_config(cfg, path)
    sched = _scheduler()
    _quietly(sched.stop, RUNNER)
    _quietly(sched.stop_service, RUNNER)
    _quietly(sched.set_autostart, False, RUNNER)
    return 0


def cmd_autostart(args) -> int:
    path = config_path()
    cfg = load_config(path)
    on = args.state == "on"
    if on and not cfg.live_wallpaper:
        print("skywall: turn on the live wallpaper first (`skywall enable`)", file=sys.stderr)
        return 1
    _scheduler().set_autostart(on, RUNNER)
    cfg.autostart = on
    save_config(cfg, path)
    return 0


def _bin() -> str:
    return str(Path(sys.executable).parent / "skywall")


def cmd_open(args) -> int:
    cfg = load_config(config_path())
    if not _has_location(cfg):
        print(NO_LOCATION, file=sys.stderr)
        return 2
    open_in_stellarium(cfg, true_facing_deg(cfg, datetime.now(timezone.utc)), runner=RUNNER)
    return 0


def cmd_install(args) -> int:
    if IS_WINDOWS:
        from . import windows
        windows.install_task(enabled=load_config(config_path()).live_wallpaper, runner=RUNNER)
        windows.install_shortcuts()
        windows.install_context_menu()
        return 0
    exe = _bin()
    scheduler.install_units(scheduler.UNIT_DIR, exe, RUNNER)
    template = Path(__file__).resolve().parent.parent / "data" / "skywall.desktop.in"
    apps = Path.home() / ".local" / "share" / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    (apps / "skywall.desktop").write_text(template.read_text().replace("@BIN@", exe))
    add_custom_keybinding("Skywall: open in Stellarium", f"{exe} open", "<Super><Alt>s", RUNNER)
    install_extension(bin_path=exe)
    enable_extension(RUNNER)
    return 0


def cmd_settings(args) -> int:
    if IS_WINDOWS:  # no GTK/libadwaita here: edit the TOML, then `skywall render`/`enable`
        path = config_path()
        if not path.exists():
            save_config(Config(), path)
        subprocess.Popen(["notepad.exe", str(path)])
        return 0
    from .settings_app import run_settings
    return run_settings()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="skywall")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render", help="render the sky and set it as the wallpaper")
    r.add_argument("--output", help="write the PNG here instead of setting the wallpaper")
    r.set_defaults(func=cmd_render)
    sub.add_parser("enable", help="turn the live sky wallpaper on").set_defaults(func=cmd_enable)
    sub.add_parser("disable", help="turn it off and restore the previous wallpaper").set_defaults(func=cmd_disable)
    a = sub.add_parser("autostart", help="start with the GNOME session")
    a.add_argument("state", choices=["on", "off"])
    a.set_defaults(func=cmd_autostart)
    sub.add_parser("open", help="open Stellarium aimed at the same view").set_defaults(func=cmd_open)
    sub.add_parser("install", help="install timer, app entry and shortcut").set_defaults(func=cmd_install)
    sub.add_parser("settings", help="open the settings window").set_defaults(func=cmd_settings)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
