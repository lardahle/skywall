"""Add a GNOME custom keyboard shortcut without disturbing existing ones."""

import ast

from .runner import Runner, run

SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
BASE = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"


def _parse_list(raw: str) -> list[str]:
    raw = raw.strip()
    if raw.startswith("@as"):
        raw = raw[3:].strip()
    return list(ast.literal_eval(raw)) if raw else []


def add_custom_keybinding(name: str, command: str, binding: str, runner: Runner = run,
                          slot: str = "skywall") -> None:
    path = f"{BASE}{slot}/"
    current = _parse_list(runner(["gsettings", "get", SCHEMA, "custom-keybindings"]))
    if path not in current:
        current.append(path)
        runner(["gsettings", "set", SCHEMA, "custom-keybindings", str(current)])
    entry = f"{SCHEMA}.custom-keybinding:{path}"
    for key, value in (("name", name), ("command", command), ("binding", binding)):
        runner(["gsettings", "set", entry, key, value])
