"""Windows backend: the same jobs as wallpaper/scheduler/keybinding/extension, done the Windows way.

- wallpaper   SystemParametersInfoW + HKCU\\Control Panel\\Desktop (instead of gsettings)
- scheduler   a Task Scheduler task that runs every minute (instead of a systemd user timer)
- shortcut    Start-menu entries, plus a tiny Win+Alt+S listener started at sign-in
              (instead of a GNOME keybinding; .lnk hotkeys can't use the Windows key)
- right-click a desktop-background context-menu verb in HKCU (instead of a GNOME Shell extension)
"""

import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from .config import Config
from .runner import Runner, run

TASK_NAME = "Skywall"
APP_ICON = Path(__file__).resolve().parent.parent / "data" / "icons" / "skywall.ico"  # tools/make_icon.py
APP_ID = "Skywall.Settings"  # taskbar identity, so the window gets Skywall's icon, not Python's
DESKTOP_KEY = r"Control Panel\Desktop"
STYLE_FILL = "10"
SPI_SETDESKWALLPAPER = 0x0014
SPI_GETDESKWALLPAPER = 0x0073
SPIF_UPDATE_AND_BROADCAST = 0x01 | 0x02
CONTEXT_KEY = r"Software\Classes\DesktopBackground\Shell\Skywall"
START_MENU = Path(os.environ.get("APPDATA", Path.home())) / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def pythonw() -> str:
    """The windowless interpreter next to the running one (no console flash from the task)."""
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return str(w if w.exists() else exe)


def skywall_command(*args: str) -> list[str]:
    return [pythonw(), "-m", "skywall.cli", *args]


# --- wallpaper ---------------------------------------------------------------------------

def _get_wallpaper_path() -> str:
    import ctypes
    buf = ctypes.create_unicode_buffer(1024)
    ctypes.windll.user32.SystemParametersInfoW(SPI_GETDESKWALLPAPER, len(buf), buf, 0)
    return buf.value


def _apply_wallpaper(path: str, style: str, tile: str) -> None:
    import ctypes
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, DESKTOP_KEY, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "WallpaperStyle", 0, winreg.REG_SZ, style)
        winreg.SetValueEx(k, "TileWallpaper", 0, winreg.REG_SZ, tile)
    if not ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, str(path),
                                                       SPIF_UPDATE_AND_BROADCAST):
        raise OSError(ctypes.get_last_error(), f"could not set wallpaper to {path}")


def _read_desktop(name: str, default: str) -> str:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, DESKTOP_KEY) as k:
            return str(winreg.QueryValueEx(k, name)[0])
    except OSError:
        return default


def set_wallpaper(path: Path, runner: Runner = run) -> None:
    _apply_wallpaper(str(Path(path).resolve()), STYLE_FILL, "0")


def save_current(cfg: Config, out_dir: Path, runner: Runner = run) -> None:
    if cfg.saved_wallpaper:
        return
    current = _get_wallpaper_path()
    if current and Path(current).resolve().is_relative_to(Path(out_dir).resolve()):
        return  # already ours
    cfg.saved_wallpaper = {"path": current,
                           "style": _read_desktop("WallpaperStyle", STYLE_FILL),
                           "tile": _read_desktop("TileWallpaper", "0")}


def restore(cfg: Config, runner: Runner = run) -> None:
    if not cfg.saved_wallpaper:
        return
    saved = cfg.saved_wallpaper
    # An empty path means "no picture" (solid colour) — SPI accepts that as-is.
    _apply_wallpaper(saved.get("path", ""), saved.get("style", STYLE_FILL), saved.get("tile", "0"))
    cfg.saved_wallpaper = {}


def taskbar_insets() -> tuple[float, float, float, float]:
    """Fractions of the primary screen the taskbar covers (left, top, right, bottom).

    Work area vs. full screen, both in the same (possibly DPI-virtualised) units, so the
    ratio is right at any scaling, on any taskbar edge, and 0 when the taskbar auto-hides.
    """
    import ctypes
    from ctypes import wintypes
    try:
        work = wintypes.RECT()
        if not ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work), 0):  # SPI_GETWORKAREA
            return (0.0, 0.0, 0.0, 0.0)
        sw, sh = ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)
        if sw <= 0 or sh <= 0:
            return (0.0, 0.0, 0.0, 0.0)
        return (max(0, work.left) / sw, max(0, work.top) / sh,
                max(0, sw - work.right) / sw, max(0, sh - work.bottom) / sh)
    except (AttributeError, OSError):
        return (0.0, 0.0, 0.0, 0.0)


# --- scheduler ---------------------------------------------------------------------------

def task_xml(command: list[str], user: str, enabled: bool = False) -> str:
    exe, *args = command
    arguments = subprocess.list2cmdline(args)
    start = datetime.now().replace(second=0, microsecond=0).isoformat()
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Re-render the Skywall star-chart wallpaper every minute</Description>
  </RegistrationInfo>
  <Triggers>
    <TimeTrigger>
      <StartBoundary>{start}</StartBoundary>
      <Repetition>
        <Interval>PT1M</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{escape(user)}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>false</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>{str(enabled).lower()}</Enabled>
    <Hidden>true</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <ExecutionTimeLimit>PT5M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(exe)}</Command>
      <Arguments>{escape(arguments)}</Arguments>
    </Exec>
  </Actions>
