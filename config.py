"""Settings.

Everything a club changes (its PlayCricket club, name, colours, logo, timings,
sponsors, setup PIN) is saved by the setup page in ``data/settings.json``.
Environment variables (on the Pi: settings.env) give the starting values and
the web server's address. The data folder is never committed to git.
"""

import json
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("ATG_DATA_DIR", ROOT / "data"))
SETTINGS_FILE = DATA_DIR / "settings.json"
SPONSOR_DIR = DATA_DIR / "sponsors"


def _number(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


HOST = os.environ.get("ATG_HOST", "0.0.0.0")   # 0.0.0.0: phones on the same Wi-Fi can look too
PORT = _number("ATG_PORT", 8080)

DEFAULTS = {
    # The club (from its PlayCricket club page link; blank until set up).
    "club_id": os.environ.get("ATG_CLUB_ID", ""),
    "club_name": os.environ.get("ATG_CLUB_NAME", ""),         # e.g. "Altona Roosters Cricket Club"
    "team_prefix": os.environ.get("ATG_TEAM_PREFIX", ""),     # how PlayCricket starts team names
    "short_name": os.environ.get("ATG_SHORT_NAME", ""),       # on the scoreboard, e.g. "Roosters"
    "timezone": os.environ.get("ATG_TIMEZONE", "Australia/Melbourne"),
    # Look.
    "title": os.environ.get("ATG_TITLE", "Around the Grounds"),
    "accent": "#f2b632",
    "background": "#0b1424",
    "panel": "#13213a",
    "text": "#f4f6fb",
    "logo": "",                       # file name in the data folder
    # Pages.
    "refresh_seconds": _number("ATG_REFRESH_SECONDS", 60),
    "page_seconds": _number("ATG_PAGE_SECONDS", 20),
    "show_results": True,
    "show_leaders": True,
    "show_coming": True,
    "live_only": False,               # while games are being played, show only the live scores
    "show_extra": True,               # pages sent by another program (see extra_pages.py)
    "extra_key": "",                  # the key that program needs (made on the setup page)
    # Sponsors: [{"file": ..., "name": ...}], one shown after every N pages.
    "sponsors": [],
    "sponsor_every": 3,
    "sponsor_seconds": 10,
    # Setup page.
    "pin_hash": "",
}

_lock = threading.Lock()
_cache = {"mtime": None, "values": None}


def load():
    """The current settings (defaults, then whatever the setup page saved)."""
    with _lock:
        try:
            mtime = SETTINGS_FILE.stat().st_mtime
        except OSError:
            mtime = None
        if _cache["values"] is None or mtime != _cache["mtime"]:
            values = dict(DEFAULTS)
            if mtime is not None:
                try:
                    values.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
                except (OSError, ValueError):
                    pass  # a damaged file: carry on with the defaults
            _cache.update(mtime=mtime, values=values)
        return dict(_cache["values"])


def get(key):
    return load().get(key, DEFAULTS.get(key))


def save(**changes):
    """Save changed settings (written to a temporary file first, so a power cut can't corrupt them)."""
    unknown = set(changes) - set(DEFAULTS)
    if unknown:
        raise KeyError(f"Unknown settings: {', '.join(sorted(unknown))}")
    with _lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        saved = {}
        if SETTINGS_FILE.exists():
            try:
                saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            except ValueError:
                saved = {}
        saved.update(changes)
        temporary = SETTINGS_FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps(saved, indent=1), encoding="utf-8")
        os.replace(temporary, SETTINGS_FILE)
        _cache["values"] = None


def version():
    """Changes whenever settings are saved (the TV reloads itself when it does)."""
    try:
        return str(int(SETTINGS_FILE.stat().st_mtime * 1000))
    except OSError:
        return "0"


def is_set_up():
    return bool(get("club_id"))
