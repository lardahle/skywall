# Skywall — design

*2026-11-22 · status: draft for approval*

## Intent

A GNOME wallpaper that shows the patch of sky the monitor is physically facing, right now — "Sky Map, but for the desktop." It is drawn as a clean star chart (not a photoreal sky), and it is always night: stars and planets are visible at noon and the Earth is see-through, so what is below the horizon is shown too.

The wallpaper is the ambient layer. When something on it catches the user's interest, one action opens **Stellarium** aimed at exactly the same view, for zooming in and exploring. Skywall itself never tries to be an interactive planetarium.

Why: the user wants a desktop that quietly reflects where they actually are in space, with a path to dig deeper when curious. They tried Caelum (too weather/photoreal-focused, and it pegged Xorg at ~100% CPU by redrawing a full-screen Cairo window 10×/s) and Stellarium (loved it, but it's an app, not a wallpaper).

## Goals

- The wallpaper shows the real sky in the monitor's real facing direction, current to within a minute.
- Star-chart look: stars sized by brightness and tinted by real colour, constellation lines, constellation names, labelled planets, Moon (with phase) and Sun as labelled markers, a faint horizon line with compass labels so the see-through part reads clearly.
- **Configurable field of view** like a game FOV slider. The default is the "literal window": what a 34" ultrawide covers at arm's length (≈60° across).
- Near-zero cost: one render per minute, roughly a second of CPU, nothing running in between.
- A settings window with: location, facing direction, tilt, FOV slider, chart toggles (lines, names, planet labels, horizon/compass), **Live sky as wallpaper** on/off, **Start with GNOME session** on/off, and an **Open in Stellarium** button.
- **Open in Stellarium** from both the settings window and a global keyboard shortcut: launches Stellarium at the user's location, current time, facing the same direction, same FOV, ground/atmosphere/fog off, constellation lines and names on.

## Non-goals

- Weather, clouds, daytime sky colours, landscapes, twinkling, meteors.
- Zooming or clicking *inside* the wallpaper — that's what Stellarium is for.
- Deep-sky objects (nebulae, clusters) and the Milky Way in v1. Both could come later from real data.
- Multi-monitor layouts (there is one monitor today).
- Translations in v1. Strings go through gettext so a language setting can be added once there's a second language.
- Changing Stellarium itself. (A separate, optional idea: contribute "pause rendering when the window is hidden" upstream. Not part of this build.)

## Anti-goals (a failure even if it technically works)

- Anything that redraws continuously or keeps a process busy between renders. The Caelum experience is the thing to avoid.
- Fake sky: no randomly placed decorative stars or a painted-on Milky Way. Everything drawn is at its real position.
- Leaving the user's desktop in a broken state: turning the live wallpaper off restores the wallpaper they had before.
- Sending location anywhere. Everything is computed locally. The only network use is the one-time download of the star catalogue and ephemeris.

## Constraints (verified on this machine)

- Debian 12, **GNOME Shell 43.9 on X11**, libadwaita 1.2 (`gir1.2-adw-1`) installed.
- One monitor: DP-0, **3440×1440**, 797×334 mm (34" 21:9).
- System `/usr/bin/python3` is 3.11 and has PyGObject + pycairo. The user's default `python3` is pyenv 3.12 without them. Use a venv created from `/usr/bin/python3 --system-site-packages`.
- The wallpaper is set via `gsettings org.gnome.desktop.background picture-uri` (and `picture-uri-dark`). GNOME only reloads when the URI changes.
- Stellarium 26.3 is installed as the Flatpak `org.stellarium.Stellarium` (user install). Its user data dir is `~/.stellarium/` (scripts go in `~/.stellarium/scripts/`).
- The monitor faces **296° magnetic** (confirmed by the user: Pixel 9 compass, magnetic north), so ≈303–304° true. See "Facing" below.

## Approaches considered

1. **Render a still image once a minute and set it as the GNOME wallpaper — chosen.** The sky turns ¼° per minute, so a per-minute still is visually live. It's a real wallpaper (behind icons, in the overview, blurred on the lock screen), and costs about a second of CPU per minute.
2. **A live animated full-screen window (GPU).** Smooth, but it keeps the machine busy constantly for motion you can't see. A desktop-type window is also fragile on GNOME. This is the same shape as Caelum, rejected.
3. **Drive Stellarium headless to screenshot every minute.** Great fidelity for free, but it keeps a ~1.7 GB app resident all day and is hard to style as a sleek chart. Rejected. Stellarium is used for the interactive step instead.

## How it works

### Pieces

- **Renderer** (`skywall render`): reads the config, computes positions, draws a 3440×1440 PNG, and sets it as the wallpaper. Runs once and exits.
- **Scheduler**: a **systemd user timer** fires the renderer every minute (`OnCalendar=*:*:00`, `Persistent=false`). "Start with GNOME session" = timer enabled. "Live sky as wallpaper" off = timer stopped and the previous wallpaper restored. *(My call: a timer instead of a long-running daemon, so nothing sits in memory between renders.)*
- **Settings app** (`skywall settings`): a small GTK4 + libadwaita 1.2 window that edits the config and triggers an immediate re-render on change, so the user sees the effect. Ships a `.desktop` entry so it's in the app grid.
- **Stellarium launcher** (`skywall open`): writes a startup script and launches Stellarium (details below).
- **Config**: `~/.config/skywall/config.toml`. **Data/cache**: `~/.local/share/skywall/`. **Rendered images**: `~/.local/share/skywall/wallpaper/`.

### Astronomy (my calls)

- **Skyfield** for all positions: proper motion, precession, nutation, aberration; refraction off (the Earth is see-through, so refraction is meaningless).
- **Stars**: the Hipparcos catalogue via Skyfield (`hip_main.dat`), filtered to magnitude ≤ 6.5 (~9,000 stars, roughly what the naked eye sees on a perfect night). Cached as a compact file after first download so each render loads fast.
- **Planets, Moon, Sun**: JPL ephemeris `de421.bsp` (valid through 2053), downloaded once.
- **Constellation lines and names**: Stellarium's *modern* sky culture data (lines are pairs of Hipparcos numbers, so they join the same catalogue). This also keeps the wallpaper and the Stellarium view consistent. GPL-2.0 data, which is fine for a personal / GPL project.

### Facing, tilt, projection

- **Facing**: the config stores the user's compass reading and whether it's magnetic or true. If magnetic, Skywall corrects it to true north using the World Magnetic Model for the configured location (a WMM library, e.g. `pygeomag`). At the user's location magnetic declination is roughly +7–8° east, so **296° magnetic ≈ 303–304° true**, a difference of about one constellation width. Settings shows both values.
- **Tilt**: the altitude at the centre of the screen. Default **0°** (the monitor is upright at eye level), so the horizon runs through the middle of the screen and the lower half is see-through sky. Range −90…+90.
- **FOV**: horizontal degrees across the 3440 px width; vertical follows from the aspect ratio. Default **60°** (2·atan(39.85 cm / 70 cm) ≈ 59°). Slider range 20°–180°.
- **Projection**: **stereographic**, centred on (facing, tilt). It keeps constellation shapes undistorted even at wide FOVs on an ultrawide. *(My call; gnomonic/perspective is the alternative and could be a setting later.)*

### Look (from the chosen "star chart" mockup)

- Background: near-black navy. Below-horizon sky gets a very slight tint so the see-through part is distinguishable without hiding stars.
- Stars: radius by magnitude, colour from B−V, soft anti-aliased edges.
- Constellation lines: thin, muted blue, partly transparent. Constellation names: small spaced caps near the figure's centre.
- Planets: slightly larger dots in their colours, each with a label. Moon drawn with its correct phase. Sun drawn as a labelled marker (no glare).
- Horizon: a faint dashed line labelled with compass points / azimuth ticks.
- No on-screen clock, data cards, or UI chrome. A small, unobtrusive "updated hh:mm" text in a corner is optional (default off).
- Exact colours, sizes, fonts and label-collision handling are left to the builder. Aim for "sleek", and check against a real render at 3440×1440 before calling it done.

### Updating the wallpaper

- Render to alternating files (`sky-a.png` / `sky-b.png`) and point `picture-uri` and `picture-uri-dark` at the new one, so GNOME notices the change without flicker. Set `picture-options` to `zoom`.
- On first enable, save the user's current wallpaper URIs and options in the config. Restore them when the live wallpaper is turned off.
- The render must finish well under a second of wall time in the steady state (data loaded from cache). Measure it.

### Open in Stellarium

- Write `~/.stellarium/scripts/skywall.ssc` with: observer location; time = now at normal rate; landscape, atmosphere and fog off; constellation lines and names on; view moved to the same azimuth (true) and tilt; FOV matched to Skywall's (Stellarium's FOV is measured differently: convert so the visible area matches).
- Launch `flatpak run org.stellarium.Stellarium --startup-script skywall.ssc`. If Stellarium is already running, re-aim the existing window instead, using its Remote Control plugin if it's enabled; otherwise just launch.
- Triggers: the **Open in Stellarium** button in settings, a `.desktop` action, and a **GNOME custom keyboard shortcut — default `Super+Alt+S`** *(my call; changeable in GNOME's keyboard settings)*.

### Location

- Settings take latitude/longitude typed in, with an **Import from Stellarium** button that reads Stellarium's configured location. Nothing is looked up online.

## Left to the builder

- Project layout, packaging (a `pip install -e` into the venv plus installing the systemd units and `.desktop` files is enough), and testing approach.
- Exact visual styling within the "Look" section, and label collision avoidance.
- How the catalogue cache is stored.
- Error handling when the data download fails (keep the last good wallpaper and log).

## Optional, separate: Stellarium tweaks

Not part of this build, just noted. With Stellarium closed, setting `minimum_fps = 1` in `~/.stellarium/config.ini` makes it nearly idle when you're not interacting with it (`maximum_fps = 60` caps it while you are).
