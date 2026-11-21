#!/usr/bin/env bash
# Gets the latest version from GitHub and restarts the scoreboard if it changed.
# Runs daily from a timer; run it by hand with:  sudo ./deploy/pi/update.sh
set -uo pipefail
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
OWNER="$(stat -c %U "$APP_DIR")"
as_owner() { runuser -u "$OWNER" -- "$@"; }

before="$(as_owner git -C "$APP_DIR" rev-parse HEAD)"
if ! as_owner git -C "$APP_DIR" pull --ff-only --quiet; then
    echo "Couldn't update (no internet, or local changes on the Pi). Keeping the current version."
    exit 0
fi
after="$(as_owner git -C "$APP_DIR" rev-parse HEAD)"

if [ "$before" != "$after" ]; then
    echo "Updated $before -> $after; restarting the scoreboard."
    chmod +x "$APP_DIR/deploy/pi/"*.sh
    systemctl restart around-the-grounds.service around-the-grounds-kiosk.service
else
    echo "Already up to date."
fi
