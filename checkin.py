"""Box check-in: lets whoever supplies the box see that it's alive.

Every ATG_CHECKIN_MINUTES (default 15) the box sends a small "I'm here" to
ATG_CHECKIN_URL, with {box} replaced by this box's name, e.g.

    ATG_CHECKIN_URL=https://hc-ping.com/<your ping key>/{box}?create=1

(healthchecks.io: one entry per box, created on its first check-in, and an
email when a box goes quiet). What's sent: the club's name, the software
version, hours since the box started, and whether its scores are working.
Off when ATG_CHECKIN_URL isn't set.
"""

import json
import os
import re
import secrets
import subprocess
import threading
import time

import requests

import config

URL = os.environ.get("ATG_CHECKIN_URL", "").strip()
MINUTES = max(5, int(os.environ.get("ATG_CHECKIN_MINUTES", "15") or 15))
last_scores = {"status": "starting"}   # set by the server each time the screen gets new scores


def enabled():
    return bool(URL)


def _box_id():
    """A short id for this box, made once (a fresh one on every new card)."""
    path = config.DATA_DIR / "box_id"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        box = secrets.token_hex(3)
        path.write_text(box, encoding="utf-8")
        return box


def box_name():
    """e.g. 'roosters-3f9a1c': the club's short name (once set up) and the box's id."""
    club = config.get("short_name") or config.get("team_prefix") or "new-box"
    slug = re.sub(r"[^a-z0-9]+", "-", club.lower()).strip("-") or "box"
    return f"{slug}-{_box_id()}"


def _version():
    try:
        out = subprocess.run(["git", "-C", str(config.ROOT), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _uptime_hours():
    try:
        return round(float(open("/proc/uptime", encoding="ascii").read().split()[0]) / 3600, 1)
    except (OSError, ValueError, IndexError):
        return None


def report():
    return {"box": box_name(), "club": config.get("club_name") or "(not set up yet)", "version": _version(),
            "uptime_hours": _uptime_hours(), "scores": last_scores["status"]}


def check_in():
    """One check-in. True if it got through."""
    if not URL:
        return False
    try:
        response = requests.post(URL.replace("{box}", box_name()), data=json.dumps(report()),
                                 headers={"Content-Type": "application/json"}, timeout=20)
        return response.status_code < 400
    except requests.RequestException:
        return False


def start():
    if not URL:
        return

    def loop():
        time.sleep(60)  # let the Wi-Fi and the scoreboard settle first
        while True:
            check_in()
            time.sleep(MINUTES * 60)

    threading.Thread(target=loop, daemon=True).start()
