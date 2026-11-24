"""Around the Grounds: the club's games and scores, straight from PlayCricket.

Read only: nothing is stored. ``board`` returns either today's games (with
full batting and bowling cards for games being played) or, on a day without
games, the latest results and the next match day's fixtures.
"""

import threading
from datetime import datetime, timedelta

import config
import playcricket as pc

import re

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

# How long PlayCricket responses are reused, in seconds.
TEAMS_MAX_AGE = 6 * 60 * 60      # the club's teams and grades for the season
FIXTURES_MAX_AGE = 15 * 60       # each grade's fixture list (finds today's games)
SCORES_MAX_AGE = 90              # a game being played today
RESULT_MAX_AGE = 60 * 60         # a game already finished
LEADERS_MAX_AGE = 60 * 60        # season statistics (they change after games are finalised)
LEADERS_ROWS = 10

COMING_DAYS = 7                  # "Coming up": every game in the week from the next match day
STATE_ORDER = {"live": 0, "upcoming": 1, "done": 2, "unscored": 3, "off": 4}

_lock = threading.Lock()
_zones = {}


def _timezone():
    name = config.get("timezone")
    if name not in _zones:
        try:
            _zones[name] = ZoneInfo(name) if ZoneInfo else None
        except Exception:  # unknown zone, or no timezone data installed
            _zones[name] = None
    return _zones[name]


def _now():
    zone = _timezone()
    return datetime.now(zone) if zone else datetime.now()


def _local(start):
    """A PlayCricket start time as a local datetime (None if unreadable)."""
    try:
        parsed = datetime.fromisoformat(str(start or "").replace("0000000", "000"))
    except ValueError:
        try:
            parsed = datetime.fromisoformat(str(start)[:19])
        except ValueError:
            return None
    zone = _timezone()
    if parsed.tzinfo is not None and zone is not None:
        parsed = parsed.astimezone(zone)
    return parsed


def _clock(moment):
    return moment.strftime("%I:%M %p").lstrip("0").lower() if moment else ""


def _starts(record):
    return [moment for moment in (_local(item.get("startDateTime"))
                                  for item in (record.get("matchSchedule") or [])) if moment]


def is_today(record, today):
    """Scheduled today, or a game still in progress from an earlier day."""
    if any(moment.date() == today for moment in _starts(record)):
        return True
    return str(record.get("status") or "").upper() == "LIVE" and any(
        moment.date() < today for moment in _starts(record))


def team_label(name):
    """'<club name> U13 Mixed' -> 'U13 Mixed'."""
    text = str(name or "").strip()
    prefix = config.get("team_prefix").strip()
    if prefix and text.casefold().startswith(prefix.casefold()) and text[len(prefix):].strip():
        return text[len(prefix):].strip()
    return text


def _is_club(team, club_team_ids):
    organisation = (team.get("owningOrganisation") or {}).get("id")
    return organisation == config.get("club_id") or str(team.get("id")) in club_team_ids


