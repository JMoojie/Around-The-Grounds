"""Around the Grounds web server.

    python server.py            # then open http://localhost:8080

/          the full-screen scoreboard (for the TV)
/board     the current pages as JSON (the scoreboard asks for this every minute)
/setup     the club's setup page (PIN protected)
/health    "ok" (the Pi's kiosk waits for this before opening the browser)
"""

import re
import secrets
import time
import uuid

import requests
from flask import Flask, abort, jsonify, make_response, redirect, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

import config
import extra_pages
import playcricket as pc
import scores
import screen
import setup_page
import sponsor_cards
import system

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024  # uploads: 6 MB is plenty for a logo or sponsor slide
MAX_SPONSORS = 20
COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")
SPONSOR_FILE = re.compile(r"^[0-9a-f]{32}\.(png|jpg|gif|webp|svg)$")
SPONSOR_ID = re.compile(r"^[0-9a-f]{32}")


def _secret_key():
    path = config.DATA_DIR / "secret.key"
    try:
        return path.read_bytes()
    except OSError:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        key = secrets.token_bytes(32)
        path.write_bytes(key)
        return key


app.secret_key = _secret_key()


def _no_store(response):
    response.headers["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------- the scoreboard

@app.get("/")
def scoreboard():
    return _no_store(make_response(screen.render_page()))


@app.get("/board")
def board():
    hotspot = system.hotspot()
    if hotspot:
        result = {"hotspot": hotspot, "checked": ""}   # no internet while the setup hotspot is on
    else:
        result = scores.live_board()
        if result.get("mode") == "setup":
            result["addresses"] = system.addresses()
    settings = config.load()
    playing = sum(1 for g in result.get("games") or [] if g["state"] == "live")
    return _no_store(jsonify({
        "html": screen.render_board(result),
        "checked": result.get("checked", ""),
        "error": result.get("error"),
        "playing": playing,
        "version": config.version(),
        "sponsors": [{"html": sponsor_cards.card_html(s, f"/media/sponsors/{s['file']}" if s.get("file") else "")}
                     for s in settings["sponsors"]],
        "sponsor_every": settings["sponsor_every"],
        "sponsor_seconds": settings["sponsor_seconds"],
    }))


@app.get("/health")
def health():
    return "ok"


def _extra_key_ok():
    key = config.get("extra_key")
    supplied = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    return bool(key) and secrets.compare_digest(supplied.encode(), key.encode())


@app.post("/api/pages")
def api_pages():
    """Extra pages from another program (needs the box's extra pages key)."""
    if not _extra_key_ok():
        time.sleep(1)
        return jsonify({"error": "Wrong or missing key."}), 401
    try:
        pack = extra_pages.save(request.get_json(silent=True))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({"ok": True, "pages": len(pack["pages"])})


@app.delete("/api/pages")
def api_pages_remove():
    if not _extra_key_ok():
        time.sleep(1)
        return jsonify({"error": "Wrong or missing key."}), 401
    extra_pages.clear()
    return jsonify({"ok": True})


@app.get("/media/logo")
def logo():
    name = config.get("logo")
    if not name:
        abort(404)
    return _image_response(send_from_directory(config.DATA_DIR, name, max_age=60))


@app.get("/media/sponsors/<name>")
def sponsor_image(name):
    if not SPONSOR_FILE.match(name):
        abort(404)
    return _image_response(send_from_directory(config.SPONSOR_DIR, name, max_age=3600))


def _image_response(response):
    # Logos can be SVG files from a sponsor's website: never let one run scripts.
    response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


# ---------------------------------------------------------------- the setup page

def _image_type(data):
    return sponsor_cards.image_type(data)


def _logged_in():
    return bool(session.get("setup")) and session.get("pin_version") == config.get("pin_hash")[-12:]


def _token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


def _done(message, kind="ok"):
    session["flash"] = (kind, message)
    return redirect("/setup")


def _guarded(view):
    """Setup actions: logged in, and the form came from our own setup page."""
    def wrapper(*args, **kwargs):
        if not _logged_in():
            return redirect("/setup")
        if request.form.get("csrf") != session.get("csrf"):
            return _done("That form had expired. Please try again.", "err")
        return view(*args, **kwargs)
    wrapper.__name__ = view.__name__
    return wrapper


@app.get("/setup")
def setup():
    settings = config.load()
    flash = session.pop("flash", None)
    if not settings["pin_hash"] or not _logged_in():
        page = setup_page.login_page(settings, first_time=not settings["pin_hash"], flash=flash)
    else:
        page = setup_page.setup_page(settings, _token(), session.get("found"), flash, session.get("sponsor_found"),
                                     editing_sponsor=request.args.get("sponsor", ""))
    return _no_store(make_response(page))


@app.post("/setup/login")
def setup_login():
    pin_hash = config.get("pin_hash")
    if pin_hash and check_password_hash(pin_hash, request.form.get("pin", "")):
        session.update(setup=True, pin_version=pin_hash[-12:])
        return redirect("/setup")
    time.sleep(1.5)  # slows down anyone guessing
    session["flash"] = ("err", "That PIN isn't right.")
    return redirect("/setup")


@app.post("/setup/logout")
@_guarded
def setup_logout():
    session.clear()
    return redirect("/setup")


@app.post("/setup/pin")
def setup_pin():
    first_time = not config.get("pin_hash")
    if not first_time and (not _logged_in() or request.form.get("csrf") != session.get("csrf")):
        return redirect("/setup")
    pin, again = request.form.get("pin", "").strip(), request.form.get("again", "").strip()
    if not (pin.isdigit() and 4 <= len(pin) <= 8):
        return _done("The PIN must be 4 to 8 digits.", "err")
    if pin != again:
        return _done("The two PINs didn't match.", "err")
    pin_hash = generate_password_hash(pin)
    config.save(pin_hash=pin_hash)
    session.update(setup=True, pin_version=pin_hash[-12:])
    return _done("PIN saved." + (" Now choose your club." if first_time else ""))


@app.post("/setup/club/find")
@_guarded
def setup_club_find():
    link = request.form.get("link", "")
    club_id = scores.club_id_from(link)
    if not club_id:
        return _done("That link doesn't include the club's ID. On play.cricket.com.au, open your club's page "
                     "and copy the whole address from the browser: it ends with a long code like "
                     "c88df151-87d8-eb11-a7ad-2818780da0cc (after the club's name).", "err")
    try:
        session["found"] = scores.discover_club(club_id)
    except ValueError as error:
        session.pop("found", None)
        return _done(str(error), "err")
    return redirect("/setup")


def _save_logo(data):
    kind = _image_type(data)
    if not kind:
        raise ValueError("That isn't a PNG, JPEG, GIF, WebP or SVG image.")
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    old = config.get("logo")
    name = f"logo-{uuid.uuid4().hex[:8]}.{kind}"
    (config.DATA_DIR / name).write_bytes(data)
    config.save(logo=name)
    if old and old != name:
        (config.DATA_DIR / old).unlink(missing_ok=True)


@app.post("/setup/club/save")
@_guarded
def setup_club_save():
    form = request.form
    club_id = scores.club_id_from(form.get("club_id"))
    if not club_id:
        return _done("Please find the club again.", "err")
    config.save(club_id=club_id, club_name=form.get("club_name", "").strip()[:80],
                short_name=form.get("short_name", "").strip()[:30],
                team_prefix=form.get("team_prefix", "").strip()[:60])
    pc.clear_cache()
    session.pop("found", None)
    message = "Club saved. The scoreboard will switch over within a minute."
    if form.get("use_logo") and form.get("logo_url", "").startswith("https://"):
        try:
            response = requests.get(form["logo_url"], timeout=20)
            response.raise_for_status()
            _save_logo(response.content)
        except (requests.RequestException, ValueError):
            message += " (The PlayCricket logo couldn't be downloaded; you can upload one below.)"
    return _done(message)


@app.post("/setup/look")
@_guarded
def setup_look():
    form = request.form
    changes = {"title": form.get("title", "").strip()[:40] or config.DEFAULTS["title"]}
    preset = setup_page.PRESETS.get(form.get("preset", ""))
    if preset:
        changes.update(zip(("background", "panel", "accent", "text"), preset))
    else:
        for key in ("accent", "background", "panel", "text"):
            if COLOUR.match(form.get(key, "")):
                changes[key] = form[key].lower()
    config.save(**changes)
    return _done("Look saved.")


@app.post("/setup/logo")
@_guarded
def setup_logo():
    upload = request.files.get("logo")
    if not upload:
        return _done("Choose an image first.", "err")
    try:
        _save_logo(upload.read())
    except ValueError as error:
        return _done(str(error), "err")
    return _done("Logo saved.")


@app.post("/setup/logo/remove")
@_guarded
def setup_logo_remove():
    old = config.get("logo")
    config.save(logo="")
    if old:
        (config.DATA_DIR / old).unlink(missing_ok=True)
    return _done("Logo removed.")


def _whole(name, low, high, default):
    try:
        return min(max(int(request.form.get(name, default)), low), high)
    except ValueError:
        return default


@app.post("/setup/pages")
@_guarded
def setup_pages():
    config.save(page_seconds=_whole("page_seconds", 5, 300, 20),
                refresh_seconds=_whole("refresh_seconds", 30, 600, 60),
                **{key: request.form.get(key) == "1" for key in ("show_results", "show_leaders", "show_coming", "live_only")})
    return _done("Pages saved.")


@app.post("/setup/sponsors/add")
@_guarded
def setup_sponsor_add():
    sponsors = config.get("sponsors")
    if len(sponsors) >= MAX_SPONSORS:
        return _done(f"There's room for {MAX_SPONSORS} sponsors; remove one first.", "err")
    upload = request.files.get("image")
    data = upload.read() if upload else b""
    kind = _image_type(data)
    if not kind:
        return _done("That isn't a PNG, JPEG, GIF, WebP or SVG image.", "err")
    config.SPONSOR_DIR.mkdir(parents=True, exist_ok=True)
    sponsor_id = uuid.uuid4().hex
    name = f"{sponsor_id}.{kind}"
    (config.SPONSOR_DIR / name).write_bytes(data)
    config.save(sponsors=sponsors + [{"id": sponsor_id, "kind": "image", "file": name,
                                      "name": request.form.get("name", "").strip()[:60]}])
    return _done("Sponsor added.")


@app.post("/setup/sponsors/find")
@_guarded
def setup_sponsor_find():
    try:
        session["sponsor_found"] = sponsor_cards.from_website(request.form.get("website"))
    except ValueError as error:
        session.pop("sponsor_found", None)
        return _done(str(error), "err")
    return redirect("/setup#sponsors")


@app.post("/setup/sponsors/cancel")
@_guarded
def setup_sponsor_cancel():
    session.pop("sponsor_found", None)
    return redirect("/setup#sponsors")


@app.post("/setup/sponsors/save-card")
@_guarded
def setup_sponsor_save_card():
    found = session.get("sponsor_found")
    sponsors = config.get("sponsors")
    if not found:
        return _done("Please look up the website again.", "err")
    if len(sponsors) >= MAX_SPONSORS:
        return _done(f"There's room for {MAX_SPONSORS} sponsors; remove one first.", "err")
    form = request.form
    sponsor_id = uuid.uuid4().hex
    colour = form.get("colour", "")
    sponsor = {"id": sponsor_id, "kind": "card", "file": "", "web": found["web"],
               "name": form.get("name", "").strip()[:60] or found["name"],
               "tagline": sponsor_cards.clip_tagline(form.get("tagline", "")),
               "colour": colour.lower() if COLOUR.match(colour) else "#ffffff",
               "show_name": form.get("show_name") == "1"}
    message = "Sponsor slide added."
    logo_url = form.get("logo", "")
    if logo_url and logo_url in found.get("logo_options", []):
        try:
            data, kind = sponsor_cards.download_logo(logo_url)
            config.SPONSOR_DIR.mkdir(parents=True, exist_ok=True)
            sponsor["file"] = f"{sponsor_id}.{kind}"
            (config.SPONSOR_DIR / sponsor["file"]).write_bytes(data)
        except ValueError as error:
            message += f" ({error} The slide shows the name instead.)"
    config.save(sponsors=sponsors + [sponsor])
    session.pop("sponsor_found", None)
    return _done(message)


def _find_sponsor(sponsors, wanted):
    for sponsor in sponsors:
        if SPONSOR_ID.match(wanted) and (sponsor.get("id") or sponsor.get("file", "")).startswith(wanted):
            return sponsor
    return None


@app.post("/setup/sponsors/edit")
@_guarded
def setup_sponsor_edit():
    sponsors = config.get("sponsors")
    sponsor = _find_sponsor(sponsors, request.form.get("id", ""))
    if not sponsor:
        return _done("Sponsor not found.", "err")
    form = request.form
    sponsor["name"] = form.get("name", "").strip()[:60] or sponsor.get("name", "")
    if sponsor.get("kind") == "card":
        sponsor["tagline"] = sponsor_cards.clip_tagline(form.get("tagline", ""))
        if COLOUR.match(form.get("colour", "")):
            sponsor["colour"] = form["colour"].lower()
        sponsor["show_name"] = form.get("show_name") == "1"
    config.save(sponsors=sponsors)
    return _done(f"{sponsor['name']} saved.")


@app.post("/setup/sponsors/reread")
@_guarded
def setup_sponsor_reread():
    """Read the sponsor's website again for its full description."""
    sponsors = config.get("sponsors")
    sponsor = _find_sponsor(sponsors, request.form.get("id", ""))
    if not sponsor or not sponsor.get("web"):
        return _done("Sponsor not found.", "err")
    try:
        found = sponsor_cards.from_website(sponsor["web"])
    except ValueError as error:
        return _done(str(error), "err")
    sponsor["tagline"] = found["tagline"]
    config.save(sponsors=sponsors)
    session["flash"] = ("ok", "Read the website again: check the description below, then save.")
    return redirect(f"/setup?sponsor={sponsor['id']}#sponsors")


@app.post("/setup/sponsors/reread-all")
@_guarded
def setup_sponsor_reread_all():
    """Read every website slide's website again for its full description (names, colours and logos stay)."""
    sponsors = config.get("sponsors")
    updated, failed = [], []
    for sponsor in sponsors:
        if sponsor.get("kind") != "card" or not sponsor.get("web"):
            continue
        try:
            sponsor["tagline"] = sponsor_cards.from_website(sponsor["web"])["tagline"]
            updated.append(sponsor.get("name", sponsor["web"]))
        except ValueError:
            failed.append(sponsor.get("name", sponsor["web"]))
    config.save(sponsors=sponsors)
    message = f"Updated {len(updated)} description{'s' if len(updated) != 1 else ''}."
    if failed:
        message += f" Couldn't read: {', '.join(failed)} (edit those by hand)."
    return _done(message, "err" if failed and not updated else "ok")


@app.post("/setup/sponsors/remove")
@_guarded
def setup_sponsor_remove():
    wanted = request.form.get("id", "")
    sponsors = config.get("sponsors")
    if not SPONSOR_ID.match(wanted):
        return _done("Sponsor not found.", "err")
    for sponsor in sponsors:
        if (sponsor.get("id") or sponsor.get("file", "")).startswith(wanted):
            config.save(sponsors=[s for s in sponsors if s is not sponsor])
            if SPONSOR_FILE.match(sponsor.get("file", "")):
                (config.SPONSOR_DIR / sponsor["file"]).unlink(missing_ok=True)
            return _done("Sponsor removed.")
    return _done("Sponsor not found.", "err")


@app.post("/setup/sponsors/timing")
@_guarded
def setup_sponsor_timing():
    config.save(sponsor_every=_whole("sponsor_every", 0, 20, 3), sponsor_seconds=_whole("sponsor_seconds", 3, 60, 10))
    return _done("Sponsor timing saved.")


@app.post("/setup/extra")
@_guarded
def setup_extra():
    action = request.form.get("action", "")
    if action == "new-key":
        config.save(extra_key=secrets.token_urlsafe(24))
        return _done("New extra pages key made. Give it to the program that sends the pages.")
    if action == "remove":
        extra_pages.clear()
        return _done("Extra pages removed.")
    config.save(show_extra=request.form.get("show_extra") == "1")
    return _done("Extra pages setting saved.")


@app.post("/setup/wifi")
@_guarded
def setup_wifi():
    if not system.on_pi():
        return _done("Wi-Fi can only be changed on the scoreboard box itself.", "err")
    ssid = (request.form.get("ssid_other") or request.form.get("ssid") or "").strip()
    if not ssid:
        return _done("Choose a network.", "err")
    system.connect_wifi(ssid, request.form.get("password", ""))
    return _done(f"Connecting to {ssid}. If you were on the setup Wi-Fi, reconnect your phone to {ssid} "
                 "and open the address shown on the TV.")


@app.post("/setup/system")
@_guarded
def setup_system():
    action = request.form.get("action", "")
    if not system.on_pi() or action not in ("update", "restart", "reboot"):
        return _done("That's only available on the scoreboard box.", "err")
    system.run(action)
    return _done({"update": "Checking for updates; the screen restarts if there's a new version.",
                  "restart": "Restarting the screen.", "reboot": "Restarting the box; back in about a minute."}[action])


def main():
    try:
        from waitress import serve  # a proper server when it's installed (it is on the Pi)
    except ImportError:
        app.run(host=config.HOST, port=config.PORT, threaded=True)
    else:
        print(f"Around the Grounds on http://{config.HOST}:{config.PORT}")
        serve(app, host=config.HOST, port=config.PORT, threads=4)


if __name__ == "__main__":
    main()
