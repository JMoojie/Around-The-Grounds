"""Tests with made-up teams and players (no real names in this repo)."""

import json
import os
import re
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# A made-up club, with its settings in a throwaway folder.
DATA = tempfile.TemporaryDirectory()
os.environ.update(ATG_DATA_DIR=DATA.name, ATG_CLUB_ID="11111111-2222-3333-4444-555555555555",
                  ATG_CLUB_NAME="Testville Tigers Cricket Club", ATG_TEAM_PREFIX="Testville Tigers",
                  ATG_SHORT_NAME="Tigers")

import config  # noqa: E402
import playcricket as pc  # noqa: E402
import scores  # noqa: E402
import screen  # noqa: E402
import server  # noqa: E402
import sponsor_cards  # noqa: E402
import extra_pages  # noqa: E402
import qr  # noqa: E402
import provisioning  # noqa: E402
import popups  # noqa: E402

CLUB = config.get("club_id")
TODAY = date(2026, 11, 21)


def team(team_id, name, score="", overs=None, batting=False, home=False, club=False):
    return {"id": team_id, "displayName": name, "scoreText": score, "oversBowled": overs,
            "isBatting": batting, "isHome": home, "owningOrganisation": {"id": CLUB if club else "other-club"}}


def fixture(match_id, status, teams, start="2026-11-21T13:00:00.0000000+11:00", result=""):
    return {"id": match_id, "status": status, "round": {"name": "Round 7"}, "resultText": result,
            "matchSchedule": [{"matchDay": 1, "startDateTime": start}],
            "venue": {"name": "Home Ground", "playingSurface": {"name": "Oval 1"}}, "teams": teams}


OURS = config.get("team_prefix")
LIVE = fixture("live1", "LIVE", [team("r1", f"{OURS} U13 Mixed", "5-70", 24, home=True, club=True),
                                 team("o1", "Visitors U13", "0-42", 5.2, batting=True)],
               start="2026-11-21T08:30:00.0000000+11:00")
SCORECARD = {
    "status": "LIVE",
    "matchSummary": {"resultText": "Visitors U13 trails by 28",
                     "teams": [{"id": "o1", "isBatting": True}, {"id": "r1", "isBatting": False}]},
    "innings": [
        {"battingTeamId": "r1", "runsScored": 70, "numberOfWicketsFallen": 5, "oversBowled": 24,
         "inningsCloseType": "Overs Completed",
         "batting": [{"playerShortName": "D Hitter", "runsScored": 40, "ballsFaced": 50, "dismissalType": "Bowled",
                      "dismissalText": "b: E Thrower"}],
         "bowling": [{"playerShortName": "E Thrower", "oversBowled": 4, "wicketsTaken": 2, "runsConceded": 12}]},
        {"battingTeamId": "o1", "runsScored": 42, "numberOfWicketsFallen": 0, "oversBowled": 5.2,
         "inningsCloseType": "In Progress",
         "batting": [{"playerShortName": "A Batter", "runsScored": 30, "ballsFaced": 20, "isOnStrike": True,
                      "dismissalType": "Not Out"},
                     {"playerShortName": "B Batter", "runsScored": 9, "ballsFaced": 12, "isOnNonStrike": True,
                      "dismissalType": "Not Out"}],
         "bowling": [{"playerShortName": "C Bowler", "oversBowled": 1.2, "wicketsTaken": 0, "runsConceded": 8,
                      "isBowling": True}],
         "fallOfWickets": []},
    ],
}
UPCOMING = fixture("soon1", "UPCOMING", [team("r2", f"{OURS} 1st XI", club=True), team("o2", "Rivals 1st XI")])
OTHER_CLUB = fixture("other", "LIVE", [team("x1", "Somewhere U13B Gold"), team("x2", "Someone Else")])
LAST_WEEK = fixture("old", "COMPLETED", [team("r3", f"{OURS} 2nd XI", "120", 40, club=True),
                                         team("o3", "Old Rivals", "3-121", 30)],
                    start="2026-11-14T13:00:00.0000000+11:00", result="Old Rivals won by 7 wickets")
NEXT_WEEK = fixture("next", "UPCOMING", [team("r4", f"{OURS} 3rd XI", club=True), team("o4", "New Rivals")],
                    start="2026-11-28T13:00:00.0000000+11:00")


def patched(matches):
    """PlayCricket replaced by the made-up fixtures above."""
    return [
        mock.patch.object(pc, "fetch_organisation_seasons", return_value={"seasons": [{"id": "s"}]}),
        mock.patch.object(pc, "fetch_organisation_teams", return_value={"teams": [
            {"id": "r1", "name": f"{OURS} U13 Mixed", "grades": [{"id": "g1", "name": "U13"}]},
            {"id": "r2", "name": "1st XI", "grades": [{"id": "g1", "name": "U13"}]}]}),
        mock.patch.object(pc, "fetch_grade_matches", return_value={"matches": matches}),
        mock.patch.object(pc, "fetch_match_scorecard", return_value=SCORECARD),
    ]


def run_board(matches, today=TODAY):
    # The clock stands at 7 am on the made-up match day.
    patches = patched(matches) + [mock.patch.object(scores, "_now", return_value=scores._local(
        f"{today.isoformat()}T07:00:00+11:00"))]
    for p in patches:
        p.start()
    try:
        return scores.board(today)
    finally:
        for p in patches:
            p.stop()


