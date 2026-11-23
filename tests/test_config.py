from skywall.config import Config, load_config, save_config


def test_missing_file_gives_defaults(tmp_path):
    cfg = load_config(tmp_path / "c.toml")
    assert cfg.facing_deg == 296.0 and cfg.facing_reference == "magnetic"
    assert cfg.fov_deg == 60.0 and (cfg.width, cfg.height) == (3440, 1440)
    assert cfg.latitude is None


def test_round_trip(tmp_path):
    p = tmp_path / "c.toml"
    save_config(Config(latitude=51.48, longitude=0.0, fov_deg=90.0,
                       saved_wallpaper={"picture-uri": "file:///x.png"}), p)
    cfg = load_config(p)
    assert cfg.latitude == 51.48 and cfg.fov_deg == 90.0
    assert cfg.saved_wallpaper == {"picture-uri": "file:///x.png"}


def test_out_of_range_values_clamped(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('fov_deg = 500\ntilt_deg = -200\nfacing_deg = 365\nfacing_reference = "bogus"\nunknown = 1\n')
    cfg = load_config(p)
    assert (cfg.fov_deg, cfg.tilt_deg, cfg.facing_deg, cfg.facing_reference) == (180.0, -90.0, 5.0, "magnetic")


def test_projection_setting(tmp_path):
    p = tmp_path / "c.toml"
    assert load_config(p).projection == "perspective"
    p.write_text('projection = "fisheye"\n')
    assert load_config(p).projection == "perspective"
    p.write_text('projection = "stereographic"\n')
    assert load_config(p).projection == "stereographic"
