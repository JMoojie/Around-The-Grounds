"""The PlayCricket (PlayHQ grassroots) public API: just the calls the scoreboard needs.

Responses are kept for ``max_age`` seconds so a refreshing screen doesn't
re-download everything each time.
"""

import copy
import threading
import time

import requests

API_BASE = "https://grassrootsapiproxy.cricket.com.au"
TIMEOUT = 30
DEFAULT_MAX_AGE = 600

_cache = {}
_cache_lock = threading.Lock()


def clear_cache():
    with _cache_lock:
        _cache.clear()


def _get_json(path, *, params=None, max_age=None):
    key = (path, tuple(sorted((params or {}).items())))
    limit = DEFAULT_MAX_AGE if max_age is None else max_age
    with _cache_lock:
        cached = _cache.get(key)
        if cached and time.monotonic() - cached[0] < limit:
            return copy.deepcopy(cached[1])
    response = requests.get(f"{API_BASE}/{path.lstrip('/')}", params=params, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()
    with _cache_lock:
        _cache[key] = (time.monotonic(), copy.deepcopy(data))
    return data


def fetch_organisation_seasons(club_id, *, max_age=None):
    return _get_json(f"fixturesladders/organisations/{club_id}/seasons",
                     params={"jsconfig": "eccn:true"}, max_age=max_age)


def fetch_organisation_teams(club_id, season_id, *, max_age=None):
    return _get_json(f"fixturesladders/organisations/{club_id}/teams",
                     params={"seasonId": season_id, "jsconfig": "eccn:true"}, max_age=max_age)


def fetch_grade_matches(grade_id, *, max_age=None):
    return _get_json(f"scores/grades/{grade_id}/matches", params={"jsconfig": "eccn:true"}, max_age=max_age)


def fetch_match_scorecard(match_id, *, max_age=None):
    return _get_json(f"scores/matches/{match_id}",
                     params={"responseModifier": "includeScorecard", "jsconfig": "eccn:true"},
                     max_age=max_age)
