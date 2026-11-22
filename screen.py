"""Around the Grounds: the full-screen 1920x1080 scoreboard page.

The page is a frame; its script asks /board for fresh pages every
REFRESH_SECONDS and turns pages every PAGE_SECONDS when there's more than one.
Card layouts come from the club archive's TV display.
"""

from html import escape

import config
import extra_pages



def _short():
    """The club's name on the scoreboard, e.g. 'Roosters'."""
    return config.get("short_name") or config.get("team_prefix") or "Us"
GRID_MAX = 9


def _e(value):
    return escape(str(value))


def _live_card(game, with_day=False):
    """A game's card. ``with_day`` adds the day to the start time (for the week ahead)."""
    state = game["state"]
    start = f"{game.get('weekday', '')} {game['start']}".strip() if with_day and game["start"] else game["start"]
    pill = {"live": '<span class="pill pill-live">LIVE</span>',
            "done": '<span class="pill pill-done">Result</span>',
            "off": '<span class="pill pill-off">Abandoned</span>',
            "unscored": '<span class="pill pill-off">No live score</span>'}.get(
        state, f'<span class="pill pill-soon">{_e(start or "Today")}</span>')
    if game.get("day"):
        pill = f'<span class="pill pill-day">Day {game["day"]}</span>' + pill
    sides = "".join(
        f'<div class="side{" ours" if side["ours"] else ""}{" batting" if side["batting"] and state == "live" else ""}">'
        f'<span class="side-name">{_short() if side["ours"] else _e(side["name"])}</span>'
        f'<span class="side-score">{_e(side["score"]) or ("&ndash;" if state != "upcoming" else "")}</span>'
        f'<span class="side-overs">{_e(side["overs"]) + " ov" if side["overs"] else ""}</span></div>'
        for side in game["sides"]
    )
    if state == "upcoming":
        note = f"Starts {_e(start)} · {'Home' if game['home'] else 'Away'}" if game["start"] else ""
    elif state == "unscored":
        note = f"Started {_e(game['start'])} · result to come"
    else:
        note = _e(game["result"])
    crease = ""
    if state == "live" and (game["batters"] or game["bowler"]):
        batters = " &nbsp; ".join(
            f'{_e(b["name"])} <strong>{b["runs"]}{"*" if b["strike"] else ""}</strong> ({b["balls"]})'
            for b in game["batters"])
        bowler = game["bowler"]
        bowling = (f'<span class="crease-bowl">Bowling: {_e(bowler["name"])} '
                   f'<strong>{bowler["wickets"]}/{bowler["runs"]}</strong> ({_e(bowler["overs"])})</span>'
                   if bowler else "")
        crease = f'<div class="crease"><span>{batters}</span>{bowling}</div>'
    meta = " · ".join(_e(part) for part in (game["round"], game["grade"]) if part)
    return (
        f'<section class="game game-{state}"><div class="game-head"><span class="game-team">{_e(game["team"])}</span>'
        f'<span class="pills">{pill}</span></div><div class="game-meta">{meta}</div>{sides}'
        f'<div class="game-note">{note}</div>{crease}'
        f'<div class="game-venue">{_e(game["venue"])}</div></section>'
    )


def _trim(rows, keep, limit):
    """At most ``limit`` rows, always including those ``keep`` picks, latest first to go last."""
    if len(rows) <= limit:
        return rows
    kept = [r for r in rows if keep(r)]
    others = [r for r in rows if not keep(r)][-(limit - len(kept)):] if limit > len(kept) else []
    return [r for r in rows if r in kept or r in others]


def _side_name(side):
    return _short() if side["ours"] else side["name"]