class ScoresTests(unittest.TestCase):
    def test_live_game(self):
        game = scores.summarise(LIVE, SCORECARD, {"r1"}, {}, "U13 Sat B", TODAY)
        self.assertEqual(game["state"], "live")
        self.assertEqual(game["team"], "U13 Mixed")
        self.assertEqual([(s["name"], s["score"], s["overs"], s["ours"]) for s in game["sides"]],
                         [("U13 Mixed", "5/70", "24", True), ("Visitors U13", "0/42", "5.2", False)])
        self.assertEqual(game["start"], "8:30 am")

    def test_match_day(self):
        result = run_board([LIVE, UPCOMING, OTHER_CLUB, LAST_WEEK])
        self.assertEqual(result["mode"], "today")
        # The other club's team isn't ours, and last week's game is over.
        self.assertEqual([(g["team"], g["state"]) for g in result["games"]],
                         [("U13 Mixed", "live"), ("1st XI", "upcoming")])

    def test_between_match_days(self):
        result = run_board([LAST_WEEK, NEXT_WEEK], today=date(2026, 11, 18))
        self.assertEqual(result["mode"], "between")
        self.assertEqual(result["results_day"], date(2026, 11, 14))
        self.assertEqual([(g["team"], g["state"], g["result"]) for g in result["results"]],
                         [("2nd XI", "done", "Old Rivals won by 7 wickets")])
        self.assertEqual([g["team"] for g in result["coming"]], ["3rd XI"])

    def test_game_nobody_is_scoring(self):
        with mock.patch.object(scores, "_now", return_value=scores._local("2026-11-21T18:00:00+11:00")):
            game = scores.summarise(UPCOMING, None, {"r2"}, {}, "Division 2", TODAY)
        self.assertEqual(game["state"], "unscored")
        self.assertIn("No live score", screen._live_card(game))
        self.assertIn("Started 1:00 pm", screen._live_card(game))

    def test_scores(self):
        self.assertEqual(scores._innings_score({"runsScored": 59, "numberOfWicketsFallen": 8,
                                                "inningsCloseType": "All Out"}), "59")
        self.assertEqual(scores._score_text("4-39"), "4/39")


class ScreenTests(unittest.TestCase):
    def test_live_page(self):
        result = run_board([LIVE, UPCOMING])
        html = screen.render_board(result)
        self.assertEqual(html.count('class="live-page'), 1)
        self.assertIn('data-title="Live scores"', html)
        self.assertIn(f"Bowling · {config.get("short_name")}", html)
        self.assertIn('<td>A Batter</td><td class="num">30*</td>', html)
        self.assertIn(f"{config.get("short_name")} 5/70</strong> (24 ov): D Hitter 40", html)
        self.assertIn('class="strip"', html)

    def test_match_day_also_shows_leaders_and_coming_up(self):
        result = run_board([LIVE, UPCOMING, NEXT_WEEK])
        self.assertEqual([g["team"] for g in result["coming"]], ["3rd XI"])
        result["leaders"] = {"season": "Summer", "runs": [("Dana Hitter", 160, "66")], "wickets": [], "catches": []}
        titles = re.findall(r'data-title="([^"]+)"', screen.render_board(result))
        self.assertEqual(titles, ["Live scores", "Season leaders · Summer", "Coming up · Saturday 28 November"])
        config.save(live_only=True)
        try:
            self.assertEqual(re.findall(r'data-title="([^"]+)"', screen.render_board(result)), ["Live scores"])
        finally:
            config.save(live_only=False)
        # Before any game starts: today's games, then the rest.
        quiet = run_board([UPCOMING, NEXT_WEEK])
        quiet["leaders"] = result["leaders"]
        self.assertEqual(re.findall(r'data-title="([^"]+)"', screen.render_board(quiet)),
                         ["Today&#x27;s games", "Season leaders · Summer",
                          "Coming up · Saturday 28 November"])

    def test_coming_up_shows_the_week_ahead(self):
        friday = fixture("fri", "UPCOMING", [team("r5", f"{OURS} U13", club=True), team("o5", "Juniors FC")],
                         start="2026-11-27T18:00:00.0000000+11:00")
        sunday = fixture("sun", "UPCOMING", [team("r6", f"{OURS} U18", club=True), team("o6", "Sunday CC")],
                         start="2026-11-29T09:00:00.0000000+11:00")
        later = fixture("dec", "UPCOMING", [team("r7", f"{OURS} 4th XI", club=True), team("o7", "Far Away")],
                        start="2026-12-05T13:00:00.0000000+11:00")
        undated = dict(fixture("tbc", "UPCOMING", [team("r8", f"{OURS} 5th XI", club=True), team("o8", "TBC")]),
                       matchSchedule=[])  # PlayCricket fixtures without a date yet
        result = run_board([LAST_WEEK, sunday, NEXT_WEEK, friday, later, undated], today=date(2026, 11, 24))
        # Friday's, Saturday's and Sunday's games, in order; the week after isn't included.
        self.assertEqual([g["team"] for g in result["coming"]], ["U13", "3rd XI", "U18"])
        html = screen.render_board(result)
        self.assertIn('data-title="Coming up · Fri 27 – Sun 29 November"', html)
        self.assertIn("Sat 1:00 pm", html)
        self.assertIn("Starts Fri 6:00 pm", html)

    def test_three_live_games_take_a_page_each(self):
        game = scores.summarise(LIVE, SCORECARD, {"r1"}, {}, "U13", TODAY)
        html = screen.render_board({"mode": "today", "games": [game, dict(game, id="b"), dict(game, id="c")]})
        self.assertEqual(html.count('class="live-page'), 3)
        self.assertIn("1 of 3", html)

    def test_between_pages(self):
        html = screen.render_board(run_board([LAST_WEEK, NEXT_WEEK], today=date(2026, 11, 18)))
        self.assertIn('data-title="Latest results · Saturday 14 November"', html)
        self.assertIn('data-title="Coming up · Saturday 28 November"', html)
        self.assertIn("Old Rivals won by 7 wickets", html)

    def test_messages(self):
        self.assertIn("No games scheduled", screen.render_board(
            {"mode": "between", "results": [], "coming": [], "results_day": None, "coming_day": None}))
        self.assertIn("Trying again", screen.render_board({"error": "Couldn't reach PlayCricket"}))


