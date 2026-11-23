"""Make an SD card ready for one club before it's posted (run on your laptop).

Write the master image to the card first (see deploy/image/README.md), then,
with the card still in the laptop:

    python tools/prepare_club_card.py --card E: --club "https://play.cricket.com.au/club/<name>/<id>"
        [--wifi-name "Club WiFi" --wifi-password "secret"] [--pin 123456] [--title "Around the Grounds"]

E: is the card's small "bootfs" drive. This finds the club on PlayCricket
(name, team names, logo), writes aroundthegrounds.json onto the card, makes a
setup PIN (random unless --pin is given), and saves a printable welcome sheet
to send with the box. On first start-up the box becomes that club, and joins
the club's Wi-Fi if it was given (the password is then wiped from the card).
"""

import argparse
import json
import secrets
import sys
from datetime import date
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FILE_NAME = "aroundthegrounds.json"


def card_folder(card):
    """The card's boot partition, checked: it has the Pi's config.txt."""
    folder = Path(card if card.endswith(("/", "\\")) or len(card) > 2 else card + "\\")
    if not (folder / "config.txt").exists() and not (folder / "cmdline.txt").exists():
        raise SystemExit(f"{folder} doesn't look like a Raspberry Pi card's bootfs drive (no config.txt).")
    return folder


def build(found, pin, wifi_name="", wifi_password="", title=""):
    from werkzeug.security import generate_password_hash

    data = {
        "club": {key: found[key] for key in ("club_id", "club_name", "team_prefix", "short_name", "logo_url")},
        "pin_hash": generate_password_hash(pin),
        "prepared": date.today().isoformat(),
    }
    if title:
        data["title"] = title
    if wifi_name:
        data["wifi"] = {"ssid": wifi_name, "password": wifi_password}
    return data


def welcome_sheet(found, pin, wifi_name):
    """A one-page welcome for the club, to print and send with the box."""
    wifi_steps = (
        f"<li>Turn on the TV, then plug the box into the TV (HDMI) and into power. It joins "
        f"<strong>{escape(wifi_name)}</strong> by itself; after about two minutes the scoreboard appears.</li>"
        if wifi_name else
        "<li>Turn on the TV, then plug the box into the TV (HDMI) and into power. After about two minutes the TV "
        "shows <strong>Connect me to Wi-Fi</strong>.</li><li>Scan code 1 on the TV with a phone camera, then code 2, "
        "and choose the club's Wi-Fi.</li>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Around the Grounds · {escape(found['club_name'])}</title>
<style>
body {{ font-family: "Segoe UI", Arial, sans-serif; max-width: 720px; margin: 40px auto; color: #1d2433; line-height: 1.5; }}
h1 {{ margin-bottom: 0; }} .club {{ color: #5b6477; margin-top: 4px; font-size: 1.2rem; }}
.pin {{ margin-left: 12px; font-size: 2.2rem; font-weight: 800; letter-spacing: 6px; border: 3px solid #1d2433; display: inline-block;
        padding: 6px 18px; border-radius: 10px; }}
li {{ margin-bottom: 8px; }} .note {{ color: #5b6477; font-size: 0.9rem; }}
@media print {{ body {{ margin: 10mm auto; }} }}
</style></head><body>
<h1>Around the Grounds</h1><p class="club">Set up for {escape(found['club_name'])}</p>
<h2>Getting started</h2><ol>{wifi_steps}
<li>Turn on <strong>Anynet+ / HDMI-CEC</strong> in the TV's settings to use the TV remote: arrows move between
pages, OK pauses.</li></ol>
<h2>Changing things</h2>
<p>On a phone on the same Wi-Fi, open <strong>http://aroundthegrounds.local:8080/setup</strong> (or scan the code
the TV shows) to change colours, the logo, sponsors and pages.</p>
<p>Your setup PIN: <span class="pin">{escape(pin)}</span></p>
<p class="note">Keep this PIN with the club's passwords. Scores come from PlayCricket; the box updates itself
overnight.</p>
</body></html>"""


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--card", required=True, help="the card's bootfs drive, e.g. E:")
    parser.add_argument("--club", required=True, help="link to the club's PlayCricket page (or its ID)")
    parser.add_argument("--wifi-name", default="")
    parser.add_argument("--wifi-password", default="")
    parser.add_argument("--pin", default="", help="4 to 8 digits (random if not given)")
    parser.add_argument("--title", default="", help="heading on the TV (default: Around the Grounds)")
    parser.add_argument("--sheet-folder", default=".", help="where to save the welcome sheet")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    import scores

    folder = card_folder(args.card)
    pin = args.pin or f"{secrets.randbelow(10 ** 6):06d}"
    if not (pin.isdigit() and 4 <= len(pin) <= 8):
        raise SystemExit("The PIN must be 4 to 8 digits.")
    try:
        found = scores.discover_club(scores.club_id_from(args.club))
    except ValueError as error:
        raise SystemExit(f"Couldn't find the club: {error}")
    print(f"Club:          {found['club_name']} ({found['teams']} teams in {found['season']})")
    print(f"On the TV as:  {found['short_name']}  (teams named '{found['team_prefix']} ...')")
    print(f"Wi-Fi:         {args.wifi_name or '(none: the club scans the QR codes on the TV)'}")

    data = build(found, pin, args.wifi_name, args.wifi_password, args.title)
    (folder / FILE_NAME).write_text(json.dumps(data, indent=1), encoding="utf-8")
    sheet = Path(args.sheet_folder) / f"Around the Grounds welcome - {found['club_name']}.html"
    sheet.write_text(welcome_sheet(found, pin, args.wifi_name), encoding="utf-8")
    print(f"\nCard ready: {folder / FILE_NAME}")
    print(f"Setup PIN:     {pin}")
    print(f"Welcome sheet: {sheet.resolve()}  (print it and send it with the box)")


if __name__ == "__main__":
    main()
