"""Settings window (GTK4 + libadwaita 1.2)."""

import argparse
import threading
from datetime import datetime, timezone

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from . import cli  # noqa: E402
from .config import load_config, save_config  # noqa: E402
from .geomag import true_facing_deg  # noqa: E402
from .stellarium import read_stellarium_location  # noqa: E402

APP_ID = "io.github.skywall.Settings"
RERENDER_DELAY_MS = 500


class SettingsWindow(Adw.PreferencesWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title="Skywall", default_width=560, default_height=720)
        self.cfg = load_config(cli.config_path())
        self._pending = 0
        self._busy = False
        self.add(self._sky_page())
        self.add(self._location_page())
        self.add(self._system_page())
        self._refresh_true_facing()

    # ── helpers ────────────────────────────────────────────────────────────
    def _toast(self, text: str) -> None:
        self.add_toast(Adw.Toast(title=text, timeout=4))

    def _changed(self) -> None:
        save_config(self.cfg, cli.config_path())
        if self.cfg.live_wallpaper:
            if self._pending:
                GLib.source_remove(self._pending)
            self._pending = GLib.timeout_add(RERENDER_DELAY_MS, self._rerender)

    def _in_worker(self, fn, done=None) -> None:
        def work():
            code = fn()
            GLib.idle_add(lambda: (done(code) if done else None, False)[1])
        threading.Thread(target=work, daemon=True).start()

    def _rerender(self) -> bool:
        self._pending = 0
        self._in_worker(lambda: cli.cmd_render(argparse.Namespace(output=None)),
                        lambda code: code and self._toast(f"Render failed (code {code})"))
        return False

    def _switch_row(self, title: str, active: bool, on_set, subtitle: str = ""):
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        sw = Gtk.Switch(active=active, valign=Gtk.Align.CENTER)
        sw.connect("notify::active", lambda s, _p: on_set(s.get_active()))
        row.add_suffix(sw)
        row.set_activatable_widget(sw)
        return row, sw

    def _cfg_switch(self, title: str, attr: str):
        def on_set(v):
            setattr(self.cfg, attr, v)
            self._changed()
        return self._switch_row(title, getattr(self.cfg, attr), on_set)[0]

    def _spin_row(self, title: str, lo: float, hi: float, value: float, on_set, step: float = 1.0,
                  digits: int = 1, subtitle: str = ""):
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        spin = Gtk.SpinButton.new_with_range(lo, hi, step)
        spin.set_digits(digits)
        spin.set_value(value)
        spin.set_valign(Gtk.Align.CENTER)
        spin.connect("value-changed", lambda s: on_set(s.get_value()))
        row.add_suffix(spin)
        return row

    # ── pages ──────────────────────────────────────────────────────────────
    def _sky_page(self):
        page = Adw.PreferencesPage(title="Sky", icon_name="weather-clear-night-symbolic")
        view = Adw.PreferencesGroup(title="View")
        fov_row = Adw.ActionRow(title="Field of view", subtitle="Degrees across the screen")
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 20, 180, 1)
        scale.set_value(self.cfg.fov_deg)
        scale.set_draw_value(True)
        scale.set_hexpand(True)
        scale.set_size_request(260, -1)
        scale.add_mark(60, Gtk.PositionType.BOTTOM, "window")

        def on_fov(s):
            self.cfg.fov_deg = round(s.get_value())
            self._changed()
        scale.connect("value-changed", on_fov)
        fov_row.add_suffix(scale)
        view.add(fov_row)

        def on_tilt(v):
            self.cfg.tilt_deg = v
            self._changed()
        view.add(self._spin_row("Tilt", -90, 90, self.cfg.tilt_deg, on_tilt,
                                subtitle="Altitude at the centre of the screen"))
        page.add(view)

        chart = Adw.PreferencesGroup(title="Chart")
        for title, attr in (("Constellation lines", "show_constellation_lines"),
                            ("Constellation names", "show_constellation_names"),
                            ("Planet labels", "show_planet_labels"),
                            ("Horizon and compass", "show_horizon"),
                            ("Last-updated time", "show_timestamp")):
            chart.add(self._cfg_switch(title, attr))
        page.add(chart)
        return page

    def _location_page(self):
        page = Adw.PreferencesPage(title="Location", icon_name="find-location-symbolic")
        place = Adw.PreferencesGroup(title="Where you are",
                                     description="Used only on this computer. Nothing is looked up online.")
        self.lat_row = Adw.EntryRow(title="Latitude", show_apply_button=True)
        self.lon_row = Adw.EntryRow(title="Longitude", show_apply_button=True)
        for row, attr in ((self.lat_row, "latitude"), (self.lon_row, "longitude")):
            v = getattr(self.cfg, attr)
            row.set_text("" if v is None else f"{v:g}")
            row.connect("apply", self._on_coord_apply, attr)
            place.add(row)
        imp = Adw.ActionRow(title="Import from Stellarium",
                            subtitle="Copies Stellarium's last location — check it's yours")
        btn = Gtk.Button(label="Import", valign=Gtk.Align.CENTER)
        btn.set_sensitive(read_stellarium_location() is not None)
        btn.connect("clicked", self._on_import)
        imp.add_suffix(btn)
        place.add(imp)
        page.add(place)

        facing = Adw.PreferencesGroup(title="Monitor direction",
                                      description="Compass reading from behind the screen")

        def on_facing(v):
            self.cfg.facing_deg = v % 360
            self._refresh_true_facing()
            self._changed()
        facing.add(self._spin_row("Facing", 0, 359.9, self.cfg.facing_deg, on_facing, step=0.5))
        ref = Adw.ComboRow(title="Compass reference", model=Gtk.StringList.new(["Magnetic", "True north"]))
        ref.set_selected(0 if self.cfg.facing_reference == "magnetic" else 1)

        def on_ref(r, _p):
            self.cfg.facing_reference = "magnetic" if r.get_selected() == 0 else "true"
            self._refresh_true_facing()
            self._changed()
        ref.connect("notify::selected", on_ref)
        facing.add(ref)
        self.true_row = Adw.ActionRow(title="True facing")
        facing.add(self.true_row)
        page.add(facing)
        return page

    def _system_page(self):
        page = Adw.PreferencesPage(title="System", icon_name="emblem-system-symbolic")
        wall = Adw.PreferencesGroup(title="Wallpaper")
        live_row, self.live_sw = self._switch_row(
            "Live sky as wallpaper", self.cfg.live_wallpaper, self._on_live,
            subtitle="Updated every minute. The lock screen shows it too, blurred by GNOME")
        wall.add(live_row)
        auto_row, self.auto_sw = self._switch_row("Start with GNOME session", self.cfg.autostart, self._on_auto)
        self.auto_sw.set_sensitive(self.cfg.live_wallpaper)
        wall.add(auto_row)
        page.add(wall)

        explore = Adw.PreferencesGroup(title="Explore")
        open_row = Adw.ActionRow(title="Open in Stellarium",
                                 subtitle="Same direction and field of view · Super+Alt+S")
        btn = Gtk.Button(label="Open", valign=Gtk.Align.CENTER)
        btn.connect("clicked", self._on_open)
        open_row.add_suffix(btn)
        explore.add(open_row)
        page.add(explore)
        return page

    # ── handlers ───────────────────────────────────────────────────────────
    def _refresh_true_facing(self) -> None:
        if self.cfg.latitude is None or self.cfg.longitude is None:
            self.true_row.set_subtitle("Set your location first")
            return
        t = true_facing_deg(self.cfg, datetime.now(timezone.utc))
        self.true_row.set_subtitle(f"{t:.1f}°")

    def _on_coord_apply(self, row, attr: str) -> None:
        limit = 90 if attr == "latitude" else 180
        try:
            v = float(row.get_text())
            if not -limit <= v <= limit:
                raise ValueError
        except ValueError:
            self._toast(f"{attr.capitalize()} must be a number between −{limit} and {limit}")
            return
        setattr(self.cfg, attr, v)
        self._refresh_true_facing()
        self._changed()

    def _on_import(self, _btn) -> None:
        loc = read_stellarium_location()
        if loc is None:
            self._toast("Stellarium has no saved location")
            return
        self.cfg.latitude, self.cfg.longitude = loc
        self.lat_row.set_text(f"{loc[0]:g}")
        self.lon_row.set_text(f"{loc[1]:g}")
        self._refresh_true_facing()
        self._changed()

    def _on_live(self, on: bool) -> None:
        if on == self.cfg.live_wallpaper:
            return
        if on and (self.cfg.latitude is None or self.cfg.longitude is None):
            self._toast("Set your location first")
            self.live_sw.set_active(False)
            return
        save_config(self.cfg, cli.config_path())
        fn = cli.cmd_enable if on else cli.cmd_disable

        def done(code):
            self.cfg = load_config(cli.config_path())
            if code:
                self._toast(f"Couldn't turn the live wallpaper {'on' if on else 'off'} (code {code})")
            self.live_sw.set_active(self.cfg.live_wallpaper)
            self.auto_sw.set_active(self.cfg.autostart)
            self.auto_sw.set_sensitive(self.cfg.live_wallpaper)
        self._in_worker(lambda: fn(argparse.Namespace()), done)

    def _on_auto(self, on: bool) -> None:
        if on == self.cfg.autostart:
            return
        code = cli.cmd_autostart(argparse.Namespace(state="on" if on else "off"))
        self.cfg = load_config(cli.config_path())
        if code:
            self.auto_sw.set_active(self.cfg.autostart)

    def _on_open(self, _btn) -> None:
        save_config(self.cfg, cli.config_path())
        if cli.cmd_open(argparse.Namespace()) == 2:
            self._toast("Set your location first")


def run_settings() -> int:
    app = Adw.Application(application_id=APP_ID)
    app.connect("activate", lambda a: (a.get_active_window() or SettingsWindow(a)).present())
    return app.run([])