STATS = {
    "batting": [{"name": "Hitter, Dana", "statistics": {"battingAggregate": 160, "battingInnings": 5,
                                                        "battingHighScore": 66, "isBattingHSNotOut": True}},
                {"name": "Nought, Ned", "statistics": {"battingAggregate": 0, "battingInnings": 2}}],
    "bowling": [{"name": "Thrower, Eli", "statistics": {"bowlingWickets": 12, "bowlingRuns": 103,
                                                        "bowlingBestInnings": "4-14"}}],
    "fielding": [{"name": "Hands, Safe", "statistics": {"fieldingTotalCatches": 8, "matches": 6}}],
}


class LeadersTests(unittest.TestCase):
    def test_season_leaders_page(self):
        def stats(club_id, kind, season_id, offset=1, max_age=None):
            return {"totalRecords": len(STATS[kind]), "participants": STATS[kind]}

        with mock.patch.object(pc, "fetch_organisation_seasons",
                               return_value={"seasons": [{"id": "s", "name": "Summer 2026/27"}]}),              mock.patch.object(pc, "fetch_participant_statistics", side_effect=stats):
            leaders = scores.season_leaders()
        self.assertEqual(leaders["runs"], [("Dana Hitter", 160, "66*")])  # nobody on 0 runs
        self.assertEqual(leaders["wickets"], [("Eli Thrower", 12, "4/14")])
        self.assertEqual(leaders["catches"], [("Safe Hands", 8, 6)])
        html = screen.render_board({"mode": "between", "results": [], "coming": [], "results_day": None,
                                    "coming_day": None, "leaders": leaders})
        self.assertIn('data-title="Season leaders · Summer 2026/27"', html)
        self.assertIn("<td>Dana Hitter</td><td class=\"num\">160</td>", html)


class ServerTests(unittest.TestCase):
    def test_routes(self):
        client = server.app.test_client()
        self.assertIn(b"AROUND THE GROUNDS", client.get("/").data)
        self.assertEqual(client.get("/health").data, b"ok")
        with mock.patch.object(scores, "live_board", return_value={"error": "Couldn't reach PlayCricket",
                                                                   "checked": "1:00 pm"}):
            data = client.get("/board").get_json()
        self.assertEqual(data["checked"], "1:00 pm")
        self.assertIn("Trying again", data["html"])


PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 64


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.client = server.app.test_client()
        self.addCleanup(lambda: config.SETTINGS_FILE.unlink(missing_ok=True))

    def token(self):
        page = self.client.get("/setup").get_data(as_text=True)
        return re.search(r'name="csrf" value="([^"]+)"', page).group(1)

    def test_first_pin_then_setup(self):
        self.assertIn("Choose a setup PIN", self.client.get("/setup").get_data(as_text=True))
        self.client.post("/setup/pin", data={"pin": "12", "again": "12"})
        self.assertIn("4 to 8 digits", self.client.get("/setup").get_data(as_text=True))
        self.client.post("/setup/pin", data={"pin": "2468", "again": "2468"})
        self.assertIn("Link to your club", self.client.get("/setup").get_data(as_text=True))
        # A second visitor needs the PIN.
        other = server.app.test_client()
        self.assertIn("Enter the setup PIN", other.get("/setup").get_data(as_text=True))
        with mock.patch.object(server.time, "sleep"):
            other.post("/setup/login", data={"pin": "0000"})
        self.assertIn("isn&#x27;t right", other.get("/setup").get_data(as_text=True))
        other.post("/setup/login", data={"pin": "2468"})
        self.assertIn("Link to your club", other.get("/setup").get_data(as_text=True))
        # Changing settings without the form's token is refused.
        self.client.post("/setup/look", data={"title": "Hacked"})
        self.assertNotEqual(config.get("title"), "Hacked")

    def test_club_look_and_sponsors(self):
        self.client.post("/setup/pin", data={"pin": "2468", "again": "2468"})
        found = {"club_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "club_name": "Riverside Cricket Club",
                 "team_prefix": "Riverside", "short_name": "Riverside", "logo_url": "", "season": "Summer", "teams": 8}
        with mock.patch.object(scores, "discover_club", return_value=found) as discover:
            self.client.post("/setup/club/find", data={
                "csrf": self.token(), "link": "https://play.cricket.com.au/club/riverside/" + found["club_id"]})
        discover.assert_called_once_with(found["club_id"])
        # A link without the club's ID explains what's missing.
        with mock.patch.object(scores, "discover_club") as never:
            self.client.post("/setup/club/find", data={
                "csrf": self.token(), "link": "https://play.cricket.com.au/club/riverside-cricket-club"})
        never.assert_not_called()
        self.assertIn("doesn&#x27;t include the club&#x27;s ID", self.client.get("/setup").get_data(as_text=True))
        with mock.patch.object(scores, "discover_club", return_value=found):
            self.client.post("/setup/club/find", data={"csrf": self.token(), "link": found["club_id"]})
        self.assertIn("Is this your club?", self.client.get("/setup").get_data(as_text=True))
        self.client.post("/setup/club/save", data={"csrf": self.token(), "club_id": found["club_id"],
                                                   "club_name": "Riverside Cricket Club", "short_name": "Rivers",
                                                   "team_prefix": "Riverside"})
        self.assertEqual((config.get("club_id"), config.get("short_name")), (found["club_id"], "Rivers"))

        self.client.post("/setup/look", data={"csrf": self.token(), "title": "Game Day", "preset": "Black and red"})
        self.assertEqual((config.get("title"), config.get("accent")), ("Game Day", "#e03131"))
        page = self.client.get("/").get_data(as_text=True)
        self.assertIn("GAME DAY", page)
        self.assertIn("--accent: #e03131", page)

        from io import BytesIO
        self.client.post("/setup/sponsors/add", data={"csrf": self.token(), "name": "Local Bakery",
                                                      "image": (BytesIO(PNG), "bakery.png")},
                         content_type="multipart/form-data")
        self.client.post("/setup/sponsors/add", data={"csrf": self.token(), "image": (BytesIO(b"not an image"), "x.png")},
                         content_type="multipart/form-data")
        sponsors = config.get("sponsors")
        self.assertEqual([s["name"] for s in sponsors], ["Local Bakery"])
        self.assertEqual(self.client.get(f"/media/sponsors/{sponsors[0]['file']}").data, PNG)
        with mock.patch.object(scores, "live_board", return_value={"error": "x", "checked": "1:00 pm"}):
            data = self.client.get("/board").get_json()
        self.assertIn("Local Bakery", data["sponsors"][0]["html"])
        self.assertIn(f"/media/sponsors/{sponsors[0]['file']}", data["sponsors"][0]["html"])
        self.assertEqual(data["version"], config.version())

        # A slide made from a sponsor's website: checked and edited before it's added.
        found = {"name": "Westside Bakery", "tagline": "Fresh bread daily", "colour": "#c92a2a",
                 "web": "westsidebakery.example", "logo_url": "https://westsidebakery.example/logo.png",
                 "logo_options": ["https://westsidebakery.example/logo.png"]}
        with mock.patch.object(sponsor_cards, "from_website", return_value=found):
            self.client.post("/setup/sponsors/find", data={"csrf": self.token(), "website": "westsidebakery.example"})
        self.assertIn("Check the slide", self.client.get("/setup").get_data(as_text=True))
        with mock.patch.object(sponsor_cards, "download_logo", return_value=(PNG, "png")):
            self.client.post("/setup/sponsors/save-card", data={
                "csrf": self.token(), "name": "Westside Bakery", "tagline": "Hot pies on game day",
                "colour": "#c92a2a", "logo": "https://westsidebakery.example/logo.png"})
        card = config.get("sponsors")[1]
        self.assertEqual((card["kind"], card["tagline"], card["web"]), ("card", "Hot pies on game day", "westsidebakery.example"))
        self.assertEqual(self.client.get(f"/media/sponsors/{card['file']}").data, PNG)
        with mock.patch.object(scores, "live_board", return_value={"error": "x", "checked": "1:00 pm"}):
            html = self.client.get("/board").get_json()["sponsors"][1]["html"]
        self.assertIn('class="sponsor-card" style="background:#c92a2a;color:#ffffff"', html)
        self.assertIn("Hot pies on game day", html)
        self.assertIn("westsidebakery.example", html)

        # Edit it later: the whole description, and read the website again.
        page = self.client.get(f"/setup?sponsor={card['id']}").get_data(as_text=True)
        self.assertIn("Edit Westside Bakery", page)
        self.client.post("/setup/sponsors/edit", data={
            "csrf": self.token(), "id": card["id"], "name": "Westside Bakery & Cafe",
            "tagline": "Hot pies on game day. Fresh bread every morning, cakes for every celebration.",
            "colour": "#123456"})
        card = config.get("sponsors")[1]
        self.assertEqual((card["name"], card["colour"], card["show_name"]), ("Westside Bakery & Cafe", "#123456", False))
        self.assertIn("cakes for every celebration", card["tagline"])
        with mock.patch.object(sponsor_cards, "from_website", return_value=dict(found, tagline="The full story " * 10)):
            response = self.client.post("/setup/sponsors/reread", data={"csrf": self.token(), "id": card["id"]})
        self.assertIn(f"sponsor={card['id']}", response.headers["Location"])
        self.assertTrue(config.get("sponsors")[1]["tagline"].startswith("The full story"))
        with mock.patch.object(sponsor_cards, "from_website", return_value=dict(found, tagline="Everything, in full.")):
            self.client.post("/setup/sponsors/reread-all", data={"csrf": self.token()})
        self.assertEqual(config.get("sponsors")[1]["tagline"], "Everything, in full.")
        self.assertEqual(config.get("sponsors")[1]["name"], "Westside Bakery & Cafe")  # names kept

        for sponsor in config.get("sponsors"):
            self.client.post("/setup/sponsors/remove", data={"csrf": self.token(), "id": sponsor["id"]})
        self.assertEqual(config.get("sponsors"), [])

    def test_new_box_asks_to_be_set_up(self):
        config.save(club_id="")
        data = self.client.get("/board").get_json()
        self.assertIn("Let&#x27;s get set up", data["html"].replace("'", "&#x27;"))
        self.assertIn("/setup", data["html"])
        with mock.patch("system.hotspot", return_value={"ssid": "ATG-Setup", "password": "scoreboard",
                                                        "address": "10.42.0.1"}):
            data = self.client.get("/board").get_json()
        self.assertIn("Connect me to Wi-Fi", data["html"])
        self.assertIn("http://10.42.0.1:8080/setup", data["html"])


