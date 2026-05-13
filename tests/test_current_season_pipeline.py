import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import current_season_pipeline as pipeline


class CurrentSeasonPipelineTest(unittest.TestCase):
    def test_append_dedupes_player_game_logs_on_season_game_and_player(self) -> None:
        existing = pd.DataFrame(
            [
                {"season": 2026, "game_id": "g1", "player_id": "p1", "points": 12},
                {"season": 2026, "game_id": "g1", "player_id": "p2", "points": 8},
            ]
        )
        incoming = pd.DataFrame(
            [
                {"season": 2026, "game_id": "g1", "player_id": "p1", "points": 99},
                {"season": 2026, "game_id": "g2", "player_id": "p1", "points": 16},
            ]
        )

        combined = pipeline.append_dedupe_frame(
            existing=existing,
            incoming=incoming,
            key_columns=("season", "game_id", "player_id"),
        )

        self.assertEqual(len(combined), 3)
        self.assertEqual(
            combined.sort_values(["game_id", "player_id"])["points"].tolist(),
            [12, 8, 16],
        )

    def test_normalize_wehoop_player_boxscores_maps_required_columns(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "season": 2026,
                    "game_id": 401000001,
                    "date": "2026-05-11",
                    "athlete_id": 42,
                    "athlete_display_name": "Test Guard",
                    "team_id": 7,
                    "team_display_name": "Test Team",
                    "team_short_display_name": "TST",
                    "opponent_id": 8,
                    "opponent_display_name": "Other Team",
                    "minutes": 31.5,
                    "points": 17,
                    "rebounds": 5,
                    "assists": 6,
                    "season_type": 2,
                }
            ]
        )

        normalized = pipeline.normalize_wehoop_player_boxscores(frame)

        self.assertEqual(normalized.loc[0, "player_id"], "42")
        self.assertEqual(normalized.loc[0, "player_name"], "Test Guard")
        self.assertEqual(normalized.loc[0, "team_id"], "7")
        self.assertEqual(normalized.loc[0, "team_name"], "Test Team")
        self.assertEqual(normalized.loc[0, "team_abbreviation"], "TST")
        self.assertEqual(normalized.loc[0, "game_id"], "401000001")
        self.assertEqual(normalized.loc[0, "season_type"], "Regular Season")
        self.assertEqual(normalized.loc[0, "source_system"], "wehoop")
        self.assertEqual(normalized.loc[0, "source_variant"], "player_boxscores")

    def test_normalize_schedule_uses_regular_and_playoff_labels(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "season": 2026,
                    "game_id": 401000001,
                    "date": "2026-05-11",
                    "season_type": 2,
                    "home_team_id": 7,
                    "home_team_display_name": "Home",
                    "away_team_id": 8,
                    "away_team_display_name": "Away",
                },
                {
                    "season": 2026,
                    "game_id": 401000099,
                    "date": "2026-09-15",
                    "season_type": 3,
                    "home_team_id": 7,
                    "home_team_display_name": "Home",
                    "away_team_id": 8,
                    "away_team_display_name": "Away",
                },
            ]
        )

        normalized = pipeline.normalize_wehoop_schedule(frame)

        self.assertEqual(normalized["season_type"].tolist(), ["Regular Season", "Playoffs"])
        self.assertEqual(normalized["source_variant"].nunique(), 1)


if __name__ == "__main__":
    unittest.main()
