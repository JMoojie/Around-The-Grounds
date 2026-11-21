"""Tests with made-up teams and players (no real names in this repo)."""

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
        self.assertEqual(data["sponsors"][0]["name"], "Local Bakery")
        self.assertEqual(data["version"], config.version())
        self.client.post("/setup/sponsors/remove", data={"csrf": self.token(), "file": sponsors[0]["file"]})
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
