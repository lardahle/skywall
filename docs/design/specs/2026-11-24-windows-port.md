# Skywall on Windows — design notes

2026-11-24. Port of Skywall v0.1 (GNOME-only) to Windows 10/11. Branch `windows-support`.

## Goal

The same behaviour on Windows as on GNOME: a star-chart wallpaper of the sky the monitor faces, refreshed every minute, with your previous wallpaper restored when it's turned off, and a one-key hand-off to Stellarium. The GNOME code path stays exactly as it was.

## Shape

Rendering (`sky`, `projection`, `render`, `catalog`, `geomag`) was already platform-neutral (Skyfield, NumPy, pycairo). Only the desktop integration was GNOME-specific, so the port adds one module, `skywall/windows.py`, with the Windows versions of those jobs. `cli.py` picks the version at runtime:

- `cli.IS_WINDOWS` (from `sys.platform`) chooses between `wallpaper`/`scheduler` and `windows` via `_wallpaper()` and `_scheduler()`. The function signatures match, including the unused `runner` argument, so the command flow (`enable`, `disable`, `render`) is shared code.
- `cmd_install`, `cmd_settings` and the new `cmd_hotkey` have explicit Windows branches. `cmd_settings` opens `settings_win.py`, a Tkinter copy of the GTK window (`settings_app.py`): the same tabs and fields, saving as you go, a debounced re-render, and the CLI-owned fields protected by `merge_owned`.

## Decisions

| Concern | GNOME | Windows | Why |
| --- | --- | --- | --- |
| Wallpaper | `gsettings` | `SystemParametersInfoW(SPI_SETDESKWALLPAPER)`; `WallpaperStyle=10` (Fill), `TileWallpaper=0` | The documented API; it broadcasts the change. The saved state is `{path, style, tile}`, kept in the existing `saved_wallpaper` table. |
| Alternating files | `sky-a.png` / `sky-b.png` | same | Windows also caches by path. A new path forces a refresh. |
| Every minute | systemd user timer | Task Scheduler task from XML | XML is the only way `schtasks` can set: run on battery (laptops), `IgnoreNew` overlaps, hidden, 5-minute limit, `InteractiveToken` (the wallpaper needs the user's session). `pythonw.exe` avoids a console flash. |
| Start at login | `systemctl --user enable` | not needed | An enabled task survives sign-out and reboot. `set_autostart` is a no-op. |
| Render lock | `fcntl.flock` | `msvcrt.locking` on byte 0, polled for blocking mode | The same lock file and semantics. Non-blocking mode raises `BlockingIOError` on both. |
| Hotkey | GNOME custom keybinding | `skywall hotkey`: `RegisterHotKey(MOD_WIN\|MOD_ALT, 'S')` message loop, started from the Startup folder | `.lnk` hotkeys can't use the Windows key and only register after Explorer rescans. A second listener fails `RegisterHotKey` and exits, so it is single-instance for free. |
| Right-click | GNOME Shell extension | `HKCU\Software\Classes\DesktopBackground\Shell\Skywall` | A cascading *Skywall* verb (`MUIVerb` + `SubCommands` with `shell\` children) holding *Open sky in Stellarium* and *Settings*. Per-user, no admin. On Windows 11 it appears under *Show more options*. The compact menu needs a signed sparse package with an `IExplorerCommand` handler, which isn't worth it for two items. |
| Timestamp | bottom-right, margin only | bottom-right of the work area (`SPI_GETWORKAREA` vs. screen size, as fractions) | The old fixed 20 px offset sat under the taskbar. Fractions work at any DPI scaling, on any taskbar edge, and with auto-hide. The spot is reserved before star labels are placed and drawn last, so it is never displaced or painted over. Size scales with height (H/90). It reads as local date and time ("24 Nov 2026 · 12:47"), so screenshots are self-dating, on a sky-coloured backing so lines never cross it. |
| App entry | `.desktop` file | Start-menu `.lnk` files via `WScript.Shell` | No extra dependencies. |
| Settings UI | GTK 4 / libadwaita | Tkinter + sv-ttk (Sun Valley theme), DPI-aware | Tk ships with python.org Python. GTK on Windows means MSYS2. sv-ttk is about 200 KB of pure Python and Tcl and matches Windows 11. |
| Light / dark | Follows the desktop (libadwaita default) | `sv_ttk.set_theme` + `DwmSetWindowAttribute(DWMWA_USE_IMMERSIVE_DARK_MODE)` | An `appearance` setting (`system`/`light`/`dark`) in `config.toml`. *System* reads `AppsUseLightTheme`. The GNOME window can pick up the same setting separately (branch `gnome-appearance`). |
| Paths | XDG | `%APPDATA%\skywall` (config, roams), `%LOCALAPPDATA%\skywall` (about 50 MB of data, doesn't roam) | Platform conventions. |
| Constellation lines | Flatpak Stellarium | Program Files or `%LOCALAPPDATA%\Programs\Stellarium`; otherwise download `skycultures/modern/index.json` from Stellarium `v25.3` | The download fallback also removes the hard Stellarium dependency on Linux. The release is pinned so the format can't drift. |
| Stellarium launch | `flatpak run … --startup-script` | `stellarium.exe --startup-script`; user data in `%APPDATA%\Stellarium` | The same script and Remote Control re-aim path. `notify-send` is replaced by a message box. |

## Testing

- The existing tests describe the GNOME backend. An autouse fixture in `conftest.py` pins `cli.IS_WINDOWS = False` unless a test is marked `windows`, so the GNOME tests run on any OS.
- `tests/test_windows.py` covers the task XML (repetition, battery, instance policy, logon type, command), enable/disable round-tripping the wallpaper with the Win32 calls stubbed, and `msvcrt` lock exclusivity (on Windows only).
- Checked by hand on Windows 11 with Python 3.14 on a 4K panel at 150%:
  - a 3840×2160 render takes about 0.7 s from start to finish, including Python start-up, once the data is cached;
  - the task's first run returned 0 and switched the wallpaper;
  - <kbd>Win</kbd>+<kbd>Alt</kbd>+<kbd>S</kbd> opens Stellarium.
- Virtual desktops (Windows 11): checked with *Last-updated time*. The desktop you're on refreshes every minute, because `SPI_SETDESKWALLPAPER` applies to the active desktop. Desktops you aren't viewing may hold an older image until you switch to them; that's acceptable, since only the visible one matters.
- `disable` restoring the previous wallpaper is covered only by the stubbed test so far.

## Open

- Confirm the GNOME path still works on the Debian 12 machine before merging.
- *Match Windows* is read when the window opens. Live switching on a system theme change (`WM_SETTINGCHANGE`) isn't wired up.
- Per-monitor wallpapers through `IDesktopWallpaper`. Multi-monitor is out of scope for v0.1 on both platforms.