def _overs(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{number:g}"


def _innings_score(inning):
    """'5/70' (wickets/runs, Australian style), '59' when all out, '6/180d' declared."""
    runs = inning.get("runsScored") or 0
    wickets = inning.get("numberOfWicketsFallen") or 0
    all_out = str(inning.get("inningsCloseType") or "").casefold() == "all out" or wickets >= 10
    text = f"{runs}" if all_out else f"{wickets}/{runs}"
    return text + ("d" if inning.get("isDeclared") else "")


def _score_text(text):
    """PlayCricket's summary score '5-70' -> '5/70'."""
    text = str(text or "").strip()
    return text.replace("-", "/") if text else ""


def _state(status, record, scorecard):
    status = str(status or "").upper()
    if status == "LIVE":
        return "live"
    if status in ("COMPLETED", "FORFEIT"):
        return "done"
    if status in ("ABANDONED", "CANCELLED", "POSTPONED"):
        return "off"
    # PENDING once play has started: finished, awaiting the result being confirmed.
    if (scorecard or {}).get("innings") or any(
            str(team.get("scoreText") or "").strip() for team in record.get("teams") or []):
        return "done"
    return "upcoming"


def _at_the_crease(innings):
    """Batters in and bowler on in the innings being played."""
    if not innings:
        return [], None
    current = innings[-1]
    batting = current.get("batting") or []
    on_strike = [b for b in batting if b.get("isOnStrike") or b.get("isOnNonStrike")]
    if not on_strike:
        on_strike = [b for b in batting if str(b.get("dismissalType") or "").casefold() == "not out"]
    batters = [
        {"name": b.get("playerShortName") or "", "runs": b.get("runsScored") or 0,
         "balls": b.get("ballsFaced") or 0, "strike": bool(b.get("isOnStrike"))}
        for b in sorted(on_strike, key=lambda b: not b.get("isOnStrike"))[:2]
    ]
    bowler = next((b for b in current.get("bowling") or [] if b.get("isBowling")), None)
    if bowler:
        bowler = {"name": bowler.get("playerShortName") or "", "overs": _overs(bowler.get("oversBowled")),
                  "wickets": bowler.get("wicketsTaken") or 0, "runs": bowler.get("runsConceded") or 0}
    return batters, bowler


def _balls(overs):
    try:
        whole, _, part = f"{float(overs):.1f}".partition(".")
        return int(whole) * 6 + int(part)
    except (TypeError, ValueError):
        return 0


def _innings_detail(inning, names, in_progress):
    """Batting and bowling card of one innings, for the big live view."""
    batting = []
    for b in inning.get("batting") or []:
        how = str(b.get("dismissalType") or "")
        not_out = how.casefold() == "not out"
        batting.append({
            "name": b.get("playerShortName") or "", "runs": b.get("runsScored") or 0,
            "balls": b.get("ballsFaced") or 0, "fours": b.get("foursScored") or 0,
            "sixes": b.get("sixesScored") or 0,
            "out": "not out" if not_out else (b.get("dismissalText") or how).replace(": ", " "),
            "dismissed": not not_out and "retired" not in how.casefold(),
            "in": bool(b.get("isOnStrike") or b.get("isOnNonStrike")), "strike": bool(b.get("isOnStrike")),
        })
    if in_progress and not any(b["in"] for b in batting):
        for b in batting:
            b["in"] = b["out"] == "not out"
    bowling = [
        {"name": b.get("playerShortName") or "", "overs": _overs(b.get("oversBowled")),
         "maidens": b.get("maidensBowled") or 0, "runs": b.get("runsConceded") or 0,
         "wickets": b.get("wicketsTaken") or 0, "now": bool(b.get("isBowling")) and in_progress}
        for b in inning.get("bowling") or []
    ]
    fall = (inning.get("fallOfWickets") or [])
    last = max(fall, key=lambda f: f.get("order") or 0) if fall else None
    last_batter = next((b for b in batting if last and b["name"] == last.get("playerShortName")), None)
    balls = _balls(inning.get("oversBowled"))
    team_id = str(inning.get("battingTeamId"))
    return {
        "team_id": team_id, "team": names.get(team_id, ""),
        "score": _innings_score(inning), "overs": _overs(inning.get("oversBowled")),
        "extras": inning.get("totalExtras") or 0,
        "run_rate": f"{(inning.get('runsScored') or 0) * 6 / balls:.2f}" if balls else "",
        "last_wicket": (f"{last.get('playerShortName')} {last_batter['runs'] if last_batter else ''}".strip()
                        + f" at {last.get('order')}/{last.get('runs')}") if last else "",
        "batting": batting, "bowling": bowling, "in_progress": in_progress,
    }


def top_performers(scorecard, our_ids):
    """The club's best with the bat and the ball in a game: {"bat": {...}, "bowl": {...}} (either may be None)."""
    if not scorecard or not our_ids:
        return None
    full_names = {str(player.get("participantId")): player.get("name") or ""
                  for team in scorecard.get("teams") or [] for player in team.get("players") or []}

    def name(row):
        return full_names.get(str(row.get("participantId"))) or row.get("playerShortName") or ""

    bat = bowl = None
    for inning in scorecard.get("innings") or []:
        if str(inning.get("battingTeamId")) in our_ids:
            for row in inning.get("batting") or []:
                runs, balls = row.get("runsScored") or 0, row.get("ballsFaced") or 0
                if runs and (bat is None or (runs, -balls) > (bat["runs"], -bat["balls"])):
                    not_out = str(row.get("dismissalType") or "").casefold() in ("not out", "retired not out")
                    bat = {"name": name(row), "runs": runs, "balls": balls, "not_out": not_out}
        else:
            for row in inning.get("bowling") or []:
                wickets, conceded = row.get("wicketsTaken") or 0, row.get("runsConceded") or 0
                if wickets and (bowl is None or (wickets, -conceded) > (bowl["wickets"], -bowl["runs"])):
                    bowl = {"name": name(row), "wickets": wickets, "runs": conceded,
                            "overs": _overs(row.get("oversBowled"))}
    return {"bat": bat, "bowl": bowl} if bat or bowl else None


def summarise(record, scorecard, club_team_ids, team_names=None, grade_name="", today=None):
    """One game for the screen, from its fixture record and (optional) scorecard."""
    team_names = team_names or {}
    summary_teams = {str(t.get("id")): t for t in ((scorecard or {}).get("matchSummary") or {}).get("teams") or []}
    innings = (scorecard or {}).get("innings") or []
    sides = []
    for team in record.get("teams") or []:
        team_id = str(team.get("id"))
        summary = summary_teams.get(team_id, {})
        # Innings nobody batted in (e.g. a game washed out before a ball) don't count as a score.
        own = [i for i in innings if str(i.get("battingTeamId")) == team_id
               and (i.get("runsScored") or i.get("numberOfWicketsFallen") or _balls(i.get("oversBowled")))]
        if own:
            score = " & ".join(_innings_score(i) for i in own)
            overs = _overs(own[-1].get("oversBowled"))
        else:
            score = _score_text(summary.get("scoreText") or team.get("scoreText"))
            overs = _overs(team.get("oversBowled")) if score else ""
        ours = _is_club(team, club_team_ids)
        name = team.get("displayName") or team.get("name") or ""
        sides.append({
            "id": team_id,
            "name": team_label(team_names.get(team_id) or name) if ours else name,
            "ours": ours, "score": score, "overs": overs,
            "batting": bool(summary.get("isBatting", team.get("isBatting"))),
            "home": bool(team.get("isHome")),
        })
    # Our team first.
    sides.sort(key=lambda side: not side["ours"])
    state = _state((scorecard or {}).get("status") or record.get("status"), record, scorecard)
    starts = sorted(_starts(record))
    if state == "upcoming" and starts and _now() > starts[-1]:
        state = "unscored"  # under way (or over), but nobody is scoring it on PlayCricket
    batters, bowler = _at_the_crease(innings) if state == "live" else ([], None)
    names = {side["id"]: side["name"] for side in sides}
    detail = ([_innings_detail(i, names, n == len(innings) - 1 and str(i.get("inningsCloseType") or "").casefold()
                               in ("in progress", ""))
               for n, i in enumerate(innings)] if state == "live" else [])
    today = today or _now().date()
    day = next((n for n, moment in enumerate(starts, 1) if moment.date() == today), 0) if len(starts) > 1 else 0
    venue = record.get("venue") or {}
    ground = " · ".join(str(part).strip() for part in
                        (venue.get("name"), (venue.get("playingSurface") or {}).get("name")) if str(part or "").strip())
    result = ((scorecard or {}).get("matchSummary") or {}).get("resultText") or record.get("resultText") or ""
    if "(local time)" in result:
        result = ""  # PlayCricket's start time standing in for a result that isn't there
    return {
        "id": record.get("id"),
        "team": sides[0]["name"] if sides else "",
        "grade": ((scorecard or {}).get("grade") or record.get("grade") or {}).get("name") or grade_name,
        "round": (record.get("round") or {}).get("name", ""),
        "state": state,
        "start": _clock(starts[day - 1] if day else starts[0]) if starts else "",
        "weekday": (starts[day - 1] if day else starts[0]).strftime("%a") if starts else "",
        "start_sort": starts[0].isoformat() if starts else "",
        "day": day,  # 1 or 2 for a two-day game, else 0
        "venue": ground,
        "home": bool(sides and sides[0]["home"]),
        "sides": sides,
        "result": result,
        "batters": batters,
        "bowler": bowler,
        "innings": detail,  # live games only: each innings' batting and bowling card
        "top": (top_performers(scorecard, {side["id"] for side in sides if side["ours"]})
                if state == "done" else None),  # finished games: the club's best bat and bowler
    }


def _club_grades():
    """(grade ids, club team ids, {team id: club team name}, {grade id: name}) for the current season."""
    seasons = pc.fetch_organisation_seasons(config.get("club_id"), max_age=TEAMS_MAX_AGE).get("seasons") or []
    grade_ids, team_ids, names, grade_names = [], set(), {}, {}
    for season in seasons[:1]:  # the newest season comes first
        teams = pc.fetch_organisation_teams(config.get("club_id"), season["id"],
                                            max_age=TEAMS_MAX_AGE).get("teams") or []
        for team in teams:
            team_ids.add(str(team.get("id")))
            names[str(team.get("id"))] = team.get("name") or ""
            for grade in team.get("grades") or ([team["grade"]] if team.get("grade") else []):
                if grade.get("id") and grade.get("isCurrent", True) is not False and grade["id"] not in grade_ids:
                    grade_ids.append(grade["id"])
                    grade_names[grade["id"]] = grade.get("name") or ""
    return grade_ids, team_ids, names, grade_names


BATTING_MILESTONES = (50, 100, 150, 200, 250, 300)
FIVE_WICKETS = 5


def milestones(record, scorecard, club_team_ids, team_names=None):
    """The club's players' milestones in one game: 50s and 100s, five wickets, hat-tricks.

    Each comes with an id that stays the same for the whole game, so the screen
    shows it once: "<match>:<player>:<innings>:<what>"."""
    if not scorecard:
        return []
    team_names = team_names or {}
    full_names = {str(player.get("participantId")): player.get("name") or ""
                  for team in scorecard.get("teams") or [] for player in team.get("players") or []}
    sides = {str(team.get("id")): team for team in record.get("teams") or []}
    ours = [team_id for team_id, team in sides.items() if _is_club(team, club_team_ids)]
    if not ours:
        return []
    our_team = team_label(team_names.get(ours[0]) or sides[ours[0]].get("displayName") or "")
    other = next((team.get("displayName") or "" for team_id, team in sides.items() if team_id not in ours), "")
    game = f"{our_team} v {other}" if other else our_team
    events = []
    for inning in scorecard.get("innings") or []:
        number = inning.get("inningsNumber") or inning.get("inningsOrder") or 1
        batting_ours = str(inning.get("battingTeamId")) in ours
        if batting_ours:
            for batter in inning.get("batting") or []:
                runs = batter.get("runsScored") or 0
                reached = max((mark for mark in BATTING_MILESTONES if runs >= mark), default=None)
                if not reached:
                    continue
                player = str(batter.get("participantId") or batter.get("playerShortName"))
                out = str(batter.get("dismissalType") or "").casefold() not in ("not out", "retired not out", "")
                events.append({
                    "id": f"{record.get('id')}:{player}:{number}:runs{reached}",
                    "big": str(reached), "what": "runs",
                    "name": full_names.get(player) or batter.get("playerShortName") or "",
                    "detail": f"{runs}{'' if out else '*'} off {batter.get('ballsFaced') or 0} balls", "game": game,
                })
        else:
            for bowler in inning.get("bowling") or []:
                player = str(bowler.get("participantId") or bowler.get("playerShortName"))
                name = full_names.get(player) or bowler.get("playerShortName") or ""
                wickets, conceded = bowler.get("wicketsTaken") or 0, bowler.get("runsConceded") or 0
                figures = f"{wickets}/{conceded} off {_overs(bowler.get('oversBowled'))} overs"
                if wickets >= FIVE_WICKETS:
                    events.append({"id": f"{record.get('id')}:{player}:{number}:wickets5", "big": "5 wickets",
                                   "what": "", "name": name, "detail": figures, "game": game})
                if (bowler.get("hatTricks") or 0) > 0:
                    events.append({"id": f"{record.get('id')}:{player}:{number}:hattrick", "big": "Hat-trick!",
                                   "what": "", "name": name, "detail": figures, "game": game})
    return events


def _first_day(record):
    starts = sorted(_starts(record))
    return starts[0].date() if starts else None


def _club_fixtures():
    """Every one of the club's fixtures this season: [(record, team ids, names, grade name)]."""
    grade_ids, team_ids, names, grade_names = _club_grades()
    fixtures, seen = [], set()
    for grade_id in grade_ids:
        for record in pc.fetch_grade_matches(grade_id, max_age=FIXTURES_MAX_AGE).get("matches") or []:
            if record.get("id") in seen or not any(_is_club(t, team_ids) for t in record.get("teams") or []):
                continue
            seen.add(record.get("id"))
            fixtures.append((record, grade_names.get(grade_id, "")))
    return fixtures, team_ids, names


def _with_scorecard(record):
    status = str(record.get("status") or "").upper()
    if status in ("ABANDONED", "CANCELLED", "UPCOMING"):
        return None
    try:
        return pc.fetch_match_scorecard(record["id"], max_age=RESULT_MAX_AGE if status == "COMPLETED"
                                        else SCORES_MAX_AGE)
    except Exception:
        return None  # the fixture's own summary score still shows


def _ordered(games):
    return sorted(games, key=lambda g: (STATE_ORDER.get(g["state"], 9), g["start_sort"], g["team"]))


def board(today=None):
    """{"mode": "today", "games": [...]} on a match day, otherwise {"mode": "between",
    "results": [...], "results_day": date}. Both also give the next match day's fixtures
    ("coming", from "coming_day" to "coming_until": the week ahead). Raises on network errors."""
    today = today or _now().date()
    with _lock:  # several screens asking at once share one set of fetches
        fixtures, team_ids, names = _club_fixtures()
        todays = [(r, g) for r, g in fixtures if is_today(r, today)]
        future = [d for d in (_first_day(r) for r, _ in fixtures) if d and d > today]
        coming_day = min(future) if future else None
        # The next match day's fixtures and past results come from the fixture
        # list's own scores: no scorecards needed.
        coming_until = coming_day + timedelta(days=COMING_DAYS - 1) if coming_day else None
        coming = sorted((summarise(r, None, team_ids, names, g, today) for r, g in fixtures
                         if coming_day and _first_day(r) and coming_day <= _first_day(r) <= coming_until),
                        key=lambda game: (game["start_sort"], game["team"]))
        if coming:
            coming_until = max(_local(game["start_sort"]).date() for game in coming)
        # Fixtures PlayCricket hasn't given a date yet (still to be played) go last, as "Date TBC".
        coming += [dict(summarise(r, None, team_ids, names, g, today), tbc=True) for r, g in fixtures
                   if not _first_day(r) and str(r.get("status") or "").upper() in ("UPCOMING", "PENDING")
                   and not any(str(t.get("scoreText") or "").strip() for t in r.get("teams") or [])]
        if todays:
            games, events = [], []
            for r, g in todays:
                scorecard = _with_scorecard(r)
                games.append(summarise(r, scorecard, team_ids, names, g, today))
                events += milestones(r, scorecard, team_ids, names)
            return {"mode": "today", "coming": coming, "coming_day": coming_day, "coming_until": coming_until,
                    "games": _ordered(games), "events": events}
        # The latest results: every game in the week up to the most recent game day
        # (a weekend's Friday juniors, Saturday seniors and Sunday games together).
        past = [d for d in (_first_day(r) for r, _ in fixtures) if d and d < today]
        results_day = max(past) if past else None
        results_from = results_day - timedelta(days=COMING_DAYS - 1) if results_day else None
        results = sorted((summarise(r, _with_scorecard(r), team_ids, names, g, today) for r, g in fixtures
                          if results_day and _first_day(r) and results_from <= _first_day(r) <= results_day),
                         key=lambda game: (game["start_sort"], game["team"]))
        if results:
            results_from = min(_local(game["start_sort"]).date() for game in results)
    return {"mode": "between", "results": results, "results_day": results_day, "results_from": results_from,
            "coming": coming, "coming_day": coming_day, "coming_until": coming_until}


JUNIOR = re.compile(r"^(u|under)[ -]?\d", re.I)


def is_junior(game):
    """A junior team: its name (or, failing that, its grade) starts with an age group (U10, U13,
    Under 15 ...). A team called "... XI" is always senior."""
    team = game.get("team") or ""
    if JUNIOR.match(team):
        return True
    return " xi" not in f" {team.lower()}" and bool(JUNIOR.match(game.get("grade") or ""))


def _player_name(participant):
    """PlayCricket's 'Venn, Heath' -> 'Heath Venn'."""
    name = str(participant.get("name") or participant.get("shortName") or "").strip()
    last, comma, first = name.partition(",")
    return f"{first.strip()} {last.strip()}".strip() if comma else name


def _all_statistics(kind, season_id):
    players, offset = [], 1
    while True:
        data = pc.fetch_participant_statistics(config.get("club_id"), kind, season_id=season_id, offset=offset,
                                               max_age=LEADERS_MAX_AGE)
        page = data.get("participants") or []
        players += page
        offset += 100
        if not page or offset > (data.get("totalRecords") or 0):
            return players


def season_leaders():
    """The season's top run scorers, wicket takers and catchers (all the club's grades together)."""
    seasons = pc.fetch_organisation_seasons(config.get("club_id"), max_age=TEAMS_MAX_AGE).get("seasons") or []
    if not seasons:
        return None
    season = seasons[0]
    stat = lambda p, key: (p.get("statistics") or {}).get(key) or 0  # noqa: E731

    batting = [p for p in _all_statistics("batting", season["id"]) if stat(p, "battingAggregate") > 0]
    batting.sort(key=lambda p: (-stat(p, "battingAggregate"), stat(p, "battingInnings"), _player_name(p)))
    bowling = [p for p in _all_statistics("bowling", season["id"]) if stat(p, "bowlingWickets") > 0]
    bowling.sort(key=lambda p: (-stat(p, "bowlingWickets"), stat(p, "bowlingRuns"), _player_name(p)))
    fielding = [p for p in _all_statistics("fielding", season["id"]) if stat(p, "fieldingTotalCatches") > 0]
    fielding.sort(key=lambda p: (-stat(p, "fieldingTotalCatches"), -stat(p, "fieldingStumpings"), _player_name(p)))
    return {
        "season": season.get("name") or "",
        "runs": [(_player_name(p), stat(p, "battingAggregate"),
                  f"{stat(p, 'battingHighScore')}{'*' if (p.get('statistics') or {}).get('isBattingHSNotOut') else ''}")
                 for p in batting[:LEADERS_ROWS]],
        "wickets": [(_player_name(p), stat(p, "bowlingWickets"),
                     str((p.get("statistics") or {}).get("bowlingBestInnings") or "").replace("-", "/"))
                    for p in bowling[:LEADERS_ROWS]],
        "catches": [(_player_name(p), stat(p, "fieldingTotalCatches"), stat(p, "matches"))
                    for p in fielding[:LEADERS_ROWS]],
    }


CLUB_LINK = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
CLUB_WORDS = re.compile(r"\s+(cricket club|cricket|club|cc)(\s+inc\.?|\s+incorporated)?$", re.I)


def club_id_from(text):
    """The club ID from a PlayCricket club page link (or the ID itself)."""
    match = CLUB_LINK.search(str(text or ""))
    return match.group(0).lower() if match else ""


def _common_prefix(names):
    """The words every name starts with: ['Altona Roosters 1st XI', 'Altona Roosters U13'] -> 'Altona Roosters'."""
    split = [n.split() for n in names if n.split()]
    if not split:
        return ""
    words = []
    for column in zip(*split):
        if all(w.casefold() == column[0].casefold() for w in column):
            words.append(column[0])
        else:
            break
    return " ".join(words)


def discover_club(club_id):
    """Everything setup needs about a club, from PlayCricket: its name, how its
    teams are named, a suggested short name and its logo. Raises ValueError."""
    if not club_id:
        raise ValueError("That doesn't look like a PlayCricket club link.")
    try:
        seasons = pc.fetch_organisation_seasons(club_id, max_age=0).get("seasons") or []
    except Exception as error:
        raise ValueError(f"PlayCricket doesn't know that club ({type(error).__name__}).") from error
    if not seasons:
        raise ValueError("PlayCricket has no seasons for that club.")
    teams = pc.fetch_organisation_teams(club_id, seasons[0]["id"]).get("teams") or []
    team_ids = {str(t.get("id")) for t in teams}
    club_name, logo, display_names = "", "", []
    for team in teams:
        for grade in (team.get("grades") or ([team["grade"]] if team.get("grade") else []))[:1]:
            for record in pc.fetch_grade_matches(grade["id"]).get("matches") or []:
                for side in record.get("teams") or []:
                    organisation = side.get("owningOrganisation") or {}
                    if organisation.get("id") == club_id or str(side.get("id")) in team_ids:
                        club_name = club_name or organisation.get("name") or ""
                        logo = logo or organisation.get("logoUrl") or ""
                        display_names.append(side.get("displayName") or "")
            if club_name and len(set(display_names)) >= 3:
                break
        if club_name and len(set(display_names)) >= 3:
            break
    club_name = club_name.strip()
    prefix = _common_prefix(sorted(set(display_names))) if len(set(display_names)) > 1 else ""
    if not prefix:
        prefix = CLUB_WORDS.sub("", club_name).strip()
    short = prefix.split()[-1] if prefix else ""
    return {"club_id": club_id, "club_name": club_name or prefix, "team_prefix": prefix,
            "short_name": short, "logo_url": logo, "season": seasons[0].get("name") or "",
            "teams": len(teams)}


def live_board():
    """``board()`` plus when it was checked, or {"error": ...} when PlayCricket can't be reached."""
    if not config.is_set_up():
        return {"mode": "setup", "checked": _clock(_now())}
    try:
        result = board()
    except Exception as error:  # offline, PlayCricket down, unexpected reply
        return {"error": f"Couldn't reach PlayCricket ({type(error).__name__})", "checked": _clock(_now())}
    result["leaders"] = None
    if config.get("show_leaders"):
        try:
            result["leaders"] = season_leaders()
        except Exception:
            pass  # the games, results and fixtures still show
    result["checked"] = _clock(_now())
    return result
