"""Install and enable the GNOME Shell extension that adds Skywall to the desktop right-click menu."""

import ast
from pathlib import Path

from .runner import Runner, run

UUID = "skywall@local"
SOURCE = Path(__file__).resolve().parent.parent / "data" / "gnome-extension"
EXTENSIONS_DIR = Path.home() / ".local" / "share" / "gnome-shell" / "extensions"


def install_extension(extensions_dir: Path = EXTENSIONS_DIR, bin_path: str = "") -> Path:
    target = Path(extensions_dir) / UUID
    target.mkdir(parents=True, exist_ok=True)
    (target / "metadata.json").write_text((SOURCE / "metadata.json").read_text())
    (target / "extension.js").write_text((SOURCE / "extension.js.in").read_text().replace("@BIN@", bin_path))
    return target


def enable_extension(runner: Runner = run) -> None:
    raw = runner(["gsettings", "get", "org.gnome.shell", "enabled-extensions"]).strip()
    if raw.startswith("@as"):
        raw = raw[3:].strip()
    current = list(ast.literal_eval(raw)) if raw else []
    if UUID not in current:
        current.append(UUID)
        runner(["gsettings", "set", "org.gnome.shell", "enabled-extensions", str(current)])
