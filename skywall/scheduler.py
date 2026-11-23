"""systemd user timer that re-renders the wallpaper every minute."""

from pathlib import Path

from .runner import Runner, run

SERVICE_NAME = "skywall.service"
TIMER_NAME = "skywall.timer"
UNIT_DIR = Path.home() / ".config" / "systemd" / "user"


def unit_texts(exec_path: str) -> dict[str, str]:
    return {
        SERVICE_NAME: f"""[Unit]
Description=Render the Skywall star-chart wallpaper

[Service]
Type=oneshot
ExecStart={exec_path} render
Nice=10
""",
        TIMER_NAME: """[Unit]
Description=Re-render the Skywall wallpaper every minute

[Timer]
OnCalendar=*:*:00
AccuracySec=1s
Persistent=false

[Install]
WantedBy=timers.target
""",
    }


def install_units(unit_dir: Path, exec_path: str, runner: Runner = run) -> None:
    unit_dir = Path(unit_dir)
    unit_dir.mkdir(parents=True, exist_ok=True)
    for name, text in unit_texts(exec_path).items():
        (unit_dir / name).write_text(text)
    runner(["systemctl", "--user", "daemon-reload"])


def start(runner: Runner = run) -> None:
    runner(["systemctl", "--user", "start", TIMER_NAME])


def stop(runner: Runner = run) -> None:
    runner(["systemctl", "--user", "stop", TIMER_NAME])


def stop_service(runner: Runner = run) -> None:
    runner(["systemctl", "--user", "stop", SERVICE_NAME])


def set_autostart(enabled: bool, runner: Runner = run) -> None:
    runner(["systemctl", "--user", "enable" if enabled else "disable", TIMER_NAME])
