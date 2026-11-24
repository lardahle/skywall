"""Settings window for Windows (Tkinter — ships with python.org Python). Mirrors settings_app.py (GTK)."""

import argparse
import queue
import sys
import threading
import tkinter as tk
from datetime import datetime, timezone
from tkinter import ttk

from . import cli
from .config import load_config, merge_owned, save_config
from .geomag import true_facing_deg
from .stellarium import read_stellarium_location

RERENDER_DELAY_MS = 500
PAD = {"padx": 12, "pady": 4}
CHART_TOGGLES = (("Constellation lines", "show_constellation_lines"),
                 ("Constellation names", "show_constellation_names"),
                 ("Star names", "show_star_names"),
                 ("Greek-letter labels", "show_star_designations"),
                 ("Planet labels", "show_planet_labels"),
                 ("Horizon and compass", "show_horizon"),
                 ("Last-updated time", "show_timestamp"))


def fmt_coord(v: float | None) -> str:
    return "" if v is None else f"{v:.6f}".rstrip("0").rstrip(".")


HINT = {"dark": "#a0a0a0", "light": "#5f5f5f"}
APPEARANCE_LABELS = {"system": "Match Windows", "light": "Light", "dark": "Dark"}


def system_prefers_dark() -> bool:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def resolve_mode(appearance: str) -> str:
    if appearance in ("light", "dark"):
        return appearance
    return "dark" if system_prefers_dark() else "light"


def apply_theme(root: tk.Tk, appearance: str) -> None:
    """Sun Valley (Windows 11-style) ttk theme in light or dark, plus a matching title bar."""
    mode = resolve_mode(appearance)
    try:
        import sv_ttk
        sv_ttk.set_theme(mode, root)
    except ImportError:  # still usable on the stock theme
        pass
    ttk.Style(root).configure("Hint.TLabel", foreground=HINT[mode])
    try:
        import ctypes
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        dark = ctypes.c_int(mode == "dark")
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (19 on Windows 10 before 20H1)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(dark), ctypes.sizeof(dark)) == 0:
                break
        # Repaint the frame now, not on the next activation.
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020)
    except (AttributeError, OSError):
        pass


def _dpi_aware() -> None:
    """Crisp text on scaled displays, and real pixel sizes from GetSystemMetrics."""
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def physical_screen_size() -> tuple[int, int]:
    import ctypes
    m = ctypes.windll.user32.GetSystemMetrics
    return m(0), m(1)


class SettingsWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.cfg = load_config(cli.config_path())
        self._pending = None
        self._results: queue.Queue = queue.Queue()
        root.title("Skywall")
        apply_theme(root, self.cfg.appearance)
        root.minsize(520, 0)

        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        nb.add(self._sky_tab(nb), text="Sky")
        self._loc = self._location_tab(nb)
        nb.add(self._loc, text="Location")
        nb.add(self._system_tab(nb), text="System")

        self.status = tk.StringVar()
        ttk.Label(root, textvariable=self.status, style="Hint.TLabel").pack(fill="x", padx=12, pady=8)
        self._refresh_true_facing()
        if self.cfg.latitude is None or self.cfg.longitude is None:
            nb.select(self._loc)
            self._toast("Welcome! Set your location and which way your monitor faces")
        root.after(100, self._poll)

    # ── helpers ────────────────────────────────────────────────────────────
    def _toast(self, text: str) -> None:
        self.status.set(text)
        self.root.after(5000, lambda: self.status.get() == text and self.status.set(""))

    def _save(self) -> None:
        """Save the window's fields without clobbering what the CLI owns (live, saved wallpaper)."""
        self.cfg = merge_owned(load_config(cli.config_path()), self.cfg)
        save_config(self.cfg, cli.config_path())

    def _changed(self) -> None:
        self._save()
        if self.cfg.live_wallpaper:
            if self._pending:
                self.root.after_cancel(self._pending)
            self._pending = self.root.after(RERENDER_DELAY_MS, self._rerender)

    def _in_worker(self, fn, done=None) -> None:
        def work():
            try:
                code = fn()
            except Exception as e:  # never leave the UI waiting on a dead thread
                print(f"skywall: {e}", file=sys.stderr)
                code = 1
            self._results.put((done, code))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self) -> None:  # Tk isn't thread-safe: run worker callbacks on the UI thread
        while not self._results.empty():
            done, code = self._results.get()
            if done:
                done(code)
        self.root.after(100, self._poll)

    def _rerender(self) -> None:
        self._pending = None
        self._toast("Updating wallpaper…")
        self._in_worker(lambda: cli.cmd_render(argparse.Namespace(output=None)),
                        lambda code: self._toast(f"Render failed (code {code})" if code else "Wallpaper updated"))

    def _check(self, parent, text: str, attr: str) -> ttk.Checkbutton:
        var = tk.BooleanVar(value=getattr(self.cfg, attr))

        def on():
            setattr(self.cfg, attr, var.get())
            self._changed()
        return ttk.Checkbutton(parent, text=text, variable=var, command=on)

    def _spin(self, parent, lo, hi, value, on_set, step=1.0, fmt="%.1f", width=8) -> ttk.Spinbox:
        var = tk.StringVar(value=fmt % value)
        spin = ttk.Spinbox(parent, from_=lo, to=hi, increment=step, textvariable=var, width=width, format=fmt)

        def commit(*_):
            try:
                v = float(var.get())
            except ValueError:
                return
            on_set(min(hi, max(lo, v)))
        spin.configure(command=commit)
        spin.bind("<Return>", commit)
        spin.bind("<FocusOut>", commit)
        return spin

    @staticmethod
    def _group(parent, title: str) -> ttk.LabelFrame:
        g = ttk.LabelFrame(parent, text=title, padding=8)
        g.pack(fill="x", padx=8, pady=6)
        g.columnconfigure(1, weight=1)
        return g

    @staticmethod
    def _row(group, r: int, label: str, widget, hint: str = "") -> None:
        ttk.Label(group, text=label).grid(row=r, column=0, sticky="w", **PAD)
        widget.grid(row=r, column=1, sticky="w", **PAD)
        if hint:
            ttk.Label(group, text=hint, style="Hint.TLabel").grid(row=r, column=2, sticky="w", **PAD)

    # ── tabs ───────────────────────────────────────────────────────────────
    def _sky_tab(self, nb) -> ttk.Frame:
        tab = ttk.Frame(nb)
        view = self._group(tab, "View")

        fov_val = tk.StringVar(value=f"{self.cfg.fov_deg:.0f}°")
        fov = ttk.Scale(view, from_=20, to=180, value=self.cfg.fov_deg, length=240)

        def on_fov_move(v):
            fov_val.set(f"{float(v):.0f}°")

        def on_fov_release(_e):
            self.cfg.fov_deg = round(fov.get())
            self._changed()
        fov.configure(command=on_fov_move)
        fov.bind("<ButtonRelease-1>", on_fov_release)
        fov.bind("<KeyRelease>", on_fov_release)
        self._row(view, 0, "Field of view", fov)
        ttk.Label(view, textvariable=fov_val, width=5).grid(row=0, column=2, sticky="w", **PAD)

        proj = ttk.Combobox(view, state="readonly", values=["Perspective", "Stereographic"], width=14)
        proj.current(0 if self.cfg.projection == "perspective" else 1)

        def on_proj(_e):
            self.cfg.projection = "perspective" if proj.current() == 0 else "stereographic"
            self._changed()
        proj.bind("<<ComboboxSelected>>", on_proj)
        self._row(view, 1, "Projection", proj, "Perspective is a true window")

        def on_tilt(v):
            self.cfg.tilt_deg = v
            self._changed()
        self._row(view, 2, "Tilt", self._spin(view, -90, 90, self.cfg.tilt_deg, on_tilt, 0.5),
                  "Altitude at the screen centre, °")

        def on_mag(v):
            self.cfg.mag_limit = v
            self._changed()
        self._row(view, 3, "Faintest stars", self._spin(view, 2, 8, self.cfg.mag_limit, on_mag, 0.5),
                  "Magnitude limit")

        chart = self._group(tab, "Chart")
        for i, (text, attr) in enumerate(CHART_TOGGLES):
            self._check(chart, text, attr).grid(row=i // 2, column=i % 2, sticky="w", **PAD)
        return tab

    def _location_tab(self, nb) -> ttk.Frame:
        tab = ttk.Frame(nb)
        place = self._group(tab, "Where you are")
        ttk.Label(place, text="Used only on this computer. Nothing is looked up online.",
                  style="Hint.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", **PAD)
        self._coord_vars = {}
        for r, (label, attr, hint) in enumerate((("Latitude", "latitude", "°, north positive"),
                                                 ("Longitude", "longitude", "°, east positive (west is −)")),
                                                start=1):
            v = getattr(self.cfg, attr)
            var = tk.StringVar(value=fmt_coord(v))
            entry = ttk.Entry(place, textvariable=var, width=14)
            entry.bind("<Return>", lambda _e, a=attr, x=var: self._apply_coord(a, x))
            entry.bind("<FocusOut>", lambda _e, a=attr, x=var: self._apply_coord(a, x))
            self._coord_vars[attr] = var
            self._row(place, r, label, entry, hint)

        def on_elev(v):
            self.cfg.elevation_m = v
            self._changed()
        self._row(place, 3, "Elevation", self._spin(place, -500, 9000, self.cfg.elevation_m, on_elev, 10), "m")
        imp = ttk.Button(place, text="Import from Stellarium", command=self._on_import)
        if read_stellarium_location() is None:
            imp.state(["disabled"])
        imp.grid(row=4, column=1, sticky="w", **PAD)

        facing = self._group(tab, "Monitor direction")
        ttk.Label(facing, text="Compass reading from behind the screen.",
                  style="Hint.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", **PAD)

        def on_facing(v):
            self.cfg.facing_deg = v % 360
            self._refresh_true_facing()
            self._changed()
        self._row(facing, 1, "Facing", self._spin(facing, 0, 359.9, self.cfg.facing_deg, on_facing, 0.5), "°")
        ref = ttk.Combobox(facing, state="readonly", values=["Magnetic", "True north"], width=14)
        ref.current(0 if self.cfg.facing_reference == "magnetic" else 1)

        def on_ref(_e):
            self.cfg.facing_reference = "magnetic" if ref.current() == 0 else "true"
            self._refresh_true_facing()
            self._changed()
        ref.bind("<<ComboboxSelected>>", on_ref)
        self._row(facing, 2, "Compass reference", ref, "Match your compass app")
        self.true_facing = tk.StringVar()
        self._row(facing, 3, "True facing", ttk.Label(facing, textvariable=self.true_facing))
        return tab

    def _system_tab(self, nb) -> ttk.Frame:
        tab = ttk.Frame(nb)
        wall = self._group(tab, "Wallpaper")
        self.live = tk.BooleanVar(value=self.cfg.live_wallpaper)
        self.live_check = ttk.Checkbutton(wall, text="Live sky as wallpaper", variable=self.live,
                                          command=self._on_live)
        self.live_check.grid(row=0, column=0, columnspan=3, sticky="w", **PAD)
        ttk.Label(wall, text="Updated every minute. Turning it off restores your previous wallpaper.",
                  style="Hint.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", **PAD)

        size = ttk.Frame(wall)
        self.width_var = tk.StringVar(value=str(self.cfg.width))
        self.height_var = tk.StringVar(value=str(self.cfg.height))
        for col, var in ((0, self.width_var), (2, self.height_var)):
            e = ttk.Entry(size, textvariable=var, width=6)
            e.grid(row=0, column=col)
            e.bind("<Return>", self._apply_size)
            e.bind("<FocusOut>", self._apply_size)
        ttk.Label(size, text=" × ").grid(row=0, column=1)
        ttk.Button(size, text="Use this screen", command=self._detect_size).grid(row=0, column=3, padx=(8, 0))
        self._row(wall, 2, "Image size", size, "Physical pixels")

        explore = self._group(tab, "Explore")
        ttk.Button(explore, text="Open in Stellarium", command=self._on_open).grid(row=0, column=0, sticky="w", **PAD)
        ttk.Label(explore, text="Same direction and field of view · Win+Alt+S",
                  style="Hint.TLabel").grid(row=0, column=1, sticky="w", **PAD)
        look = self._group(tab, "Appearance")
        theme = ttk.Combobox(look, state="readonly", width=16, values=list(APPEARANCE_LABELS.values()))
        theme.current(list(APPEARANCE_LABELS).index(self.cfg.appearance))

        def on_theme(_e):
            self.cfg.appearance = list(APPEARANCE_LABELS)[theme.current()]
            self._save()  # no re-render: the wallpaper is always night
            apply_theme(self.root, self.cfg.appearance)
        theme.bind("<<ComboboxSelected>>", on_theme)
        self._row(look, 0, "Theme", theme, "Settings window only")

        ttk.Button(explore, text="Edit config file", command=self._on_edit_file).grid(row=1, column=0, sticky="w", **PAD)
        ttk.Label(explore, text=str(cli.config_path()), style="Hint.TLabel").grid(row=1, column=1, sticky="w", **PAD)
        return tab

    # ── handlers ───────────────────────────────────────────────────────────
    def _refresh_true_facing(self) -> None:
        if self.cfg.latitude is None or self.cfg.longitude is None:
            self.true_facing.set("Set your location first")
            return
        self.true_facing.set(f"{true_facing_deg(self.cfg, datetime.now(timezone.utc)):.1f}°")

    def _apply_coord(self, attr: str, var: tk.StringVar) -> None:
        text = var.get().strip()
        if text == fmt_coord(getattr(self.cfg, attr)):
            return  # unchanged
        limit = 90 if attr == "latitude" else 180
        try:
            v = float(text)
            if not -limit <= v <= limit:
                raise ValueError
        except ValueError:
            self._toast(f"{attr.capitalize()} must be a number between −{limit} and {limit}")
            return
        setattr(self.cfg, attr, v)
        self._refresh_true_facing()
        self._changed()

    def _on_import(self) -> None:
        loc = read_stellarium_location()
        if loc is None:
            self._toast("Stellarium has no saved location")
            return
        self.cfg.latitude, self.cfg.longitude = loc
        self._coord_vars["latitude"].set(fmt_coord(loc[0]))
        self._coord_vars["longitude"].set(fmt_coord(loc[1]))
        self._refresh_true_facing()
        self._changed()

    def _apply_size(self, _e=None) -> None:
        try:
            w, h = int(self.width_var.get()), int(self.height_var.get())
            if not (320 <= w <= 16384 and 240 <= h <= 16384):
                raise ValueError
        except ValueError:
            self._toast("Size must be whole pixels, e.g. 3840 × 2160")
            return
        if (w, h) != (self.cfg.width, self.cfg.height):
            self.cfg.width, self.cfg.height = w, h
            self._changed()

    def _detect_size(self) -> None:
        w, h = physical_screen_size()
        self.width_var.set(str(w))
        self.height_var.set(str(h))
        self._apply_size()

    def _on_live(self) -> None:
        on = self.live.get()
        if on == self.cfg.live_wallpaper:
            return
        if on and (self.cfg.latitude is None or self.cfg.longitude is None):
            self._toast("Set your location first")
            self.live.set(False)
            return
        if self._pending:
            self.root.after_cancel(self._pending)
            self._pending = None
        self._save()
        self.live_check.state(["disabled"])
        self._toast("Turning the live wallpaper " + ("on…" if on else "off…"))
        fn = cli.cmd_enable if on else cli.cmd_disable

        def done(code):
            self.live_check.state(["!disabled"])
            self.cfg = load_config(cli.config_path())
            self.live.set(self.cfg.live_wallpaper)
            self._toast(f"Couldn't turn the live wallpaper {'on' if on else 'off'} (code {code})" if code
                        else f"Live wallpaper {'on' if on else 'off'}")
        self._in_worker(lambda: fn(argparse.Namespace()), done)

    def _on_open(self) -> None:
        self._save()
        if cli.cmd_open(argparse.Namespace()) == 2:
            self._toast("Set your location first")

    def _on_edit_file(self) -> None:
        import subprocess
        self._save()
        subprocess.Popen(["notepad.exe", str(cli.config_path())])


def run_settings() -> int:
    import ctypes
    from .windows import APP_ICON, APP_ID
    _dpi_aware()
    try:  # its own taskbar button (and icon) instead of grouping under pythonw
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    try:
        root.iconbitmap(default=str(APP_ICON))
    except tk.TclError:
        pass
    SettingsWindow(root)
    root.mainloop()
    return 0
