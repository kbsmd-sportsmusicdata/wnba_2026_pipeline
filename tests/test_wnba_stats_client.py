import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wnba_stats_client as client


class WnbaStatsClientTest(unittest.TestCase):
    def test_build_player_boxscore_params_uses_wnba_league_and_measure(self) -> None:
        params = client.build_player_boxscore_params(
            season="2026",
            season_type="Regular Season",
            measure_type="Advanced",
        )

        self.assertEqual(params["LeagueID"], "10")
        self.assertEqual(params["Season"], "2026")
        self.assertEqual(params["SeasonType"], "Regular Season")
        self.assertEqual(params["MeasureType"], "Advanced")
        self.assertEqual(params["PlayerID"], "0")
        self.assertEqual(params["PerMode"], "Totals")

    def test_build_team_boxscore_params_uses_requested_measure(self) -> None:
        params = client.build_team_boxscore_params(
            season="2026",
            season_type="Regular Season",
            measure_type="Misc",
        )

        self.assertEqual(params["LeagueID"], "10")
        self.assertEqual(params["MeasureType"], "Misc")
        self.assertEqual(params["TeamID"], "0")

    def test_normalize_result_sets_handles_resultset_payload(self) -> None:
        payload = {
            "resultSets": [
                {
                    "name": "PlayerGameLogs",
                    "headers": ["PLAYER_ID", "PLAYER_NAME", "PTS"],
                    "rowSet": [
                        [203000, "Test Player", 22],
                        [203001, "Test Player 2", 15],
                    ],
                }
            ]
        }

        normalized = client.normalize_result_sets(payload)

        self.assertIn("PlayerGameLogs", normalized)
        frame = normalized["PlayerGameLogs"]
        self.assertEqual(frame.columns.tolist(), ["PLAYER_ID", "PLAYER_NAME", "PTS"])
        self.assertEqual(len(frame), 2)
        self.assertEqual(frame.iloc[0]["PLAYER_NAME"], "Test Player")

    def test_normalize_result_sets_handles_resultset_payload_singular(self) -> None:
        payload = {
            "resultSet": {
                "name": "TeamGameLogs",
                "headers": ["TEAM_ID", "TEAM_NAME", "PTS"],
                "rowSet": [
                    [1611661313, "New York Liberty", 88],
                ],
            }
        }

        normalized = client.normalize_result_sets(payload)

        self.assertIn("TeamGameLogs", normalized)
        self.assertEqual(normalized["TeamGameLogs"].iloc[0]["TEAM_NAME"], "New York Liberty")

    def test_normalize_result_sets_handles_hana_datasets_payload(self) -> None:
        payload = {
            "datasets": {
                "PlayerGameLogs": {
                    "name": "PlayerGameLogs",
                    "rows": [
                        {"PLAYER_ID": 203000, "PLAYER_NAME": "Test Player", "PTS": 22},
                        {"PLAYER_ID": 203001, "PLAYER_NAME": "Test Player 2", "PTS": 15},
                    ],
                }
            }
        }

        normalized = client.normalize_result_sets(payload)

        self.assertIn("PlayerGameLogs", normalized)
        frame = normalized["PlayerGameLogs"]
        self.assertEqual(frame.columns.tolist(), ["PLAYER_ID", "PLAYER_NAME", "PTS"])
        self.assertEqual(len(frame), 2)


if __name__ == "__main__":
    unittest.main()
