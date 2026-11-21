"""Settings, read from environment variables (on the Pi: settings.env).

Defaults are for Altona Roosters. Another club only needs its PlayCricket
organisation ID, name and short name.
"""

import os


def _number(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


CLUB_ID = os.environ.get("ATG_CLUB_ID", "c88df151-87d8-eb11-a7ad-2818780da0cc")
CLUB_NAME = os.environ.get("ATG_CLUB_NAME", "Altona Roosters")     # as PlayCricket names its teams
SHORT_NAME = os.environ.get("ATG_SHORT_NAME", "Roosters")          # shown on the scoreboard
TIMEZONE = os.environ.get("ATG_TIMEZONE", "Australia/Melbourne")

HOST = os.environ.get("ATG_HOST", "0.0.0.0")   # 0.0.0.0: phones on the same Wi-Fi can look too
PORT = _number("ATG_PORT", 8080)
REFRESH_SECONDS = _number("ATG_REFRESH_SECONDS", 60)   # how often the screen asks for new scores
PAGE_SECONDS = _number("ATG_PAGE_SECONDS", 20)         # time on each page when there's more than one
