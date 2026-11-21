"""Tests with made-up teams and players (no real names in this repo)."""

import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import playcricket as pc  # noqa: E402
import scores  # noqa: E402
import screen  # noqa: E402
import server  # noqa: E402

CLUB = config.CLUB_ID
TODAY = date(2026, 11, 21)


def team(team_id, name, score="", overs=None, batting=False, home=False, club=False):
    return {"id": team_id, "displayName": name, "scoreText": score, "oversBowled": overs,
            "isBatting": batting, "isHome": home, "owningOrganisation": {"id": CLUB if club else "other-club"}}


def fixture(match_id, status, teams, start="2026-11-21T13:00:00.0000000+11:00", result=""):
    return {"id": match_id, "status": status, "round": {"name": "Round 7"}, "resultText": result,
            "matchSchedule": [{"matchDay": 1, "startDateTime": start}],
            "venue": {"name": "Home Ground", "playingSurface": {"name": "Oval 1"}}, "teams": teams}


OURS = config.CLUB_NAME
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
        self.assertIn(f"Bowling · {config.SHORT_NAME}", html)
        self.assertIn('<td>A Batter</td><td class="num">30*</td>', html)
        self.assertIn(f"{config.SHORT_NAME} 5/70</strong> (24 ov): D Hitter 40", html)
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


if __name__ == "__main__":
    unittest.main()
