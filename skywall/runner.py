"""Default runner for external commands; tests pass a fake instead."""

import subprocess
from typing import Callable

Runner = Callable[[list[str]], str]


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
