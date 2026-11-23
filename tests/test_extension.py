import ast
import json

from skywall.extension import UUID, enable_extension, install_extension


class FakeShellSettings:
    def __init__(self, initial: str):
        self.value = initial
        self.calls = []

    def __call__(self, cmd):
        self.calls.append(cmd)
        if cmd[:4] == ["gsettings", "get", "org.gnome.shell", "enabled-extensions"]:
            return self.value + "\n"
        if cmd[:4] == ["gsettings", "set", "org.gnome.shell", "enabled-extensions"]:
            self.value = cmd[4]
        return ""


def test_install_fills_in_binary(tmp_path):
    install_extension(tmp_path, "/x/.venv/bin/skywall")
    d = tmp_path / UUID
    assert json.loads((d / "metadata.json").read_text())["uuid"] == UUID
    js = (d / "extension.js").read_text()
    assert "/x/.venv/bin/skywall" in js and "@BIN@" not in js


def test_enable_preserves_other_extensions_and_is_idempotent():
    r = FakeShellSettings("['pano@elhan.io', 'user-theme@gnome-shell-extensions.gcampax.github.com']")
    enable_extension(r)
    enable_extension(r)
    assert ast.literal_eval(r.value) == ["pano@elhan.io", "user-theme@gnome-shell-extensions.gcampax.github.com", UUID]


def test_enable_from_empty():
    r = FakeShellSettings("@as []")
    enable_extension(r)
    assert ast.literal_eval(r.value) == [UUID]
