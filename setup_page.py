"""The setup page (/setup): made for a phone, as that's what's usually to hand at the clubrooms."""

from html import escape

import config
import extra_pages
import sponsor_cards
import system

PRESETS = {
    "Navy and gold": ("#0b1424", "#13213a", "#f2b632", "#f4f6fb"),
    "Black and red": ("#0d0d0f", "#1c1c21", "#e03131", "#f8f9fa"),
    "Green and gold": ("#0b2016", "#14321f", "#f2c12e", "#f4f8f4"),
    "Maroon and white": ("#22080d", "#3a1018", "#ffffff", "#fbeff1"),
    "Royal blue and white": ("#081a3d", "#11295c", "#ffffff", "#eef3ff"),
    "Black and white": ("#000000", "#18181b", "#ffffff", "#f4f4f5"),
}

STYLE = """
* { box-sizing: border-box; }
body { margin: 0; font-family: "Segoe UI", "Noto Sans", Arial, sans-serif; background: #f3f4f7; color: #1d2433; }
header { background: var(--bg); color: var(--text); padding: 16px 20px; border-bottom: 4px solid var(--accent);
         display: flex; align-items: center; gap: 14px; }
header img { height: 44px; }
header h1 { margin: 0; font-size: 1.3rem; }
header small { display: block; color: var(--accent); font-size: 0.8rem; letter-spacing: 2px; }
main { max-width: 760px; margin: 0 auto; padding: 16px; }
section { background: #fff; border-radius: 12px; padding: 18px 20px; margin-bottom: 16px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08); }
h2 { margin: 0 0 12px; font-size: 1.15rem; }
label { display: block; margin: 12px 0 4px; font-weight: 600; font-size: 0.95rem; }
label.inline { display: flex; gap: 8px; align-items: center; font-weight: 400; }
input[type=text], input[type=password], input[type=number], input[type=url], select {
    width: 100%; padding: 10px; font-size: 1rem; border: 1px solid #c8ccd6; border-radius: 8px; }
input[type=color] { width: 64px; height: 40px; border: none; padding: 0; background: none; }
.colours { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; }
button, .button { display: inline-block; margin-top: 14px; padding: 10px 18px; font-size: 1rem; border: none;
                  border-radius: 8px; background: #1d4ed8; color: #fff; cursor: pointer; text-decoration: none; }
button.secondary { background: #e4e7ee; color: #1d2433; }
button.danger { background: #c92a2a; }
.note { color: #5b6477; font-size: 0.9rem; }
.flash { padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; }
.flash.ok { background: #e6f6ea; color: #1b5e2b; } .flash.err { background: #fdecec; color: #8a1c1c; }
.sponsors { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }
.sponsor { border: 1px solid #e1e4ea; border-radius: 8px; padding: 8px; text-align: center; }
.sponsor img { max-width: 100%; max-height: 90px; object-fit: contain; }
.inline-form { display: inline; }
.sc-mini { height: 90px; display: flex; align-items: center; justify-content: center; border-radius: 6px;
           font-weight: 700; border: 1px solid #e1e4ea; color: #111; }
.logo-options { display: flex; flex-wrap: wrap; gap: 10px; }
.logo-option { display: flex; align-items: center; gap: 6px; border: 1px solid #e1e4ea; border-radius: 8px;
               padding: 6px 10px; font-weight: 400; margin: 0; background: #f8f9fb; }
.logo-option img { max-height: 60px; max-width: 160px; object-fit: contain; }
dl { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 4px 12px; margin: 0; }
dt { color: #5b6477; }
dd { margin: 0; min-width: 0; overflow-wrap: anywhere; }
main, section { min-width: 0; overflow-wrap: anywhere; }
input[type=file] { display: block; max-width: 100%; margin-top: 6px; }
"""


def _e(value):
    return escape(str(value), quote=True)


def _form(action, inner, token, extra=""):
    return (f'<form method="post" action="{action}"{extra}>'
            f'<input type="hidden" name="csrf" value="{_e(token)}">{inner}</form>')


def _shell(body, settings, flash=None):
    from screen import theme_css

    note = ""
    if flash:
        kind, text = flash
        note = f'<div class="flash {_e(kind)}">{_e(text)}</div>'
    logo = '<img src="/media/logo" alt="">' if settings.get("logo") else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Set up · {_e(settings["title"])}</title><style>{theme_css(settings)}{STYLE}</style></head>
