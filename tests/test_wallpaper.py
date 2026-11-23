from conftest import FakeRunner

from skywall.config import Config
from skywall.wallpaper import next_wallpaper_path, restore, save_current, set_wallpaper

OLD = {"picture-uri": "'file:///old.png'", "picture-uri-dark": "'file:///old-d.png'", "picture-options": "'zoom'"}


def test_alternates_files(tmp_path):
    a = next_wallpaper_path(tmp_path)
    a.write_bytes(b"x")
    assert next_wallpaper_path(tmp_path).name != a.name


def test_set_wallpaper_sets_both_uris(tmp_path):
    r = FakeRunner()
    set_wallpaper(tmp_path / "sky-a.png", r)
    uri = (tmp_path / "sky-a.png").as_uri()
    assert ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri] in r.calls
    assert ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri] in r.calls


def test_save_then_restore_round_trip(tmp_path):
    r = FakeRunner(OLD)
    cfg = Config()
    save_current(cfg, tmp_path, r)
    restore(cfg, r)
    assert ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", "file:///old.png"] in r.calls
    assert cfg.saved_wallpaper == {}


def test_does_not_save_own_wallpaper(tmp_path):
    own = (tmp_path / "sky-a.png").as_uri()
    r = FakeRunner({**OLD, "picture-uri": f"'{own}'"})
    cfg = Config()
    save_current(cfg, tmp_path, r)
    assert cfg.saved_wallpaper == {}


def test_restore_with_nothing_saved_sets_nothing():
    r = FakeRunner()
    restore(Config(), r)
    assert not any(c[1] == "set" for c in r.calls)
