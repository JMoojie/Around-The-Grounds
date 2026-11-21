"""Extra pages: ready-made pages another program sends to the scoreboard.

A club's own stats system (for example the Altona Roosters Cricket Archive)
can POST pages to /api/pages with the box's extra pages key. They're shown in
the rotation after the season leaders, until replaced or removed. The pages
are saved in the data folder (never in git) and checked on the way in: no
scripts, sensible sizes.

The JSON sent:
    {"source": "Club archive", "published": "2026-11-22T10:00",
     "css": "optional extra rules",
     "pages": [{"title": "Career leaders", "html": "<section class='panel'>...</section>",
                "columns": 3, "screen": "leaders"}]}
"""

import json
import os
import re
import threading

import config

FILE = config.DATA_DIR / "extra_pages.json"
MAX_PAGES = 30
MAX_PAGE_HTML = 200_000
MAX_CSS = 20_000
UNSAFE = re.compile(r"<\s*/?\s*(script|iframe|object|embed|link|meta|base|form)\b|javascript:|<[^>]*\son[a-z]+\s*=",
                    re.I)
SCREEN = re.compile(r"^[a-z0-9-]{1,40}$")

_lock = threading.Lock()
_cache = {"mtime": None, "pack": None}


def clean(pack):
    """The pack, checked and trimmed to what the scoreboard uses. Raises ValueError."""
    if not isinstance(pack, dict) or not isinstance(pack.get("pages"), list):
        raise ValueError("Expected {\"pages\": [...]}.")
    if len(pack["pages"]) > MAX_PAGES:
        raise ValueError(f"At most {MAX_PAGES} pages.")
    pages = []
    for n, page in enumerate(pack["pages"], start=1):
        if not isinstance(page, dict):
            raise ValueError(f"Page {n} isn't an object.")
        title, html = str(page.get("title") or "").strip()[:120], str(page.get("html") or "")
        if not title or not html:
            raise ValueError(f"Page {n} needs a title and html.")
        if len(html) > MAX_PAGE_HTML:
            raise ValueError(f"Page {n} is too big.")
        if UNSAFE.search(html):
            raise ValueError(f"Page {n} contains scripts or other content the scoreboard won't show.")
        try:
            columns = min(max(int(page.get("columns") or 1), 1), 3)
        except (TypeError, ValueError):
            columns = 1
        screen = str(page.get("screen") or "")
        pages.append({"title": title, "html": html, "columns": columns,
                      "screen": screen if SCREEN.match(screen) else ""})
    css = str(pack.get("css") or "")
    if len(css) > MAX_CSS or "<" in css or "@import" in css.lower() or "url(" in css.lower():
        raise ValueError("The css isn't allowed (too long, or it loads other files).")
    return {"source": str(pack.get("source") or "")[:80], "published": str(pack.get("published") or "")[:40],
            "css": css, "pages": pages}


def save(pack):
    cleaned = clean(pack)
    with _lock:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        temporary = FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps(cleaned), encoding="utf-8")
        os.replace(temporary, FILE)
        _cache["pack"] = None
    return cleaned


def load():
    """The saved pack, or None."""
    with _lock:
        try:
            mtime = FILE.stat().st_mtime
        except OSError:
            return None
        if _cache["pack"] is None or _cache["mtime"] != mtime:
            try:
                _cache.update(pack=json.loads(FILE.read_text(encoding="utf-8")), mtime=mtime)
            except (OSError, ValueError):
                return None
        return _cache["pack"]


def clear():
    with _lock:
        FILE.unlink(missing_ok=True)
        _cache["pack"] = None