<body><header>{logo}<div><h1>{_e(settings["title"])}</h1><small>SETUP</small></div></header>
<main>{note}{body}</main></body></html>"""


def login_page(settings, first_time, flash=None):
    if first_time:
        body = """<section><h2>Welcome</h2><p>Choose a setup PIN (4 to 8 digits). You'll need it to change
        the scoreboard later, so keep it with the club's passwords.</p>
        <form method="post" action="/setup/pin"><label for="pin">New PIN</label>
        <input id="pin" name="pin" type="password" inputmode="numeric" autocomplete="new-password" required>
        <label for="again">Same PIN again</label>
        <input id="again" name="again" type="password" inputmode="numeric" autocomplete="new-password" required>
        <button type="submit">Save PIN</button></form></section>"""
    else:
        body = """<section><h2>Enter the setup PIN</h2>
        <form method="post" action="/setup/login"><label for="pin">PIN</label>
        <input id="pin" name="pin" type="password" inputmode="numeric" autocomplete="current-password" autofocus required>
        <button type="submit">Open setup</button></form>
        <p class="note">Forgotten it? See "Reset the setup PIN" in the guide that came with the scoreboard.</p></section>"""
    return _shell(body, settings, flash)


def setup_page(settings, token, found=None, flash=None, sponsor_found=None):
    parts = []

    # ---- Wi-Fi (on the Pi only)
    if system.on_pi():
        networks = system.wifi_networks()
        current = system.current_wifi()
        options = "".join(f'<option value="{_e(n["ssid"])}">{_e(n["ssid"])} ({n["signal"]}%)'
                          f'{"" if n["secure"] else " · open"}</option>' for n in networks)
        parts.append(f"""<section><h2>Wi-Fi</h2>
        <p>{"Connected to <strong>" + _e(current) + "</strong>." if current else "Not connected to a Wi-Fi network."}</p>
        {_form("/setup/wifi", f'''<label for="ssid">Network</label>
        <select id="ssid" name="ssid">{options}<option value="">Other (type it below)</option></select>
        <label for="ssid-other">Other network name</label><input id="ssid-other" name="ssid_other" type="text">
        <label for="wifi-password">Password</label><input id="wifi-password" name="password" type="password">
        <button type="submit">Connect</button>
        <p class="note">The scoreboard switches over straight away. If you're using its setup Wi-Fi,
        your phone will drop off it: reconnect your phone to the club's Wi-Fi and open the address the TV shows.</p>''', token)}
        </section>""")

    # ---- Club
    club = settings.get("club_name")
    current = (f"<dl><dt>Club</dt><dd>{_e(club)}</dd><dt>On the scoreboard</dt><dd>{_e(settings['short_name'])}</dd>"
               f"<dt>Team names start</dt><dd>{_e(settings['team_prefix'])}</dd></dl>" if club
               else "<p>No club chosen yet.</p>")
    confirm = ""
    if found:
        confirm = _form("/setup/club/save", f"""<h2 style="margin-top:16px">Is this your club?</h2>
        <p><strong>{_e(found['club_name'])}</strong> · {found['teams']} teams in {_e(found['season'])}</p>
        <input type="hidden" name="club_id" value="{_e(found['club_id'])}">
        <input type="hidden" name="logo_url" value="{_e(found['logo_url'])}">
        <label for="club-name">Club name</label><input id="club-name" name="club_name" type="text" value="{_e(found['club_name'])}">
        <label for="short-name">Name on the scoreboard (short)</label><input id="short-name" name="short_name" type="text" value="{_e(found['short_name'])}">
        <label for="prefix">Team names start with</label><input id="prefix" name="team_prefix" type="text" value="{_e(found['team_prefix'])}">
        <p class="note">Used to shorten "{_e(found['team_prefix'])} 1st XI" to "1st XI".</p>
        {'<label class="inline"><input type="checkbox" name="use_logo" value="1" checked> Use the club logo from PlayCricket</label>' if found['logo_url'] else ''}
        <button type="submit">Yes, use this club</button>""", token)
    parts.append(f"""<section><h2>Club</h2>{current}
    {_form("/setup/club/find", '''<label for="link">Link to your club's PlayCricket page</label>
    <input id="link" name="link" type="url" placeholder="https://play.cricket.com.au/club/..." required>
    <p class="note">Find your club on play.cricket.com.au, open its page, and copy the whole address from the
    browser. It ends with a long code after the club's name, e.g.
    play.cricket.com.au/club/your-club-name/<strong>c88df151-87d8-eb11-a7ad-2818780da0cc</strong></p>
    <button type="submit">Find club</button>''', token)}{confirm}</section>""")

    # ---- Look
    presets = "".join(f'<option value="{_e(name)}">{_e(name)}</option>' for name in PRESETS)
    colours = "".join(
        f'<label>{label}<br><input type="color" name="{key}" value="{_e(settings[key])}"></label>'
        for key, label in (("accent", "Highlight"), ("background", "Background"), ("panel", "Panels"), ("text", "Text")))
    logo_now = ('<p><img src="/media/logo" alt="" style="max-height:80px"></p>' if settings.get("logo")
                else '<p class="note">No logo yet.</p>')
    parts.append(f"""<section><h2>Look</h2>
    {_form("/setup/look", f'''<label for="title">Heading</label>
    <input id="title" name="title" type="text" value="{_e(settings['title'])}" maxlength="40">
    <label>Colours</label><div class="colours">{colours}</div>
    <label for="preset">Or a ready-made set</label>
    <select id="preset" name="preset"><option value="">(keep the colours above)</option>{presets}</select>
    <button type="submit">Save look</button>''', token)}
    <h2 style="margin-top:18px">Logo</h2>{logo_now}
    {_form("/setup/logo", '''<input name="logo" type="file" accept="image/png,image/jpeg,image/webp,image/gif" required>
    <button type="submit">Upload logo</button>''', token, ' enctype="multipart/form-data"')}
    {_form("/setup/logo/remove", '<button type="submit" class="secondary">Remove logo</button>', token) if settings.get("logo") else ""}
    </section>""")

    # ---- Pages
    def tick(key, label):
        return (f'<label class="inline"><input type="checkbox" name="{key}" value="1"'
                f'{" checked" if settings[key] else ""}> {label}</label>')

    parts.append(f"""<section><h2>Pages</h2>
    {_form("/setup/pages", f'''<label for="page-seconds">Seconds on each page</label>
    <input id="page-seconds" name="page_seconds" type="number" min="5" max="300" value="{settings['page_seconds']}">
    <label for="refresh">Seconds between score checks</label>
    <input id="refresh" name="refresh_seconds" type="number" min="30" max="600" value="{settings['refresh_seconds']}">
    <label>Also show</label>
    {tick("show_leaders", "Season leaders")}
    {tick("show_coming", "Coming up (the next match day's games)")}
    {tick("show_results", "Latest results (on days without games)")}
    <label>While games are being played</label>
    {tick("live_only", "Show only the live scores")}
    <button type="submit">Save pages</button>''', token)}</section>""")

    # ---- Sponsors
    def tile(s):
        picture = (f'<img src="/media/sponsors/{_e(s["file"])}" alt="">' if s.get("file")
                   else f'<div class="sc-mini" style="background:{_e(s.get("colour", "#fff"))}">{_e(s.get("name", ""))}</div>')
        kind = "Website slide" if s.get("kind") == "card" else "Image"
        return (f'<div class="sponsor">{picture}<div>{_e(s.get("name", ""))}</div><div class="note">{kind}</div>'
                + _form("/setup/sponsors/remove", f'<input type="hidden" name="id" value="{_e(s.get("id") or s["file"])}">'
                        '<button type="submit" class="secondary">Remove</button>', token, ' class="inline-form"')
                + "</div>")

    tiles = "".join(tile(s) for s in settings["sponsors"]) or '<p class="note">No sponsors yet.</p>'
    confirm = ""
    if sponsor_found:
        options = "".join(
            f'<label class="logo-option"><input type="radio" name="logo" value="{_e(url)}"{" checked" if n == 0 else ""}>'
            f'<img src="{_e(url)}" alt="" referrerpolicy="no-referrer"></label>'
            for n, url in enumerate(sponsor_found["logo_options"]))
        options += '<label class="logo-option"><input type="radio" name="logo" value=""' + (
            "" if sponsor_found["logo_options"] else " checked") + '> No logo (show the name)</label>'
        confirm = _form("/setup/sponsors/save-card", f"""<h2 style="margin-top:16px">Check the slide</h2>
        <p class="note">From {_e(sponsor_found['web'])}. Change anything that isn't right.</p>
        <label for="sc-name">Name</label><input id="sc-name" name="name" type="text" maxlength="60" value="{_e(sponsor_found['name'])}">
        <label for="sc-tag">Line underneath</label><input id="sc-tag" name="tagline" type="text" maxlength="140" value="{_e(sponsor_found['tagline'])}">
        <label>Background colour</label><input name="colour" type="color" value="{_e(sponsor_found['colour'])}">
        <label>Logo</label><div class="logo-options">{options}</div>
        <label class="inline"><input type="checkbox" name="show_name" value="1"> Show the name under the logo too
        (leave this off if the logo already says it)</label>
        <button type="submit">Add this sponsor</button>""", token) + _form(
            "/setup/sponsors/cancel", '<button type="submit" class="secondary">Cancel</button>', token)
    parts.append(f"""<section id="sponsors"><h2>Sponsors</h2>
    <p class="note">A sponsor's slide comes up between pages.</p>
    <div class="sponsors">{tiles}</div>
    {_form("/setup/sponsors/find", '''<label for="sponsor-site">Make a slide from the sponsor's website</label>
    <input id="sponsor-site" name="website" type="text" inputmode="url" placeholder="e.g. westsidebakery.com.au" required>
    <button type="submit">Make slide</button>''', token)}{confirm}
    {_form("/setup/sponsors/add", '''<label for="sponsor-file">Or upload their logo or advert (a wide, landscape image looks best)</label>
    <input id="sponsor-file" name="image" type="file" accept="image/png,image/jpeg,image/webp,image/gif,image/svg+xml" required>
    <label for="sponsor-name">Sponsor's name (optional)</label><input id="sponsor-name" name="name" type="text" maxlength="60">
    <button type="submit">Add sponsor</button>''', token, ' enctype="multipart/form-data"')}
    {_form("/setup/sponsors/timing", f'''<label for="every">Show a sponsor after every … pages (0 = never)</label>
    <input id="every" name="sponsor_every" type="number" min="0" max="20" value="{settings['sponsor_every']}">
    <label for="sponsor-seconds">Seconds on each sponsor</label>
    <input id="sponsor-seconds" name="sponsor_seconds" type="number" min="3" max="60" value="{settings['sponsor_seconds']}">
    <button type="submit" class="secondary">Save sponsor timing</button>''', token)}</section>""")

    # ---- Extra pages (sent by another program, e.g. a club's own stats archive)
    pack = extra_pages.load()
    if pack and pack["pages"]:
        titles = "".join(f"<li>{_e(p['title'])}</li>" for p in pack["pages"])
        status = (f"<p>{len(pack['pages'])} page{'s' if len(pack['pages']) != 1 else ''} from "
                  f"<strong>{_e(pack['source'] or 'another program')}</strong>"
                  f"{', sent ' + _e(pack['published'].replace('T', ' at ')) if pack['published'] else ''}:</p><ul>{titles}</ul>")
    else:
        status = '<p class="note">No extra pages yet.</p>'
    key = settings.get("extra_key")
    key_text = (f'<p>Key: <code style="word-break:break-all">{_e(key)}</code></p>' if key
                else '<p class="note">No key yet: make one to let another program send pages.</p>')
    parts.append(f"""<section id="extra"><h2>Extra pages</h2>
    <p class="note">Pages your club's own systems send to the scoreboard (for example career stats from a club
    archive). They show after the season leaders. The sending program needs this box's address and key.</p>
    {status}
    {_form("/setup/extra", f'''<label class="inline"><input type="checkbox" name="show_extra" value="1"{" checked" if settings["show_extra"] else ""}> Show extra pages</label>
    <button type="submit" class="secondary">Save</button>''', token)}
    {key_text}
    {_form("/setup/extra", '<input type="hidden" name="action" value="new-key"><button type="submit" class="secondary">Make a new key</button>', token, ' class="inline-form"')}
    {_form("/setup/extra", '<input type="hidden" name="action" value="remove"><button type="submit" class="secondary">Remove extra pages</button>', token, ' class="inline-form"') if pack else ""}
    </section>""")

    # ---- PIN and system
    system_buttons = ""
    if system.on_pi():
        system_buttons = "".join(
            _form("/setup/system", f'<input type="hidden" name="action" value="{action}">'
                  f'<button type="submit" class="{style}">{label}</button>', token, ' class="inline-form"') + " "
            for action, label, style in (("update", "Check for updates now", "secondary"),
                                         ("restart", "Restart the screen", "secondary"),
                                         ("reboot", "Restart the scoreboard box", "danger")))
    parts.append(f"""<section><h2>Setup PIN{" and system" if system_buttons else ""}</h2>
    {_form("/setup/pin", '''<label for="new-pin">New PIN</label>
    <input id="new-pin" name="pin" type="password" inputmode="numeric" autocomplete="new-password" required>
    <label for="new-again">Same PIN again</label>
    <input id="new-again" name="again" type="password" inputmode="numeric" autocomplete="new-password" required>
    <button type="submit" class="secondary">Change PIN</button>''', token)}
    <div>{system_buttons}</div>
    <p><a class="button" href="/" target="_blank">View the scoreboard</a>
    {_form("/setup/logout", '<button type="submit" class="secondary">Log out</button>', token, ' class="inline-form"')}</p>
    </section>""")
    return _shell("".join(parts), settings, flash)