def _focus_card(game, wide, rows, page_note=""):
    """One live game, large: scoreboard, then the innings being played."""
    sides = "".join(
        f'<div class="team-score{" ours" if side["ours"] else ""}{" batting" if side["batting"] else ""}">'
        f'<span class="ts-name">{_e(_side_name(side))}</span>'
        f'<span class="ts-score">{_e(side["score"]) or "&ndash;"}</span>'
        f'<span class="ts-overs">{_e(side["overs"]) + " overs" if side["overs"] else "yet to bat"}</span></div>'
        for side in game["sides"]
    )
    innings = game.get("innings") or []
    current = innings[-1] if innings else None
    body = ""
    if current:
        ours = {side["id"]: side["ours"] for side in game["sides"]}
        batting_name = _short() if ours.get(current["team_id"]) else current["team"]
        bowling_side = next((side for side in game["sides"] if side["id"] != current["team_id"]), None)
        bowling_name = _side_name(bowling_side) if bowling_side else ""
        batters = _trim(current["batting"], lambda b: b["in"], rows)
        bowlers = _trim(current["bowling"], lambda b: b["now"], rows)
        wide_cols = '<th class="num wide-col">4s</th><th class="num wide-col">6s</th>' if wide else ""
        bat_rows = "".join(
            f'<tr class="{"in" if b["in"] else ("out" if b["dismissed"] else "")}">'
            f'<td>{_e(b["name"])}'
            + (f' <span class="how">{_e(b["out"])}</span>' if wide and not b["in"] else "")
            + f'</td><td class="num">{b["runs"]}{"*" if b["in"] else ""}</td><td class="num">{b["balls"]}</td>'
            + (f'<td class="num wide-col">{b["fours"]}</td><td class="num wide-col">{b["sixes"]}</td>' if wide else "")
            + "</tr>"
            for b in batters
        )
        bowl_rows = "".join(
            f'<tr class="{"in" if b["now"] else ""}"><td>{_e(b["name"])}{" &bull;" if b["now"] else ""}</td>'
            f'<td class="num">{_e(b["overs"])}</td>'
            + (f'<td class="num wide-col">{b["maidens"]}</td>' if wide else "")
            + f'<td class="num">{b["runs"]}</td><td class="num">{b["wickets"]}</td></tr>'
            for b in bowlers
        )
        facts = " · ".join(part for part in (
            f"Last wicket: {_e(current['last_wicket'])}" if current["last_wicket"] else "",
            f"Extras {current['extras']}",
            f"Run rate {current['run_rate']}" if current["run_rate"] else "",
        ) if part)
        earlier = ""
        for inning in innings[:-1]:
            top_bat = sorted(inning["batting"], key=lambda b: -b["runs"])[:2]
            top_bowl = sorted(inning["bowling"], key=lambda b: (-b["wickets"], b["runs"]))[:2]
            who = _short() if ours.get(inning["team_id"]) else inning["team"]
            earlier += (
                f'<p class="earlier"><strong>{_e(who)} {_e(inning["score"])}</strong> ({_e(inning["overs"])} ov)'
                + (": " + ", ".join(f'{_e(b["name"])} {b["runs"]}' for b in top_bat) if top_bat else "")
                + (" · bowling " + ", ".join(f'{_e(b["name"])} {b["wickets"]}/{b["runs"]}' for b in top_bowl)
                   if top_bowl else "")
                + "</p>"
            )
        body = (
            '<div class="cards">'
            f'<div><h3>Batting · {_e(batting_name)}</h3><table class="card-table"><thead><tr><th>Batter</th>'
            f'<th class="num">R</th><th class="num">B</th>{wide_cols}</tr></thead><tbody>{bat_rows}</tbody></table></div>'
            f'<div><h3>Bowling · {_e(bowling_name)}</h3><table class="card-table"><thead><tr><th>Bowler</th>'
            '<th class="num">O</th>' + ('<th class="num wide-col">M</th>' if wide else "")
            + f'<th class="num">R</th><th class="num">W</th></tr></thead><tbody>{bowl_rows}</tbody></table></div>'
            "</div>"
            f'<p class="facts">{facts}</p>{earlier}'
        )
    meta = " · ".join(_e(part) for part in (game["round"], game["grade"], game["venue"]) if part)
    return (
        f'<section class="focus-card"><div class="game-head"><span class="game-team">{_e(game["team"])}</span>'
        f'<span class="head-meta">{meta}</span>'
        f'<span class="pills">{page_note}<span class="pill pill-live">LIVE</span></span></div>'
        f'<div class="scoreboard">{sides}</div>'
        f'<div class="state">{_e(game["result"])}</div>{body}</section>'
    )