</Task>
"""


def _current_user() -> str:
    domain, user = os.environ.get("USERDOMAIN", ""), os.environ.get("USERNAME", "")
    return f"{domain}\\{user}" if domain else user


def install_task(enabled: bool = False, runner: Runner = run) -> None:
    xml = task_xml(skywall_command("render"), _current_user(), enabled)
    fd, tmp = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    try:
        Path(tmp).write_text(xml, encoding="utf-16")
        runner(["schtasks", "/Create", "/TN", TASK_NAME, "/XML", tmp, "/F"])
    finally:
        os.unlink(tmp)


def start(runner: Runner = run) -> None:
    runner(["schtasks", "/Change", "/TN", TASK_NAME, "/ENABLE"])


def stop(runner: Runner = run) -> None:
    runner(["schtasks", "/Change", "/TN", TASK_NAME, "/DISABLE"])


def stop_service(runner: Runner = run) -> None:
    try:
        runner(["schtasks", "/End", "/TN", TASK_NAME])
    except subprocess.CalledProcessError:
        pass  # not running


def set_autostart(enabled: bool, runner: Runner = run) -> None:
    """No-op: an enabled scheduled task already survives sign-out and reboot."""


# --- Start menu, hotkey, desktop right-click ---------------------------------------------

def _shortcut(lnk: Path, command: list[str], description: str, hotkey: str = "") -> None:
    exe, *args = command
    ps = "; ".join([
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:SW_LNK)",
        "$s.TargetPath = $env:SW_EXE",
        "$s.Arguments = $env:SW_ARGS",
        "$s.Description = $env:SW_DESC",
        "$s.IconLocation = \"$env:SW_ICON,0\"",
        "if ($env:SW_HOTKEY) { $s.Hotkey = $env:SW_HOTKEY }",
        "$s.Save()",
    ])
    env = dict(os.environ, SW_LNK=str(lnk), SW_EXE=exe, SW_ARGS=subprocess.list2cmdline(args),
               SW_DESC=description, SW_HOTKEY=hotkey, SW_ICON=str(APP_ICON))
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                   check=True, capture_output=True, env=env)


def install_shortcuts(start_menu: Path = START_MENU) -> None:
    start_menu.mkdir(parents=True, exist_ok=True)
    _shortcut(start_menu / "Skywall.lnk", skywall_command("settings"), "Skywall settings")
    _shortcut(start_menu / "Skywall - Open in Stellarium.lnk", skywall_command("open"),
              "Open Stellarium aimed at the wallpaper's view")


CONTEXT_ITEMS = (("1open", "Open sky in Stellarium", "open"), ("2settings", "Settings", "settings"))


def _delete_tree(root, path: str) -> None:
    import winreg
    try:
        with winreg.OpenKey(root, path) as k:
            while True:
                try:
                    child = winreg.EnumKey(k, 0)
                except OSError:
                    break
                _delete_tree(root, f"{path}\\{child}")
        winreg.DeleteKey(root, path)
    except FileNotFoundError:
        pass


def install_context_menu() -> None:
    """Desktop right-click → Skywall ▸ Open sky in Stellarium / Settings (Windows 11: 'Show more options')."""
    import winreg
    hk = winreg.HKEY_CURRENT_USER
    _delete_tree(hk, CONTEXT_KEY)  # replaces older single-verb installs cleanly
    with winreg.CreateKey(hk, CONTEXT_KEY) as k:
        winreg.SetValueEx(k, "MUIVerb", 0, winreg.REG_SZ, "Skywall")
        winreg.SetValueEx(k, "SubCommands", 0, winreg.REG_SZ, "")  # cascade from the shell\ subkeys
        winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, f"{APP_ICON},0")
    for key, label, cmd in CONTEXT_ITEMS:  # subkey names sort the items
        with winreg.CreateKey(hk, rf"{CONTEXT_KEY}\shell\{key}") as k:
            winreg.SetValueEx(k, "MUIVerb", 0, winreg.REG_SZ, label)
        with winreg.CreateKey(hk, rf"{CONTEXT_KEY}\shell\{key}\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, subprocess.list2cmdline(skywall_command(cmd)))


STARTUP = START_MENU / "Startup"
HOTKEY_LNK = "Skywall hotkey.lnk"
MOD_ALT, MOD_WIN, MOD_NOREPEAT, VK_S, WM_HOTKEY = 0x0001, 0x0008, 0x4000, 0x53, 0x0312


def hotkey_loop(on_press) -> int:
    """Hold Win+Alt+S for this session and call `on_press` each time (the GNOME shortcut's twin).

    Returns 1 at once if the combination is taken, e.g. by an already-running listener.
    """
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    if not user32.RegisterHotKey(None, 1, MOD_WIN | MOD_ALT | MOD_NOREPEAT, VK_S):
        return 1
    msg = wintypes.MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                try:
                    on_press()
                except Exception as e:  # keep listening whatever one press does
                    print(f"skywall: {e}", file=sys.stderr)
    finally:
        user32.UnregisterHotKey(None, 1)
    return 0


def install_hotkey(startup: Path = STARTUP) -> None:
    """Start the Win+Alt+S listener now and at every sign-in."""
    startup.mkdir(parents=True, exist_ok=True)
    _shortcut(startup / HOTKEY_LNK, skywall_command("hotkey"), "Skywall: Win+Alt+S opens Stellarium")
    subprocess.Popen(skywall_command("hotkey"), creationflags=subprocess.DETACHED_PROCESS,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)


def notify(message: str) -> None:
    import ctypes
    ctypes.windll.user32.MessageBoxW(None, message, "Skywall", 0x40)
