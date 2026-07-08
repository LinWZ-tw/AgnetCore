#!/usr/bin/env bash
# ============================================================================
#  Translational Agent Framework -- one-click Web GUI launcher (macOS / Linux)
#
#  On macOS, double-click this file in Finder. On Linux, run it from your file
#  manager or with `./run_gui.command`. It starts the local web server and
#  opens the GUI in your default browser -- no terminal command to type.
#
#  First time only, if double-click is blocked, make it executable once:
#      chmod +x run_gui.command
#
#  Keep the Terminal window that appears open while you use the GUI; press
#  Ctrl+C (or close it) when you are finished.
# ============================================================================
set -e

# Run from the repo root (the folder this script lives in), regardless of the
# directory it was launched from.
cd "$(dirname "$0")"

# Prefer python3; fall back to python.
PY=python3
if ! command -v "$PY" >/dev/null 2>&1; then
    PY=python
fi
if ! command -v "$PY" >/dev/null 2>&1; then
    echo
    echo "[!] Python was not found on this machine."
    echo "    Install Python 3.10+ (https://www.python.org/downloads/ or your"
    echo "    package manager), then run this file again."
    echo
    read -r -p "Press Enter to close..." _
    exit 1
fi

echo
echo "Starting the Translational Agent Framework GUI..."
echo "A browser tab will open automatically at http://127.0.0.1:8000/"
echo "Keep this window open while you use the GUI; press Ctrl+C to stop."
echo

exec "$PY" server.py --open