def _tile(game):
    """A small score for the strip along the bottom."""
    state = game["state"]
    pill = {"live": '<span class="pill pill-live">LIVE</span>', "done": '<span class="pill pill-done">Result</span>',
            "off": '<span class="pill pill-off">Off</span>',
            "unscored": '<span class="pill pill-off">No live score</span>'}.get(
        state, f'<span class="pill pill-soon">{_e(game["start"] or "Today")}</span>')
    opponent = next((side for side in game["sides"] if not side["ours"]), None)
    if state in ("upcoming", "unscored"):
        line = f'v {_e(opponent["name"]) if opponent else ""}'
    elif state == "live":
        line = " v ".join(
            f'<strong>{_e(side["score"]) or "&ndash;"}</strong>'
            + (f' <small>({_e(side["overs"])})</small>' if side["overs"] else "")
            for side in game["sides"])
    else:
        line = " v ".join(
            f'{_e(_short() if side["ours"] else side["name"])} <strong>{_e(side["score"]) or "&ndash;"}</strong>'
            for side in game["sides"])
    note = _e(game["result"]) if state not in ("upcoming", "unscored") else ""
    return (f'<div class="tile tile-{state}"><div class="tile-head"><span class="tile-team">{_e(game["team"])}</span>'
            f'{pill}</div><div class="tile-line">{line}</div><div class="tile-note">{note}</div></div>')



def _day(day):
    return f"{day:%A} {day.day} {day:%B}" if day else ""


def _days(first, last):
    """'Friday 27 November', or 'Fri 27 – Sun 29 November' for several days."""
    if not first:
        return ""
    if not last or last == first:
        return _day(first)
    start = f"{first:%a} {first.day}" + ("" if first.month == last.month else f" {first:%B}")
    return f"{start} – {last:%a} {last.day} {last:%B}"


def _page(title, inner, first=False):
    return f'<div class="live-page{" on" if first else ""}" data-title="{escape(title, quote=True)}">{inner}</div>'


