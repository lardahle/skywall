#!/usr/bin/env bash
# Install Skywall for the current user: venv, systemd units, app entry, Super+Alt+S shortcut.
set -euo pipefail
cd "$(dirname "$0")"
[ -d .venv ] || /usr/bin/python3 -m venv --system-site-packages .venv
.venv/bin/pip install -q -e .
.venv/bin/skywall install
echo "Installed. Open 'Skywall' from the app grid to set your location and turn on the live wallpaper."
