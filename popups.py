"""Milestone pop-ups: which of today's milestones are new, so each pops up once.

The first time a milestone appears in the scores, its time is saved (in the
data folder, so a restart doesn't show it again). It's offered to the screen
for the next POPUP_MINUTES; the screen shows each one once.
"""

import json
import os
import threading
import time

import config

POPUP_MINUTES = 15
KEEP_DAYS = 3
_lock = threading.Lock()


def _file():
    return config.DATA_DIR / "popups.json"


def fresh(events, now=None):
    """The events first seen in the last POPUP_MINUTES (recording any new ones)."""
    now = now or time.time()
    with _lock:
        try:
            seen = json.loads(_file().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            seen = {}
        changed = False
        for event in events:
            if event["id"] not in seen:
                seen[event["id"]] = now
                changed = True
        old = [key for key, when in seen.items() if now - when > KEEP_DAYS * 86400]
        for key in old:
            del seen[key]
        if changed or old:
            config.DATA_DIR.mkdir(parents=True, exist_ok=True)
            temporary = _file().with_suffix(".tmp")
            temporary.write_text(json.dumps(seen), encoding="utf-8")
            os.replace(temporary, _file())
    return [event for event in events if now - seen[event["id"]] < POPUP_MINUTES * 60]