def _grid_pages(title, games, with_day=False):
    """Cards in a grid, nine to a page."""
    pages = []
    for start in range(0, len(games), GRID_MAX):
        chunk = games[start:start + GRID_MAX]
        columns = 2 if len(chunk) <= 4 else 3
        rows = -(-len(chunk) // columns)
        pages.append((title, f'<div class="live-grid cols{columns} rows{rows}">'
                      + "".join(_live_card(g, with_day) for g in chunk) + "</div>"))
    return pages


def _leaders_page(leaders):
    def table(headers, rows):
        head = '<th class="rank">#</th>' + "".join(
            f'<th class="{"num" if i else ""}">{_e(h)}</th>' for i, h in enumerate(headers))
        body = "".join(
            f'<tr><td class="rank">{n}</td><td>{_e(name)}</td><td class="num">{_e(main)}</td>'
            f'<td class="num">{_e(extra)}</td></tr>'
            for n, (name, main, extra) in enumerate(rows, start=1)
        ) or '<tr><td colspan="4" class="empty">None yet</td></tr>'
        return f'<table class="ranked"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'

    panels = (
        ("Most runs", table(("Player", "Runs", "HS"), leaders["runs"])),
        ("Most wickets", table(("Player", "Wkts", "Best"), leaders["wickets"])),
        ("Most catches", table(("Player", "Ct", "Games"), leaders["catches"])),
    )
    return '<div class="leaders">' + "".join(
        f'<section class="panel"><h2>{title}</h2>{inner}</section>' for title, inner in panels) + "</div>"


def _message(text):
    return f'<p class="live-empty">{text}</p>'


def _setup_message(board):
    """What a new (or offline) box shows: how to reach its setup page."""
    hotspot = board.get("hotspot")
    addresses = board.get("addresses") or []
    steps = []
    if hotspot:
        steps.append(f"On a phone, join the Wi-Fi network <strong>{_e(hotspot['ssid'])}</strong>"
                     f" (password <strong>{_e(hotspot['password'])}</strong>)")
        steps.append(f"Open <strong>http://{_e(hotspot['address'])}:{config.PORT}/setup</strong>")
        steps.append("Choose the club's Wi-Fi, then follow the steps")
    else:
        where = " or ".join(f"<strong>http://{_e(a)}:{config.PORT}/setup</strong>" for a in addresses[:2])
        steps.append("On a phone or laptop on the same Wi-Fi as this screen")
        steps.append(f"Open {where}")
        steps.append("Paste the link to your club's PlayCricket page, then follow the steps")
    heading = "Connect me to Wi-Fi" if hotspot else "Let's get set up"
    items = "".join(f"<li>{step}</li>" for step in steps)
    return f'<div class="setup-screen"><h2>{heading}</h2><ol>{items}</ol></div>'


def _sent_pages():
    """Pages another program sent (extra_pages.py), with their own extra styles."""
    pack = extra_pages.load() if config.get("show_extra") else None
    if not pack or not pack["pages"]:
        return []
    pages = []
    for n, page in enumerate(pack["pages"]):
        style = f"<style>{pack['css']}</style>" if n == 0 and pack.get("css") else ""
        screen = f' data-screen="{page["screen"]}"' if page.get("screen") else ""
        pages.append((page["title"], f'{style}<div class="extra-grid cols-{page["columns"]}"{screen}>{page["html"]}</div>'))
    return pages


def _extra_pages(board):
    """Season leaders and the next match day, after the day's own pages."""
    pages = []
    leaders = board.get("leaders")
    if leaders and config.get("show_leaders") and (leaders["runs"] or leaders["wickets"] or leaders["catches"]):
        pages.append((f"Season leaders · {leaders['season']}", _leaders_page(leaders)))
    pages += _sent_pages()
    if board.get("coming") and config.get("show_coming"):
        pages += _grid_pages(f"Coming up · {_days(board['coming_day'], board.get('coming_until'))}",
                             board["coming"], with_day=True)
    return pages


def render_board(board):
    """The pages for one ``scores.live_board()`` result (None: still checking)."""
    pages = []
    if board is not None and (board.get("hotspot") or board.get("mode") == "setup"):
        pages = [(config.get("title"), _setup_message(board))]
    elif board is None:
        pages = [(config.get("title"), _message("Checking PlayCricket&hellip;"))]
    elif board.get("error"):
        pages = [(config.get("title"), _message(f"{_e(board['error'])}. Trying again shortly."))]
    elif board["mode"] == "today" and any(g["state"] == "live" for g in board["games"]):
        # The games being played fill the screen (two side by side; three or
        # more take a page each); everything else is a small score along the bottom.
        games = board["games"]
        playing = [g for g in games if g["state"] == "live"]
        groups = [playing] if len(playing) <= 2 else [[g] for g in playing]
        for n, group in enumerate(groups, start=1):
            others = [g for g in games if g not in group][:6]
            note = f'<span class="pill pill-day">{n} of {len(groups)}</span>' if len(groups) > 1 else ""
            cards = "".join(_focus_card(g, len(group) == 1, 6 if others else 10, note) for g in group)
            strip = f'<div class="strip">{"".join(_tile(g) for g in others)}</div>' if others else ""
            pages.append(("Live scores", f'<div class="focus focus-{len(group)}">{cards}</div>{strip}'))
        if not config.get("live_only"):
            pages += _extra_pages(board)
    elif board["mode"] == "today":
        pages = _grid_pages("Today\'s games", board["games"]) + _extra_pages(board)
    else:
        if board.get("results") and config.get("show_results"):
            pages += _grid_pages(f"Latest results · {_day(board['results_day'])}", board["results"])
        pages += _extra_pages(board)
        if not pages:
            pages = [(config.get("title"), _message("No games scheduled."))]
    return "".join(_page(title, inner, n == 0) for n, (title, inner) in enumerate(pages))


STYLE = """
:root { --bg: #0b1424; --panel: #13213a; --line: #24375a; --text: #f4f6fb; --muted: #9fb0cc;
        --accent: #f2b632; --win: #2f9e44; --loss: #c92a2a; --draw: #8c7a1e; }
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; background: #000; overflow: hidden; cursor: none; }
body { font-family: "Segoe UI", Arial, sans-serif; color: var(--text); }
#stage { position: absolute; top: 0; left: 0; width: 1920px; height: 1080px; background: var(--bg);
         transform-origin: top left; overflow: hidden; }
.topbar { position: absolute; top: 0; left: 0; right: 0; height: 96px; display: flex; align-items: center;
          justify-content: space-between; padding: 0 56px; border-bottom: 4px solid var(--accent); }
.club { font-size: 40px; font-weight: 800; letter-spacing: 2px; }
.club small { display: block; font-size: 20px; font-weight: 600; color: var(--accent); letter-spacing: 6px; }
.level-badge { font-size: 30px; font-weight: 800; letter-spacing: 4px; text-transform: uppercase;
               color: var(--bg); background: var(--accent); border-radius: 999px; padding: 6px 30px; }
.level-badge:empty { display: none; }
.clock { font-size: 40px; font-weight: 700; text-align: right; }
.clock small { display: block; font-size: 20px; font-weight: 500; color: var(--muted); }
.slide { position: absolute; top: 96px; left: 0; width: 1920px; height: 924px; padding: 28px 56px 0;
         opacity: 0; transition: opacity 0.8s ease; }
.slide.active { opacity: 1; }
.slide-head h1 { margin: 0 0 22px; font-size: 64px; line-height: 1.1; }
.slide-body { display: grid; gap: 36px; height: 770px; }
.cols-1 .slide-body { grid-template-columns: 1fr; }
.cols-2 .slide-body { grid-template-columns: 1fr 1fr; }
.cols-3 .slide-body { grid-template-columns: 1fr 1fr 1fr; }
.panel { background: var(--panel); border-radius: 18px; padding: 22px 28px; overflow: hidden; }
.panel.wide { grid-column: 1 / -1; padding-bottom: 12px; }
.panel h2 { margin: 0 0 12px; font-size: 38px; color: var(--accent); }
.panel .sub { margin: -6px 0 10px; font-size: 22px; color: var(--muted); }
table { width: 100%; border-collapse: collapse; font-size: 32px; table-layout: fixed; }
th { text-align: left; font-size: 22px; color: var(--muted); font-weight: 600; text-transform: uppercase;
     letter-spacing: 1px; padding: 6px 10px; border-bottom: 2px solid var(--line); white-space: nowrap; }
td { padding: 9px 10px; border-bottom: 1px solid var(--line); white-space: nowrap; overflow: hidden;
     text-overflow: ellipsis; }
th.rank { width: 64px; }
th.num { width: 190px; }
.cols-3 table { font-size: 30px; }
.cols-3 th.rank { width: 64px; }
td.rank { padding-right: 4px; text-overflow: clip; }
.cols-3 th.num { width: 92px; }
.slide[data-screen="milestones"] th.num { width: 200px; }
.slide[data-screen="leaders"] th.num { width: 150px; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
td.num small { font-size: 20px; color: var(--muted); }
td.rank { color: var(--muted); }
table.ranked tbody tr:first-child td { font-weight: 700; }
td.empty { color: var(--muted); font-style: italic; }
.detail { color: var(--muted); font-size: 26px; }
.chip { display: inline-block; min-width: 54px; text-align: center; border-radius: 8px; font-weight: 800; }
.chip-w { background: var(--win); } .chip-l { background: var(--loss); }
.chip-d, .chip-t { background: var(--draw); } .chip-x { background: #555; }
.tallies { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }
.tally { background: var(--bg); border-radius: 14px; padding: 18px; text-align: center; }
.tally strong { display: block; font-size: 72px; color: var(--accent); line-height: 1; }
.tally span { font-size: 26px; }
.reached { columns: 3; margin: 0; padding: 0 0 0 28px; font-size: 28px; }
.reached li { margin-bottom: 6px; }
.footer { position: absolute; left: 0; right: 0; bottom: 0; height: 60px; display: flex; align-items: center;
          justify-content: space-between; padding: 0 56px; font-size: 22px; color: var(--muted); }
.dots span { display: inline-block; width: 16px; height: 16px; border-radius: 50%; background: var(--line);
             margin-left: 10px; }
.dots span.on { background: var(--accent); }
.slide-head h1 small { font-size: 26px; font-weight: 500; color: var(--muted); margin-left: 18px; }
.live-empty { font-size: 44px; color: var(--muted); margin: 120px 0 0; text-align: center; }
.live-grid { display: grid; gap: 28px; height: 770px; }
.live-grid.cols2 { grid-template-columns: 1fr 1fr; }
.live-grid.cols3 { grid-template-columns: 1fr 1fr 1fr; }
.live-grid.rows1 { grid-template-rows: 1fr; } .live-grid.rows2 { grid-template-rows: 1fr 1fr; }
.live-grid.rows3 { grid-template-rows: 1fr 1fr 1fr; }
.game { background: var(--panel); border-radius: 18px; padding: 20px 26px; overflow: hidden;
        display: flex; flex-direction: column; gap: 8px; border-left: 8px solid var(--line); }
.game > * { flex-shrink: 0; line-height: 1.25; }
.cols3 .game, .rows2 .game { gap: 4px; padding: 18px 24px; }
.game-live { border-left-color: var(--loss); }
.game-done { border-left-color: var(--accent); }
.game-head { display: flex; justify-content: space-between; align-items: center; }
.game-team { font-size: 40px; font-weight: 800; color: var(--accent); }
.pill { display: inline-block; border-radius: 999px; padding: 2px 18px; font-size: 24px; font-weight: 800;
        margin-left: 10px; background: var(--line); }
.pill-live { background: var(--loss); animation: pulse 2s ease-in-out infinite; }
.pill-done { background: var(--accent); color: var(--bg); }
@keyframes pulse { 50% { opacity: 0.55; } }
.game-meta, .game-venue { font-size: 22px; color: var(--muted); white-space: nowrap; overflow: hidden;
                          text-overflow: ellipsis; }
.game-venue { margin-top: auto; }
.side { display: grid; grid-template-columns: 1fr auto 130px; align-items: baseline; gap: 16px; font-size: 34px; }
.side-name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.side.ours .side-name { font-weight: 800; }
.side.batting .side-name::before { content: ""; display: inline-block; width: 16px; height: 16px; margin-right: 12px;
                                   border-radius: 50%; background: var(--loss); vertical-align: middle; }
.side-score { font-size: 46px; font-weight: 800; font-variant-numeric: tabular-nums; }
.side-overs { font-size: 24px; color: var(--muted); text-align: right; }
.game-note { font-size: 26px; }
.crease { font-size: 24px; color: var(--muted); display: flex; flex-wrap: wrap; gap: 4px 28px; }
.crease strong { color: var(--text); }
.cols3 .game-team { font-size: 34px; } .cols3 .side { font-size: 28px; grid-template-columns: 1fr auto 96px; }
.cols3 .side-score { font-size: 38px; } .cols3 .side-overs { font-size: 20px; }
.rows3 .game { padding: 12px 22px; gap: 2px; } .rows3 .game-meta, .rows3 .game-venue { font-size: 18px; }
.rows3 .game-note, .rows3 .crease { font-size: 20px; } .rows3 .side-score { font-size: 32px; }
.slide[data-screen="live"] .slide-body { display: block; }
.live-page { display: none; height: 770px; flex-direction: column; gap: 22px; }
.live-page.on { display: flex; }
.focus { flex: 1; min-height: 0; display: grid; gap: 28px; }
.focus-2 { grid-template-columns: 1fr 1fr; }
.focus-card { background: var(--panel); border-radius: 18px; padding: 18px 30px; border-left: 10px solid var(--loss);
              display: flex; flex-direction: column; gap: 8px; min-height: 0; overflow: hidden; }
.focus-card > * { flex-shrink: 0; }
.focus-card .game-team { font-size: 40px; flex-shrink: 0; }
.head-meta { flex: 1; min-width: 0; margin: 0 20px; font-size: 22px; color: var(--muted); white-space: nowrap;
             overflow: hidden; text-overflow: ellipsis; padding-top: 10px; }
.focus-2 .head-meta { display: none; }
.scoreboard { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.team-score { background: var(--bg); border-radius: 14px; padding: 8px 22px; display: grid;
              grid-template-columns: 1fr auto; grid-template-rows: auto auto; column-gap: 16px; }
.ts-name { font-size: 30px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.team-score.ours .ts-name { font-weight: 800; color: var(--accent); }
.team-score.batting .ts-name::before { content: ""; display: inline-block; width: 16px; height: 16px; margin-right: 10px;
                                       border-radius: 50%; background: var(--loss); vertical-align: middle; }
.ts-score { grid-row: 1 / 3; grid-column: 2; font-size: 72px; font-weight: 800; line-height: 1;
            align-self: center; font-variant-numeric: tabular-nums; }
.ts-overs { font-size: 22px; color: var(--muted); }
.state { font-size: 30px; font-weight: 700; }
.cards { display: grid; grid-template-columns: 1.35fr 1fr; gap: 30px; min-height: 0; flex-shrink: 1; overflow: hidden; }
.focus-2 .cards { grid-template-columns: 1.15fr 1fr; gap: 20px; }
.cards h3 { margin: 0 0 4px; font-size: 22px; color: var(--accent); text-transform: uppercase; letter-spacing: 1px; }
table.card-table { font-size: 25px; }
table.card-table th { font-size: 18px; padding: 3px 8px; }
table.card-table td { padding: 2px 8px; }
table.card-table th.num { width: 70px; }
table.card-table tr.out td { color: var(--muted); }
table.card-table tr.in td { font-weight: 800; color: var(--text); background: rgba(242, 182, 50, 0.1); }
.how { font-size: 18px; color: var(--muted); font-weight: 400; margin-left: 8px; }
.facts, .earlier { margin: 0; font-size: 22px; color: var(--muted); white-space: nowrap; overflow: hidden;
                   text-overflow: ellipsis; }
.earlier strong { color: var(--text); }
.focus-2 .ts-score { font-size: 54px; } .focus-2 .ts-name { font-size: 24px; } .focus-2 .team-score { padding: 8px 14px; }
.focus-2 table.card-table { font-size: 22px; } .focus-2 table.card-table th.num { width: 50px; }
.focus-2 .state { font-size: 24px; }
.strip { display: flex; gap: 18px; height: 132px; flex-shrink: 0; }
.tile { flex: 1; min-width: 0; background: var(--panel); border-radius: 14px; padding: 10px 18px;
        border-left: 6px solid var(--line); display: flex; flex-direction: column; gap: 4px; }
.tile-live { border-left-color: var(--loss); } .tile-done { border-left-color: var(--accent); }
.tile-head { display: flex; justify-content: space-between; align-items: center; }
.tile-team { font-size: 28px; font-weight: 800; color: var(--accent); white-space: nowrap; }
.tile .pill { font-size: 18px; padding: 1px 12px; }
.tile-line { font-size: 24px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tile-line small { font-size: 18px; color: var(--muted); }
.tile-note { font-size: 18px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.progress { position: absolute; left: 0; bottom: 0; height: 6px; width: 0; background: var(--accent); }
.paused .progress { background: var(--muted); }

.slide { opacity: 1; }
.live-page { display: none; height: 770px; flex-direction: column; gap: 22px; }
.live-page.on { display: flex; }
.live-page > .live-grid { height: 770px; }
.topbar .club small { letter-spacing: 4px; }
.extra-grid { display: grid; gap: 36px; height: 770px; }
.extra-grid.cols-1 { grid-template-columns: 1fr; }
.extra-grid.cols-2 { grid-template-columns: 1fr 1fr; }
.extra-grid.cols-3 { grid-template-columns: 1fr 1fr 1fr; }
.leaders { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 36px; height: 770px; }
.leaders table { font-size: 30px; }
.leaders th.num { width: 100px; }
table.card-table tr.in td { background: color-mix(in srgb, var(--accent) 12%, transparent); }
.topbar .brand { display: flex; align-items: center; gap: 24px; min-width: 0; }
.topbar .logo { height: 72px; max-width: 160px; object-fit: contain; }
.setup-screen { margin: 70px auto 0; max-width: 1400px; background: var(--panel); border-radius: 24px;
                padding: 50px 70px; border-left: 12px solid var(--accent); }
.setup-screen h2 { margin: 0 0 30px; font-size: 64px; color: var(--accent); }
.setup-screen ol { margin: 0; padding-left: 50px; font-size: 42px; line-height: 1.6; }
.sponsor { position: absolute; inset: 0; background: var(--bg); display: none; flex-direction: column;
           align-items: center; justify-content: center; gap: 30px; z-index: 5; }
.sponsor.on { display: flex; }
.sponsor > p { margin: 0; font-size: 34px; color: var(--muted); letter-spacing: 3px; text-transform: uppercase; }
.sponsor-body { display: flex; flex-direction: column; align-items: center; gap: 24px; }
.sponsor-image { max-width: 1600px; max-height: 780px; object-fit: contain; }
.sponsor-name { margin: 0; font-size: 40px; color: var(--text); }
.sponsor-card { width: 1600px; height: 800px; border-radius: 28px; display: flex; flex-direction: column;
                align-items: center; justify-content: center; gap: 26px; padding: 50px 80px; text-align: center;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.35); }
.sc-logo { max-width: 1100px; max-height: 380px; object-fit: contain; }
.sc-name { font-size: 64px; font-weight: 800; }
.sc-name-big { font-size: 120px; }
.sc-tag { font-size: 40px; max-width: 1350px; opacity: 0.85; }
.sc-web { font-size: 40px; font-weight: 700; letter-spacing: 1px; opacity: 0.9; }
/* Noto Sans is installed on the Pi; Segoe UI is the Windows look. */
body { font-family: "Segoe UI", "Noto Sans", Arial, sans-serif; }
"""

SCRIPT = """
(() => {
  const stage = document.getElementById("stage");
  const fit = () => {
    const scale = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
    stage.style.transform = `translate(${(window.innerWidth - 1920 * scale) / 2}px, ${(window.innerHeight - 1080 * scale) / 2}px) scale(${scale})`;
  };
  window.addEventListener("resize", fit); fit();

  const body = document.getElementById("board"), title = document.getElementById("title");
  const checked = document.getElementById("checked"), dots = document.getElementById("dots");
  const sponsorBox = document.getElementById("sponsor");
  const refresh = Number(stage.dataset.refresh) || 60, turn = Number(stage.dataset.page) || 20;
  let page = 0, loaded = false, turns = 0, sponsorAt = 0;
  let sponsors = [], every = 0, sponsorSeconds = 10;
  const show = (n) => {
    const pages = Array.from(body.querySelectorAll(".live-page"));
    page = pages.length ? ((n % pages.length) + pages.length) % pages.length : 0;
    pages.forEach((p, i) => p.classList.toggle("on", i === page));
    title.textContent = pages[page] ? pages[page].dataset.title : "";
    dots.innerHTML = pages.length > 1 ? pages.map((_, i) => `<span class="${i === page ? "on" : ""}"></span>`).join("") : "";
  };
  const load = async () => {
    try {
      const response = await fetch("/board", { cache: "no-store" });
      if (!response.ok) return;
      const board = await response.json();
      // Settings changed on the setup page: start again with the new look.
      if (board.version && board.version !== stage.dataset.version) { location.reload(); return; }
      sponsors = board.sponsors || []; every = board.sponsor_every || 0; sponsorSeconds = board.sponsor_seconds || 10;
      // PlayCricket unreachable: keep the last scores up and say so.
      if (board.error && loaded) { checked.textContent = `${board.checked} (couldn't reach PlayCricket)`; return; }
      body.innerHTML = board.html;
      loaded = !board.error;
      checked.textContent = board.checked;
      show(page);
    } catch (error) {
      // the scoreboard itself is restarting: try again next time
    }
  };
  // Every few pages, a sponsor's slide.
  const nextPage = () => {
    if (sponsorBox.classList.contains("on")) return;
    turns += 1;
    if (sponsors.length && every > 0 && turns % every === 0) {
      const sponsor = sponsors[sponsorAt % sponsors.length]; sponsorAt += 1;
      sponsorBox.querySelector(".sponsor-body").innerHTML = sponsor.html;
      sponsorBox.classList.add("on");
      setTimeout(() => { sponsorBox.classList.remove("on"); show(page + 1); }, sponsorSeconds * 1000);
      return;
    }
    show(page + 1);
  };
  load(); setInterval(load, refresh * 1000);
  setInterval(nextPage, turn * 1000);

  const clock = document.getElementById("clock-time"), day = document.getElementById("clock-date");
  const time = () => {
    const now = new Date();
    clock.textContent = now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    day.textContent = now.toLocaleDateString([], { weekday: "long", day: "numeric", month: "long" });
  };
  time(); setInterval(time, 15000);
})();
"""


def _blend(colour, other, amount):
    """Mix two #rrggbb colours: amount 0 = colour, 1 = other."""
    try:
        a = [int(colour[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(other[i:i + 2], 16) for i in (1, 3, 5)]
    except (ValueError, TypeError, IndexError):
        return colour
    return "#" + "".join(f"{round(x + (y - x) * amount):02x}" for x, y in zip(a, b))


def theme_css(settings):
    bg, panel, text, accent = (settings["background"], settings["panel"], settings["text"], settings["accent"])
    return (f":root {{ --bg: {bg}; --panel: {panel}; --text: {text}; --accent: {accent};"
            f" --line: {_blend(panel, text, 0.14)}; --muted: {_blend(text, bg, 0.35)}; }}")


def render_page():
    settings = config.load()
    logo = (f'<img class="logo" src="/media/logo?v={escape(config.version())}" alt="">'
            if settings.get("logo") else "")
    club = settings.get("club_name") or "Set up needed"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(settings["title"])}</title>
<style>{STYLE}{theme_css(settings)}</style></head>
<body>
<div id="stage" data-refresh="{settings["refresh_seconds"]}" data-page="{settings["page_seconds"]}"
     data-version="{escape(config.version())}">
  <div class="topbar">
    <div class="brand">{logo}<div class="club">{escape(settings["title"].upper())}<small>{escape(club.upper())}</small></div></div>
    <div class="clock"><span id="clock-time"></span><small id="clock-date"></small></div>
  </div>
  <article class="slide active" data-screen="live">
    <header class="slide-head"><h1 id="title">{escape(settings["title"])}</h1></header>
    <div class="slide-body" id="board">{render_board(None)}</div>
  </article>
  <div class="sponsor" id="sponsor"><p>Proudly supported by</p><div class="sponsor-body"></div></div>
  <div class="footer"><span>From PlayCricket · checked <span id="checked">&hellip;</span></span>
  <span class="dots" id="dots"></span></div>
</div>
<script>{SCRIPT}</script>
</body></html>"""
