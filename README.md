# Skywall

**Your desktop wallpaper is the sky behind your monitor, right now.**

Skywall draws a star chart of exactly the patch of sky your screen is facing — as if the monitor were a window and the Earth were see-through — and refreshes it every minute. Stars, planets, the Moon (with its phase), constellation lines, star names. When something catches your eye, right-click the desktop (or press <kbd>Super</kbd>/<kbd>Win</kbd>+<kbd>Alt</kbd>+<kbd>S</kbd>) and [Stellarium](https://stellarium.org) opens aimed at the very same view.

Runs on **Linux with GNOME** and on **Windows 10/11**.

![Skywall on a 3440×1440 ultrawide, facing north-west: Boötes with Arcturus setting, Canes Venatici and Coma Berenices](docs/screenshot.png)

Think [Sky Map](https://github.com/sky-map-team/stardroid), but for a desktop that doesn't move.

## What it does

- **Real positions, nothing decorative.** ~15,000 catalogued stars (to magnitude 7) at their computed positions, coloured by their real colour index; Sun, Moon and the eight planets from the JPL ephemeris.
- **A true window.** Perspective projection with a vertical image plane: the horizon is a straight line at your eye level and vertical lines stay vertical. A stereographic mode is there for very wide fields of view.
- **Always night, Earth see-through.** Stars are shown at noon and below the horizon too; the horizon is marked with a dashed line and compass ticks.
- **Labels like a planetarium.** Constellation lines and names, proper star names (Arcturus, Izar…), Greek-letter designations for unnamed bright stars (ζ Boo, κ² Boo…), planet labels — each toggleable.
- **Practically free to run.** A systemd user timer (Linux) or a hidden scheduled task (Windows) renders one PNG per minute and exits. Nothing runs in between, nothing animates.
- **Polite.** Turning it off restores the wallpaper you had before. Your location never leaves the machine.

## Requirements

| | Linux (GNOME) | Windows 10/11 |
| --- | --- | --- |
| Desktop | GNOME (tested on GNOME 43 / X11, Debian 12) | Windows 10 or 11 (tested on 11) |
| Python | System **Python ≥ 3.11 with PyGObject, pycairo, GTK 4 and libadwaita ≥ 1.2** — Debian/Ubuntu: `sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1` | **Python ≥ 3.11** from [python.org](https://www.python.org/downloads/windows/) (tested on 3.14); pycairo installs from a wheel |
| Stellarium | Recommended, as a Flatpak: `flatpak install flathub org.stellarium.Stellarium` | Recommended: `winget install Stellarium.Stellarium` |

Stellarium is used for the interactive view, and Skywall reads its constellation lines once from a local install. Without one, the same lines are downloaded once from a pinned Stellarium release.

Internet is needed on first run only, to download the star catalogue (~35 MB), the planetary ephemeris (~17 MB) and, if needed, the constellation lines.

## Install on Linux (GNOME)

```bash
git clone https://github.com/lardahle/skywall.git ~/skywall
cd ~/skywall && ./install.sh
```

This creates a virtualenv, installs the systemd user timer, adds **Skywall** to the app grid, binds <kbd>Super</kbd>+<kbd>Alt</kbd>+<kbd>S</kbd>, and installs the right-click menu extension. On X11, restart GNOME Shell once (<kbd>Alt</kbd>+<kbd>F2</kbd>, `r`, <kbd>Enter</kbd>) or log out and in so the extension loads.

Then open **Skywall** from the app grid:

1. **Location** — type your latitude/longitude (or import Stellarium's).
2. **Monitor direction** — see [Finding your monitor's direction](#finding-your-monitors-direction).
3. **System → Live sky as wallpaper** — on. Optionally *Start with GNOME session*.

## Install on Windows

In PowerShell:

```powershell
git clone https://github.com/lardahle/skywall.git; cd skywall
.\install.ps1
```

If PowerShell refuses to run the script, allow local scripts for your account once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

`install.ps1` creates a virtualenv and then:

- registers a hidden **Task Scheduler** task, `Skywall`, that re-renders every minute (left disabled until you turn the wallpaper on);
- adds **Skywall** and **Skywall - Open in Stellarium** to the Start menu;
- starts the <kbd>Win</kbd>+<kbd>Alt</kbd>+<kbd>S</kbd> listener and puts it in your Startup folder;
- adds **Open sky in Stellarium** to the desktop's right-click menu.

There is no settings window on Windows. Configure Skywall by editing its config file:

```powershell
.\.venv\Scripts\skywall settings     # opens %APPDATA%\skywall\config.toml in Notepad
```

Set at least these keys (the full list is in [Configuration](#configuration)), save, then turn it on:

```toml
latitude = 37.108333          # decimal degrees, north positive
longitude = -113.583611       # decimal degrees, east positive (west is negative)
elevation_m = 834.8
facing_deg = 289.0            # compass bearing the screen faces
facing_reference = "true"     # or "magnetic", to match your compass app
width = 3840                  # the panel's physical pixels, not the scaled size
height = 2160
```

```powershell
.\.venv\Scripts\skywall enable
```

The wallpaper changes straight away and then every minute. Changes to `config.toml` take effect at the next refresh.

**Size on scaled displays.** Windows reports scaled sizes in many places. A 4K panel at 150% shows as 2560×1440, but the wallpaper should be rendered at 3840×2160. *Settings → System → Display → Display resolution* shows the real size.

### Opening Stellarium on Windows

- <kbd>Win</kbd>+<kbd>Alt</kbd>+<kbd>S</kbd>. Shortcut files can't use the Windows key, so a tiny idle listener (`skywall hotkey`) holds this key. It starts at sign-in from the Startup folder.
- Start menu → **Skywall - Open in Stellarium**.
- Right-click the desktop → **Show more options** (or <kbd>Shift</kbd>+right-click) → **Open sky in Stellarium**. Windows 11's short menu only lists packaged apps, so the entry is in the full menu.

If Stellarium is already open, Skywall re-aims it through Stellarium's *Remote Control* plugin. Enable that plugin (Configuration → Plugins → Remote Control → *Load at startup*) for re-aiming to work.

### Windows Spotlight

If your wallpaper was Windows Spotlight, `skywall disable` brings back the last Spotlight image as a still picture. To get it rotating again, choose Spotlight in *Settings → Personalization → Background*.

### Uninstall on Windows

```powershell
.\.venv\Scripts\skywall disable                       # restores your previous wallpaper
schtasks /Delete /TN Skywall /F
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object CommandLine -like '*skywall.cli hotkey*' | ForEach-Object { Stop-Process -Id $_.ProcessId }
Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Skywall*.lnk", "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Skywall hotkey.lnk"
Remove-Item -Recurse HKCU:\Software\Classes\DesktopBackground\Shell\Skywall
Remove-Item -Recurse "$env:APPDATA\skywall", "$env:LOCALAPPDATA\skywall"   # config, data and images
```

## Finding your monitor's direction

Hold a phone flat against the back of the monitor and read its compass. That bearing is `facing_deg`. Most compass apps can show either true or magnetic north (the iPhone Compass uses true north by default). Set *Magnetic* or *True north* (`facing_reference`) to match. Magnetic readings are corrected with the World Magnetic Model, so either works as long as the setting matches the app.

### Making it a true window

For the literal view through your monitor, set the field of view and tilt from your seating position (*Sky* tab on Linux; `fov_deg` and `tilt_deg` on Windows):

- **FOV** = 2 · atan(½ · screen width ÷ eye distance). Example: an 80 cm-wide screen seen from 96.5 cm → 2 · atan(40 / 96.5) ≈ **45°**.
- **Tilt** = atan(height of the screen centre above your eye line ÷ eye distance). Example: eyes on the lower-third line of a 33.4 cm-tall screen → atan(5.57 / 96.5) ≈ **3.3°**, which puts the horizon on your eye line.

## Configuration

Every setting lives in `config.toml`. The Linux settings window edits it for you; on Windows, edit it directly.

| Key | Default | Meaning |
| --- | --- | --- |
| `latitude`, `longitude` | — | Decimal degrees; north and east positive. Required. |
| `elevation_m` | `0.0` | Height above sea level, metres. |
| `facing_deg` | `180.0` | Compass bearing the screen faces. |
| `facing_reference` | `"magnetic"` | `"magnetic"` or `"true"` — whichever your compass reading used. |
| `tilt_deg` | `0.0` | Upward tilt of the view centre (−90 to 90). |
| `fov_deg` | `60.0` | Horizontal field of view (20 to 180). |
| `projection` | `"perspective"` | `"perspective"` (true window) or `"stereographic"` (better past ~100°). |
| `width`, `height` | `3440`, `1440` | Rendered size in physical pixels. |
| `mag_limit` | `7.0` | Faintest star magnitude drawn. |
| `show_constellation_lines`, `show_constellation_names`, `show_star_names`, `show_star_designations`, `show_planet_labels`, `show_horizon`, `show_timestamp` | `true` (timestamp `false`) | Toggle each layer. |

Leave `live_wallpaper`, `autostart` and `saved_wallpaper` alone. The `enable`, `disable` and `autostart` commands manage them.

| | Linux | Windows |
| --- | --- | --- |
| Config | `~/.config/skywall/config.toml` | `%APPDATA%\skywall\config.toml` |
| Data and rendered images | `~/.local/share/skywall/` | `%LOCALAPPDATA%\skywall\` |

## Command line

On Windows, run these as `.\.venv\Scripts\skywall …`.

```
skywall render [--output FILE]   render now (sets the wallpaper only while live is on)
skywall enable | disable         turn the live wallpaper on / off (off restores your old one)
skywall autostart on|off         start with the GNOME session (Windows: no-op, the task already persists)
skywall open                     open Stellarium aimed at the same view
skywall settings                 settings window (Windows: opens config.toml in Notepad)
skywall install                  (re)install timer/task, app entries, shortcut and right-click entry
skywall hotkey                   (Windows) hold Win+Alt+S; started for you at sign-in
```

How the pieces map between platforms:

| Job | Linux (GNOME) | Windows |
| --- | --- | --- |
| Set and restore wallpaper | `gsettings` (`org.gnome.desktop.background`) | `SystemParametersInfoW` + `HKCU\Control Panel\Desktop` (Fill) |
| Refresh every minute | systemd user timer `skywall.timer` | Task Scheduler task `Skywall` (`pythonw`, hidden, runs on battery) |
| Start at login | `skywall autostart on` (enables the timer) | Automatic while enabled |
| Hotkey | GNOME custom keybinding <kbd>Super</kbd>+<kbd>Alt</kbd>+<kbd>S</kbd> | `skywall hotkey` listener, <kbd>Win</kbd>+<kbd>Alt</kbd>+<kbd>S</kbd> |
| Right-click entry | GNOME Shell extension `skywall@local` | `HKCU\Software\Classes\DesktopBackground\Shell\Skywall` |
| App entry | `skywall.desktop` in the app grid | Start-menu shortcuts |
| Settings | GTK 4 / libadwaita window | `config.toml` in Notepad |
| Stellarium | Flatpak `org.stellarium.Stellarium` | `stellarium.exe` (Program Files or `%LOCALAPPDATA%\Programs`) |

## Known limits

- The GNOME right-click extension targets **GNOME Shell 43–44** (legacy `imports`). GNOME 45+ needs a port to ES modules — contributions welcome.
- Windows has no settings window yet; settings are edited in `config.toml`.
- On Windows 11 the right-click entry is only in the full menu (*Show more options*).
- One monitor (on Windows, every monitor gets the same image); deep-sky objects and the Milky Way aren't drawn yet.
- If you have enabled *south-based azimuth* in Stellarium, the "open in Stellarium" view will point the wrong way.

## Development

```bash
.venv/bin/python -m pytest -q            # full suite (first run downloads test data to ~/.cache/skywall-test-data)
.venv/bin/python -m pytest -q -m "not network"
```

On Windows use `.\.venv\Scripts\python.exe -m pytest -q`. The suite runs on both platforms. Tests describe the GNOME backend unless marked `windows`. A `conftest.py` fixture pins the backend, so both sets run on either OS.

Design notes are in [`docs/design/`](docs/design), including the [Windows port](docs/design/specs/2026-11-24-windows-port.md).

## Sources and credits

Data and models Skywall computes from:

- **Star catalogue** — [HYG Database v4.1](https://github.com/astronexus/HYG-Database) by David Nash / astronexus, licensed [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Downloaded at first run (not redistributed here); positions, proper motions, magnitudes, colour indices, proper names and Bayer designations. HYG is in turn compiled from the ESA **Hipparcos** catalogue (Perryman et al. 1997, ESA SP-1200), the Yale Bright Star Catalog and the Gliese Catalog of Nearby Stars.
- **Constellation lines and names** — the *Modern* sky culture from [Stellarium](https://github.com/Stellarium/stellarium) (GPL-2.0-or-later), read from your local Stellarium installation or downloaded once from Stellarium's repository (release v25.3); figures follow the IAU constellations.
- **Sun, Moon and planet positions** — NASA/JPL planetary ephemeris **DE421** (Folkner et al. 2008, JPL IOM 343R-08-003), via [Skyfield](https://rhodesmill.org/skyfield/).
- **Magnetic declination** — the **World Magnetic Model 2025** (NOAA NCEI and the British Geological Survey), via [pygeomag](https://github.com/boxpet/pygeomag).

Software it builds on:

- [Skyfield](https://rhodesmill.org/skyfield/) by Brandon Rhodes (MIT) — astrometry, apparent positions, Moon phase.
- [NumPy](https://numpy.org) (BSD-3-Clause), [pycairo](https://pycairo.readthedocs.io) / [Cairo](https://cairographics.org) (LGPL-2.1 / MPL-1.1), [PyGObject](https://pygobject.gnome.org), GTK 4 and [libadwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/) (LGPL-2.1+), [pygeomag](https://github.com/boxpet/pygeomag) (MIT), [tomli-w](https://github.com/hukkin/tomli-w) (MIT).
- [Stellarium](https://stellarium.org) (GPL-2.0-or-later) — the interactive view, driven through its [scripting API](https://stellarium.org/doc/head/scripting.html).

Inspiration and prior art: [Sky Map](https://github.com/sky-map-team/stardroid) (the "hold your phone up to the sky" idea), [Stellarium](https://stellarium.org), and [Caelum](https://github.com/Juliowilly/caelum), a photoreal live-sky desktop widget for GNOME.

## License

Skywall's code is [MIT](LICENSE). Data it downloads or reads keeps its own license (see above) — notably the HYG catalogue is CC BY-SA 4.0 and Stellarium's sky-culture data is GPL-2.0-or-later.