HOME_PAGE = b"""<html><head><title>Home | Westside Bakery</title>
<meta name="description" content="Fresh bread, pies and cakes baked every morning in Westside.">
<meta name="theme-color" content="#fc0">
<link rel="icon" sizes="16x16" href="/tiny.ico"><link rel="apple-touch-icon" href="/touch.png">
<meta property="og:image" content="https://cdn.example/banner.jpg?width=1200"></head>
<body><a class="site-logo" href="/"><img src="/img/brand.png?width=80"></a></body></html>"""


PACK = {"source": "Club archive", "published": "2026-11-22T10:00", "css": ".extra-grid[data-screen=leaders] th.num { width: 150px; }",
        "pages": [{"title": "Career leaders · Seniors", "html": "<section class='panel'><h2>Career runs</h2></section>",
                   "columns": 3, "screen": "leaders"}]}


class ExtraPagesTests(unittest.TestCase):
    def setUp(self):
        self.client = server.app.test_client()
        self.addCleanup(lambda: config.SETTINGS_FILE.unlink(missing_ok=True))
        self.addCleanup(extra_pages.clear)

    def send(self, pack, key):
        with mock.patch.object(server.time, "sleep"):
            return self.client.post("/api/pages", json=pack, headers={"Authorization": f"Bearer {key}"})

    def test_pages_from_another_program(self):
        # No key made yet: nothing is accepted.
        self.assertEqual(self.send(PACK, "").status_code, 401)
        config.save(extra_key="k" * 32)
        self.assertEqual(self.send(PACK, "wrong").status_code, 401)
        bad = {"pages": [{"title": "x", "html": "<img src=x onerror=alert(1)>"}]}
        self.assertEqual(self.send(bad, "k" * 32).status_code, 400)
        self.assertEqual(self.send({"pages": [{"title": "x", "html": "<script>1</script>"}]}, "k" * 32).status_code, 400)
        response = self.send(PACK, "k" * 32)
        self.assertEqual(response.get_json(), {"ok": True, "pages": 1})

        result = run_board([LAST_WEEK, NEXT_WEEK], today=date(2026, 11, 18))
        result["leaders"] = {"season": "Summer", "runs": [("Dana Hitter", 160, "66")], "wickets": [], "catches": []}
        html = screen.render_board(result)
        self.assertEqual(re.findall(r'data-title="([^"]+)"', html),
                         ["Latest results · Saturday 14 November", "Season leaders · Summer",
                          "Career leaders · Seniors", "Coming up · Saturday 28 November"])
        self.assertIn('<div class="extra-grid cols-3" data-screen="leaders"><section', html)
        self.assertIn("<style>.extra-grid[data-screen=leaders] th.num", html)
        # Turned off on the setup page: gone from the rotation.
        config.save(show_extra=False)
        self.assertNotIn("Career leaders", screen.render_board(result))
        config.save(show_extra=True)
        with mock.patch.object(server.time, "sleep"):
            self.client.delete("/api/pages", headers={"Authorization": "Bearer " + "k" * 32})
        self.assertIsNone(extra_pages.load())

    def test_spread_pages_are_mixed_in(self):
        self.assertEqual(screen._spread(list("ABCDEF"), ["1", "2"]), list("ABC1DE2F"))
        self.assertEqual(screen._spread(list("AB"), ["1", "2", "3"]), ["A", "1", "B", "2", "3"])
        self.assertEqual(screen._spread([], ["1"]), ["1"])
        config.save(extra_key="k" * 32)
        pack = {"pages": [{"title": "Career leaders", "html": "<p>a</p>"}, {"title": "Records", "html": "<p>b</p>"}]
                + [{"title": f"Profile {n}", "html": f"<p>{n}</p>", "spread": True} for n in (1, 2)]}
        self.assertEqual(self.send(pack, "k" * 32).status_code, 200)
        result = run_board([LAST_WEEK, NEXT_WEEK], today=date(2026, 11, 18))
        result["leaders"] = {"season": "Summer", "runs": [("Dana Hitter", 160, "66")], "wickets": [], "catches": []}
        titles = re.findall(r'data-title="([^"]+)"', screen.render_board(result))
        self.assertEqual(titles, ["Latest results · Saturday 14 November", "Season leaders · Summer", "Profile 1",
                                  "Career leaders", "Records", "Profile 2", "Coming up · Saturday 28 November"])

    def test_setup_makes_a_key(self):
        self.client.post("/setup/pin", data={"pin": "2468", "again": "2468"})
        page = self.client.get("/setup").get_data(as_text=True)
        token = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
        self.assertIn("No key yet", page)
        self.client.post("/setup/extra", data={"csrf": token, "action": "new-key"})
        key = config.get("extra_key")
        self.assertGreater(len(key), 20)
        self.assertIn(key, self.client.get("/setup").get_data(as_text=True))


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "deploy" / "pi"))
import cec_remote  # noqa: E402


