"""Set, save and restore the GNOME desktop background via gsettings."""

import ast

from pathlib import Path

from .config import Config
from .runner import Runner, run

SCHEMA = "org.gnome.desktop.background"
KEYS = ("picture-uri", "picture-uri-dark", "picture-options")
NAMES = ("sky-a.png", "sky-b.png")


def _get(key: str, runner: Runner) -> str:
    raw = runner(["gsettings", "get", SCHEMA, key]).strip()
    try:
        return ast.literal_eval(raw) if raw[:1] in "'\"" else raw
    except (ValueError, SyntaxError):
        return raw.strip("'")


def _set(key: str, value: str, runner: Runner) -> None:
    runner(["gsettings", "set", SCHEMA, key, value])


def next_wallpaper_path(out_dir: Path) -> Path:
    """The alternate file to the one written last (a missing file counts as oldest)."""
    out_dir = Path(out_dir)
    a, b = (out_dir / n for n in NAMES)
    mtime = lambda p: p.stat().st_mtime if p.exists() else -1.0
    return a if mtime(a) <= mtime(b) else b


def set_wallpaper(path: Path, runner: Runner = run) -> None:
    uri = Path(path).as_uri()
    _set("picture-uri", uri, runner)
    _set("picture-uri-dark", uri, runner)
    _set("picture-options", "zoom", runner)


def save_current(cfg: Config, out_dir: Path, runner: Runner = run) -> None:
    if cfg.saved_wallpaper:
        return
    current = {k: _get(k, runner) for k in KEYS}
    if current["picture-uri"].startswith(Path(out_dir).as_uri()):
        return  # already ours; nothing of the user's to save
    cfg.saved_wallpaper = current


def restore(cfg: Config, runner: Runner = run) -> None:
    if not cfg.saved_wallpaper:
        return
    for k in KEYS:
        if cfg.saved_wallpaper.get(k):
            _set(k, cfg.saved_wallpaper[k], runner)
        else:
            runner(["gsettings", "reset", SCHEMA, k])  # never write an empty URI
    cfg.saved_wallpaper = {}
