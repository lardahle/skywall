import ast

from skywall.keybinding import BASE, add_custom_keybinding

LIST_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"


class FakeKeybindingRunner:
    def __init__(self, initial: str):
        self.store = {(LIST_SCHEMA, "custom-keybindings"): initial}
        self.calls = []

    def __call__(self, cmd):
        self.calls.append(cmd)
        if cmd[1] == "get":
            return self.store.get((cmd[2], cmd[3]), "''") + "\n"
        if cmd[1] == "set":
            self.store[(cmd[2], cmd[3])] = cmd[4]
        return ""

    def current_list(self):
        raw = self.store[(LIST_SCHEMA, "custom-keybindings")]
        return [] if raw.startswith("@as") else ast.literal_eval(raw)


def test_keybinding_preserves_existing_and_is_idempotent():  # Review Focus 5
    existing = f"['{BASE}custom0/']"
    r = FakeKeybindingRunner(existing)
    add_custom_keybinding("Skywall", "/x/skywall open", "<Super><Alt>s", r)
    add_custom_keybinding("Skywall", "/x/skywall open", "<Super><Alt>s", r)
    assert r.current_list() == [f"{BASE}custom0/", f"{BASE}skywall/"]
    entry = f"{LIST_SCHEMA}.custom-keybinding:{BASE}skywall/"
    assert r.store[(entry, "binding")] == "<Super><Alt>s" and r.store[(entry, "command")] == "/x/skywall open"


def test_keybinding_from_empty_list():
    r = FakeKeybindingRunner("@as []")
    add_custom_keybinding("Skywall", "/x/skywall open", "<Super><Alt>s", r)
    assert r.current_list() == [f"{BASE}skywall/"]