class RemoteTests(unittest.TestCase):
    def test_tv_remote_buttons(self):
        monitor = [
            "Received from TV to Playback Device 1 (0 to 4): USER_CONTROL_PRESSED (0x44):",
            "	ui-cmd: right (0x04)",
            "Received from TV to Playback Device 1 (0 to 4): USER_CONTROL_RELEASED (0x45)",
            "Received from TV to Playback Device 1 (0 to 4): USER_CONTROL_PRESSED (0x44):",
            "	ui-cmd: select (0x00)",
            "Received from TV to Playback Device 1 (0 to 4): USER_CONTROL_PRESSED (0x44):",
            "	ui-cmd: rewind (0x48)",
            "Received from TV to Playback Device 1 (0 to 4): USER_CONTROL_PRESSED (0x44):",
            "	ui-cmd: number-5 (0x25)",   # not used
            "Received from TV to all (0 to 15): STANDBY (0x36)",
        ]
        self.assertEqual(list(cec_remote.presses(monitor)), ["next", "pause", "previous"])

    def test_presses_reach_the_box_screen_only(self):
        client = server.app.test_client()
        start = client.get("/remote?after=-1").get_json()
        self.assertEqual(start["actions"], [])
        self.assertEqual(client.post("/api/remote", json={"action": "next"}).status_code, 200)
        self.assertEqual(client.post("/api/remote", json={"action": "pause"}).status_code, 200)
        self.assertEqual(client.post("/api/remote", json={"action": "explode"}).status_code, 400)
        # Only the box itself may press buttons (not phones on the Wi-Fi).
        outside = client.post("/api/remote", json={"action": "next"}, environ_base={"REMOTE_ADDR": "192.168.1.50"})
        self.assertEqual(outside.status_code, 403)
        pressed = client.get(f"/remote?after={start['last']}").get_json()
        self.assertEqual(pressed["actions"], ["next", "pause"])
        self.assertEqual(client.get(f"/remote?after={pressed['last']}").get_json()["actions"], [])
        page = screen.render_page()
        self.assertIn('id="paused" hidden', page)
        self.assertIn("/remote?after=", page)


