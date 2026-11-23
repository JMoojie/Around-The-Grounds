"""Ready-for-a-club cards: settings written onto the SD card before it's posted.

tools/prepare_club_card.py writes ``aroundthegrounds.json`` onto the card's
boot partition (the drive Windows can open). On start-up the scoreboard reads
it once and becomes that club: name, team names, short name, logo and setup
PIN. Its Wi-Fi details are used by deploy/pi/provision_wifi.py (run as root
by the Wi-Fi watcher), which then deletes the password from the card.

    {"club": {"club_id": ..., "club_name": ..., "team_prefix": ..., "short_name": ...,
              "logo_url": ...},
     "pin_hash": "...", "title": "...",
     "wifi": {"ssid": ..., "password": ...}}
"""

import hashlib
import json
import threading
import time
import uuid
from pathlib import Path

import requests

import config

PATHS = (Path("/boot/firmware/aroundthegrounds.json"), Path("/boot/aroundthegrounds.json"))
LOGO_RETRY_SECONDS = 300


def find(paths=PATHS):
    for path in paths:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
        except (OSError, ValueError) as error:
            print(f"Couldn't read {path}: {error}")
    return None


def _fingerprint(data):
    """Which club settings were applied (Wi-Fi left out: its password is removed after use)."""
    kept = {key: value for key, value in data.items() if key != "wifi"}
    return hashlib.sha256(json.dumps(kept, sort_keys=True).encode()).hexdigest()[:16]


def apply(data):
    """Make this box the card's club, once per card. Returns True if anything changed."""
    if not data or not isinstance(data.get("club"), dict) or not data["club"].get("club_id"):
        return False
    fingerprint = _fingerprint(data)
    if config.get("provisioned") == fingerprint:
        return False
    club = data["club"]
    changes = {key: str(club.get(key) or "")[:80] for key in ("club_id", "club_name", "team_prefix", "short_name")}
    if data.get("title"):
        changes["title"] = str(data["title"])[:40]
    if data.get("pin_hash"):
        changes["pin_hash"] = str(data["pin_hash"])
    changes["logo_pending"] = str(club.get("logo_url") or "")
    config.save(provisioned=fingerprint, **changes)
    print(f"Set up for {changes['club_name'] or changes['club_id']} from the card.")
    return True


def fetch_pending_logo():
    """Download the club's logo (the first start-up may be before the Wi-Fi is up). True when done."""
    url = config.get("logo_pending")
    if not url:
        return True
    if not url.startswith("https://"):
        config.save(logo_pending="")
        return True
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
    except requests.RequestException:
        return False
    import sponsor_cards  # its image check

    kind = sponsor_cards.image_type(response.content)
    if not kind:
        config.save(logo_pending="")
        return True
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    name = f"logo-{uuid.uuid4().hex[:8]}.{kind}"
    (config.DATA_DIR / name).write_bytes(response.content)
    old = config.get("logo")
    config.save(logo=name, logo_pending="")
    if old and old != name:
        (config.DATA_DIR / old).unlink(missing_ok=True)
    return True


def start(paths=PATHS):
    """At start-up: apply the card's settings, and keep trying for the logo in the background."""
    apply(find(paths))
    if config.get("logo_pending"):
        def keep_trying():
            while not fetch_pending_logo():
                time.sleep(LOGO_RETRY_SECONDS)
        threading.Thread(target=keep_trying, daemon=True).start()