class SponsorCardTests(unittest.TestCase):
    def test_reading_a_sponsors_home_page(self):
        with mock.patch.object(sponsor_cards, "_get", return_value=("https://westside.example/", HOME_PAGE, "text/html")):
            found = sponsor_cards.from_website("westside.example")
        self.assertEqual(found["name"], "Westside Bakery")
        self.assertEqual(found["tagline"], "Fresh bread, pies and cakes baked every morning in Westside.")
        self.assertEqual(found["colour"], "#ffcc00")
        self.assertEqual(found["web"], "westside.example")
        # The image inside the "logo" link first; big icons only (no 16px favicon).
        self.assertEqual(found["logo_options"], ["https://westside.example/img/brand.png?width=80",
                                                 "https://cdn.example/banner.jpg?width=1200",
                                                 "https://westside.example/touch.png"])

    def test_bot_check_pages_and_private_addresses(self):
        page = b"<html><head><title>Just a moment...</title></head></html>"
        with mock.patch.object(sponsor_cards, "_get", return_value=("https://shy.example/", page, "text/html")):
            with self.assertRaises(ValueError):
                sponsor_cards.from_website("shy.example")
        for address in ("http://127.0.0.1/", "http://192.168.1.1/", "ftp://example.org/"):
            with self.assertRaises(ValueError):
                sponsor_cards._check_public(address)

    def test_full_descriptions(self):
        long = "Fresh bread every morning. " * 12
        self.assertEqual(sponsor_cards.clip_tagline("  Pies,   cakes and bread.  "), "Pies, cakes and bread.")
        clipped = sponsor_cards.clip_tagline(long)
        self.assertLessEqual(len(clipped), sponsor_cards.TAGLINE_LIMIT)
        self.assertTrue(clipped.endswith("morning."))  # stops at a full sentence
        html = sponsor_cards.card_html({"kind": "card", "name": "A", "tagline": "x" * 200}, "")
        self.assertIn('class="sc-tag sc-tag-long"', html)
        self.assertIn('class="sc-tag"', sponsor_cards.card_html({"kind": "card", "name": "A", "tagline": "Short"}, ""))

    def test_text_colour_suits_the_background(self):
        self.assertIn("color:#111111", sponsor_cards.card_html({"kind": "card", "name": "A", "colour": "#ffec0f"}, ""))
        self.assertIn("color:#ffffff", sponsor_cards.card_html({"kind": "card", "name": "A", "colour": "#0b1424"}, ""))
        with_logo = {"kind": "card", "name": "Westside", "colour": "#ffffff", "file": "x.png"}
        self.assertNotIn("sc-name", sponsor_cards.card_html(dict(with_logo, show_name=False), "/x.png"))
        self.assertIn("sc-name", sponsor_cards.card_html(dict(with_logo, show_name=True), "/x.png"))
        self.assertEqual(sponsor_cards.image_type(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"), "svg")


class QRTests(unittest.TestCase):
    def test_codes_on_the_setup_screens(self):
        self.assertEqual(qr.wifi_text("Club;Wi-Fi", 'pa:ss"word'), 'WIFI:T:WPA;S:Club\;Wi-Fi;P:pa\:ss\\"word;;')
        self.assertIn("<path d=\"M", qr.svg("http://10.42.0.1:8080/setup"))
        hotspot = screen.render_board({"hotspot": {"ssid": "ATG-Setup", "password": "scoreboard", "address": "10.42.0.1"}})
        self.assertEqual(hotspot.count('<svg class="qr"'), 2)
        self.assertIn("1 · Join the Wi-Fi", hotspot)
        self.assertNotIn("WIFI:", hotspot)  # the code itself, not the text, is on screen
        new_box = screen.render_board({"mode": "setup", "addresses": ["aroundthegrounds.local", "192.168.20.118"]})
        self.assertEqual(new_box.count('<svg class="qr"'), 1)
        with mock.patch.dict(sys.modules, {"qrcode": None}):  # without the QR package: words only
            self.assertEqual(qr.svg("x"), "")
            self.assertNotIn("<svg", screen.render_board({"mode": "setup", "addresses": ["192.168.20.118"]}))


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import prepare_club_card  # noqa: E402

FOUND = {"club_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "club_name": "Riverside Cricket Club",
         "team_prefix": "Riverside", "short_name": "Rivers", "logo_url": "https://example.org/logo.png",
         "season": "Summer 2026/27", "teams": 9}


class ClubCardTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(lambda: config.SETTINGS_FILE.unlink(missing_ok=True))

    def test_preparing_a_card_and_the_box_becoming_the_club(self):
        card = Path(self.folder.name) / "bootfs"
        card.mkdir()
        (card / "config.txt").write_text("# the Pi's settings")
        argv = ["prepare_club_card.py", "--card", str(card), "--club", FOUND["club_id"], "--pin", "482913",
                "--sheet-folder", self.folder.name]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(scores, "discover_club", return_value=FOUND),              mock.patch("builtins.print"):
            prepare_club_card.main()
        written = json.loads((card / "aroundthegrounds.json").read_text())
        self.assertEqual(written["club"]["club_name"], "Riverside Cricket Club")
        self.assertNotIn("wifi", written)  # the club joins its own Wi-Fi with the QR codes
        self.assertNotIn("482913", json.dumps(written))  # only the PIN's hash goes on the card
        sheet = next(Path(self.folder.name).glob("Around the Grounds welcome - *.html")).read_text(encoding="utf-8")
        self.assertIn("482913", sheet)
        self.assertIn("Connect me to Wi-Fi", sheet)

        # First start-up: the box becomes the club, logo fetched once the internet is there.
        with mock.patch.object(provisioning, "threading"):
            provisioning.start(paths=[card / "aroundthegrounds.json"])
        self.assertEqual((config.get("club_id"), config.get("short_name")), (FOUND["club_id"], "Rivers"))
        self.assertEqual(config.get("logo_pending"), FOUND["logo_url"])
        from werkzeug.security import check_password_hash
        self.assertTrue(check_password_hash(config.get("pin_hash"), "482913"))
        with mock.patch.object(provisioning.requests, "get", side_effect=provisioning.requests.ConnectionError):
            self.assertFalse(provisioning.fetch_pending_logo())  # no internet yet: try again later
        response = mock.Mock(content=PNG, raise_for_status=lambda: None)
        with mock.patch.object(provisioning.requests, "get", return_value=response):
            self.assertTrue(provisioning.fetch_pending_logo())
        self.assertEqual((config.DATA_DIR / config.get("logo")).read_bytes(), PNG)
        # Changes made later on the setup page aren't undone by the next start-up.
        config.save(short_name="River Rats")
        self.assertFalse(provisioning.apply(provisioning.find([card / "aroundthegrounds.json"])))
        self.assertEqual(config.get("short_name"), "River Rats")

    def test_not_a_card(self):
        with self.assertRaises(SystemExit):
            prepare_club_card.card_folder(self.folder.name)


class NoticeTests(unittest.TestCase):
    def setUp(self):
        self.client = server.app.test_client()
        self.addCleanup(lambda: config.SETTINGS_FILE.unlink(missing_ok=True))
        self.client.post("/setup/pin", data={"pin": "2468", "again": "2468"})

    def token(self):
        return re.search(r'name="csrf" value="([^"]+)"', self.client.get("/setup").get_data(as_text=True)).group(1)

    def test_notices_come_and_go(self):
        self.client.post("/setup/notices/add", data={"csrf": self.token(), "heading": "Presentation night",
                                                    "text": "Saturday 14 March, 7pm in the clubrooms.\nAll welcome!",
                                                    "until": "2026-03-14"})
        self.client.post("/setup/notices/add", data={"csrf": self.token(), "text": "Training Tuesday 5:30"})
        self.assertIn("Presentation night", self.client.get("/setup").get_data(as_text=True))
        with mock.patch.object(scores, "_now", return_value=scores._local("2026-03-10T09:00:00+11:00")):
            pages = screen._notice_pages()
        self.assertEqual(len(pages), 2)
        self.assertIn('<h2 class="notice-heading">Presentation night</h2>', pages[0][1])
        self.assertIn("<p>All welcome!</p>", pages[0][1])
        with mock.patch.object(scores, "_now", return_value=scores._local("2026-03-15T09:00:00+11:00")):
            self.assertEqual(len(screen._notice_pages()), 1)  # the day after its end date: gone
            page = self.client.get("/setup").get_data(as_text=True)
        self.assertIn("finished, no longer shown", page)
        # Mixed in with the other pages.
        result = run_board([LAST_WEEK, NEXT_WEEK], today=date(2026, 11, 18))
        with mock.patch.object(scores, "_now", return_value=scores._local("2026-03-10T09:00:00+11:00")):
            titles = re.findall(r'data-title="([^"]+)"', screen.render_board(result))
        self.assertEqual(titles.count("Club notice"), 2)
        self.assertNotEqual(titles[0], "Club notice")
        first = config.get("notices")[0]["id"]
        self.client.post("/setup/notices/remove", data={"csrf": self.token(), "id": first})
        self.assertEqual(len(config.get("notices")), 1)


MILESTONE_CARD = {
    "status": "LIVE",
    "teams": [{"id": "r1", "players": [{"participantId": "p1", "name": "Dana Hitter"},
                                       {"participantId": "p2", "name": "Eli Thrower"}]},
              {"id": "o1", "players": [{"participantId": "q1", "name": "Visiting Batter"}]}],
    "innings": [
        {"inningsNumber": 1, "battingTeamId": "r1", "runsScored": 180, "numberOfWicketsFallen": 4,
         "batting": [{"participantId": "p1", "playerShortName": "D Hitter", "runsScored": 104, "ballsFaced": 88,
                      "dismissalType": "Not Out"},
                     {"participantId": "p2", "playerShortName": "E Thrower", "runsScored": 12, "ballsFaced": 20,
                      "dismissalType": "Bowled"}],
         "bowling": [{"participantId": "q1", "playerShortName": "V Batter", "wicketsTaken": 6, "runsConceded": 20,
                      "oversBowled": 8}]},
        {"inningsNumber": 2, "battingTeamId": "o1", "runsScored": 60, "numberOfWicketsFallen": 7,
         "batting": [{"participantId": "q1", "playerShortName": "V Batter", "runsScored": 55, "ballsFaced": 40}],
         "bowling": [{"participantId": "p2", "playerShortName": "E Thrower", "wicketsTaken": 5, "runsConceded": 18,
                      "oversBowled": 6.3, "hatTricks": 1}]},
    ],
}


class PopupTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(lambda: config.SETTINGS_FILE.unlink(missing_ok=True))
        self.addCleanup(lambda: (config.DATA_DIR / "popups.json").unlink(missing_ok=True))

    def test_our_milestones_only(self):
        events = scores.milestones(LIVE, MILESTONE_CARD, {"r1"}, {})
        self.assertEqual([(e["big"], e["name"], e["detail"]) for e in events], [
            ("100", "Dana Hitter", "104* off 88 balls"),
            ("5 wickets", "Eli Thrower", "5/18 off 6.3 overs"),
            ("Hat-trick!", "Eli Thrower", "5/18 off 6.3 overs")])
        # The other side's 55 and six wickets aren't ours.
        self.assertEqual(events[0]["game"], "U13 Mixed v Visitors U13")
        self.assertIn('<p class="popup-big">100<span class="popup-what">runs</span></p>', screen.popup_html(events[0]))

    def test_each_pops_up_once_and_not_when_old(self):
        events = scores.milestones(LIVE, MILESTONE_CARD, {"r1"}, {})
        self.assertEqual(len(popups.fresh(events, now=1000)), 3)
        self.assertEqual(len(popups.fresh(events, now=1000 + 60)), 3)  # still offered: the screen shows each once
        self.assertEqual(popups.fresh(events, now=1000 + popups.POPUP_MINUTES * 60 + 1), [])
        # A new milestone later in the day is offered on its own.
        later = dict(events[0], id="match:p1:1:runs150", big="150")
        self.assertEqual([e["big"] for e in popups.fresh(events + [later], now=5000)], ["150"])

    def test_board_sends_them(self):
        client = server.app.test_client()
        event = scores.milestones(LIVE, MILESTONE_CARD, {"r1"}, {})[0]
        with mock.patch.object(scores, "live_board", return_value={"mode": "today", "games": [], "events": [event],
                                                                   "checked": "3:00 pm"}):
            data = client.get("/board").get_json()
            self.assertEqual([p["id"] for p in data["popups"]], [event["id"]])
            config.save(show_popups=False)
            self.assertEqual(client.get("/board").get_json()["popups"], [])


class DiscoverTests(unittest.TestCase):
    def test_club_from_its_playcricket_link(self):
        club = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        self.assertEqual(scores.club_id_from(f"https://play.cricket.com.au/club/riverside-cc/{club.upper()}"), club)
        self.assertEqual(scores.club_id_from("not a link"), "")
        mine = {"id": club, "name": "Riverside Cricket Club Inc", "logoUrl": "https://example.org/logo.png"}
        matches = {"matches": [{"teams": [
            {"id": "t1", "displayName": "Riverside Rams 1st XI", "owningOrganisation": mine},
            {"id": "t9", "displayName": "Elsewhere 1st XI", "owningOrganisation": {"id": "other"}}]},
            {"teams": [{"id": "t2", "displayName": "Riverside Rams U13", "owningOrganisation": mine}]},
            {"teams": [{"id": "t3", "displayName": "Riverside Rams 2nd XI", "owningOrganisation": mine}]}]}
        with mock.patch.object(pc, "fetch_organisation_seasons", return_value={"seasons": [{"id": "s", "name": "Summer"}]}), \
             mock.patch.object(pc, "fetch_organisation_teams", return_value={"teams": [
                 {"id": "t1", "grades": [{"id": "g1"}]}, {"id": "t2", "grades": [{"id": "g2"}]}]}), \
             mock.patch.object(pc, "fetch_grade_matches", return_value=matches):
            found = scores.discover_club(club)
        self.assertEqual((found["club_name"], found["team_prefix"], found["short_name"]),
                         ("Riverside Cricket Club Inc", "Riverside Rams", "Rams"))
        self.assertEqual(found["logo_url"], "https://example.org/logo.png")
        with self.assertRaises(ValueError):
            scores.discover_club("")


if __name__ == "__main__":
    unittest.main()
